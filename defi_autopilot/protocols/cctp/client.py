"""Circle CCTP (Cross-Chain Transfer Protocol) V1 client.

Native burn-and-mint USDC transfers across EVM chains — no liquidity pools, no
wrapped assets.  The flow is three steps:

    1. burn   — source chain: TokenMessenger.depositForBurn(amount, dstDomain,
                mintRecipient, USDC)  → emits a MessageSent(bytes) event
    2. attest — off-chain: poll Circle's Iris attestation service with the
                keccak256 hash of the message bytes until status == "complete"
    3. mint   — destination chain: MessageTransmitter.receiveMessage(message,
                attestation)  → mints native USDC to the recipient

Because steps 1 and 3 live on different chains and step 2 is an asynchronous
off-chain wait, a CCTP transfer is the canonical resumable workflow.  The
``transfer`` orchestrator records progress in the shared state machine keyed by
``run_id`` so an interrupted transfer can resume at attest/mint without
re-burning.

Reference: https://developers.circle.com/cctp (V1 legacy interface)
"""

from __future__ import annotations

import os
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx
from web3 import Web3
from web3.logs import DISCARD

from defi_autopilot import audit as _audit
from defi_autopilot import policy as _policy
from defi_autopilot import state_machine
from defi_autopilot.core.rpc import get_chain_config, get_w3
from defi_autopilot.core.signer import get_address
from defi_autopilot.core.tx import approve_token, build_and_send_tx, check_allowance


# ── CCTP domain mapping (chain_id → CCTP domain id) ──────────────────────────
# Source: https://developers.circle.com/cctp/concepts/supported-chains-and-domains
CCTP_DOMAINS: Dict[int, int] = {
    1: 0,        # Ethereum
    43114: 1,    # Avalanche
    10: 2,       # Optimism
    42161: 3,    # Arbitrum
    8453: 6,     # Base
    137: 7,      # Polygon PoS
    130: 10,     # Unichain
}

# Native USDC token addresses per chain.
USDC_ADDRESSES: Dict[int, str] = {
    1: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    10: "0x0b2c639c533813f4aa9d7837caf62653d097ff85",
    42161: "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    8453: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    137: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
    130: "0x078D782b760474a361dDA0AF3839290b0EF57AD6",
    43114: "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
}

# TokenMessenger (depositForBurn) — CCTP V1 mainnet.
TOKEN_MESSENGER: Dict[int, str] = {
    1: "0xBd3fa81B58Ba92a82136038B25aDec7066af3155",
    10: "0x2B4069517957735bE00ceE0fadAE88a26365528f",
    42161: "0x19330d10D9Cc8751218eaf51E8885D058642E08A",
    8453: "0x1682Ae6375C4E4A97e4B583BC394c861A46D8962",
    137: "0x9daF8c91AEFAE50b9c0E69629D3F6Ca40cA3B3FE",
    130: "0x4e744b28E787c3aD0e810eD65A24461D4ac5a762",
    43114: "0x6B25532e1060CE10cc3B0A99e5683b91BFDe6982",
}

# MessageTransmitter (receiveMessage) — CCTP V1 mainnet.
MESSAGE_TRANSMITTER: Dict[int, str] = {
    1: "0x0a992d191DEeC32aFe36203Ad87D7d289a738F81",
    10: "0x4D41f22c5a0e5c74090899E5a8Fb597a8842b3e8",
    42161: "0xC30362313FBBA5cf9163F0bb16a0e01f01A896ca",
    8453: "0xAD09780d193884d503182aD4588450C416D6F9D4",
    137: "0xF3be9355363857F3e001be68856A2f96b4C39Ba9",
    130: "0x353bE9E2E38AB1D19104534e4edC21c643Df86f4",
    43114: "0x8186359aF5F57FbB40c6b14A588d2A59C0C29880",
}

ATTESTATION_API = "https://iris-api.circle.com"

USDC_DECIMALS = 6

# Minimal ABIs.
TOKEN_MESSENGER_ABI = [
    {
        "inputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "destinationDomain", "type": "uint32"},
            {"name": "mintRecipient", "type": "bytes32"},
            {"name": "burnToken", "type": "address"},
        ],
        "name": "depositForBurn",
        "outputs": [{"name": "_nonce", "type": "uint64"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

MESSAGE_TRANSMITTER_ABI = [
    {
        "inputs": [
            {"name": "message", "type": "bytes"},
            {"name": "attestation", "type": "bytes"},
        ],
        "name": "receiveMessage",
        "outputs": [{"name": "success", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [{"indexed": False, "name": "message", "type": "bytes"}],
        "name": "MessageSent",
        "type": "event",
    },
]


def address_to_bytes32(addr: str) -> bytes:
    """Left-pad a 20-byte EVM address to 32 bytes (CCTP mintRecipient format)."""
    return bytes(12) + bytes.fromhex(Web3.to_checksum_address(addr)[2:])


def _resolve_run_id(explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    for name in ("STAGEFORGE_RUN_ID", "AUDIT_RUN_ID", "RUN_ID"):
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return f"cctp-{uuid.uuid4().hex[:12]}"


class CCTPClient:
    """Circle CCTP V1 client bound to a source chain."""

    def __init__(self, chain_id: int):
        if chain_id not in CCTP_DOMAINS:
            raise ValueError(
                f"CCTP not supported on chain {chain_id}. "
                f"Supported: {sorted(CCTP_DOMAINS)}"
            )
        if chain_id not in TOKEN_MESSENGER:
            raise ValueError(f"No TokenMessenger address for chain {chain_id}")
        self.chain_id = chain_id
        self.domain = CCTP_DOMAINS[chain_id]
        self.config = get_chain_config(chain_id)
        self.w3 = get_w3(chain_id)
        self.usdc = Web3.to_checksum_address(USDC_ADDRESSES[chain_id])
        self.token_messenger = Web3.to_checksum_address(TOKEN_MESSENGER[chain_id])
        self.message_transmitter = Web3.to_checksum_address(MESSAGE_TRANSMITTER[chain_id])

    # ── Step 1: burn on source chain ─────────────────────────────────────────

    def burn(
        self,
        amount: int,
        dest_chain_id: int,
        mint_recipient: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Burn USDC on the source chain and return the CCTP message + hash.

        ``amount`` is in USDC base units (6 decimals).  ``mint_recipient``
        defaults to the signer's own address on the destination chain.
        """
        if dest_chain_id not in CCTP_DOMAINS:
            raise ValueError(f"CCTP destination chain {dest_chain_id} not supported")
        if dest_chain_id == self.chain_id:
            raise ValueError("source and destination chains must differ")

        signer_addr = get_address(private_key)
        recipient = mint_recipient or signer_addr
        dest_domain = CCTP_DOMAINS[dest_chain_id]

        # Approve USDC to the TokenMessenger if needed.
        allowance = check_allowance(self.chain_id, self.usdc, signer_addr, self.token_messenger)
        if allowance < amount:
            approve_token(self.chain_id, self.usdc, self.token_messenger, 2**256 - 1, private_key)

        contract = self.w3.eth.contract(address=self.token_messenger, abi=TOKEN_MESSENGER_ABI)
        data = contract.encode_abi(
            "depositForBurn",
            [amount, dest_domain, address_to_bytes32(recipient), self.usdc],
        )

        result = build_and_send_tx(
            chain_id=self.chain_id,
            to=self.token_messenger,
            data=data,
            private_key=private_key,
        )
        burn_tx = result["tx_hash"]

        # Parse MessageSent event to recover the message bytes for attestation.
        message_hex, message_hash = self._extract_message(burn_tx)

        return {
            "burn_tx": burn_tx,
            "status": result.get("status"),
            "src_chain_id": self.chain_id,
            "dest_chain_id": dest_chain_id,
            "amount": amount,
            "mint_recipient": recipient,
            "message": message_hex,
            "message_hash": message_hash,
        }

    def _extract_message(self, burn_tx: str) -> tuple[str, str]:
        """Pull the MessageSent message bytes + keccak hash from a burn receipt."""
        receipt = self.w3.eth.get_transaction_receipt(burn_tx)
        transmitter = self.w3.eth.contract(
            address=self.message_transmitter, abi=MESSAGE_TRANSMITTER_ABI
        )
        events = transmitter.events.MessageSent().process_receipt(receipt, errors=DISCARD)
        if not events:
            raise RuntimeError(
                f"No MessageSent event in burn tx {burn_tx}; cannot fetch attestation"
            )
        message_bytes = events[0]["args"]["message"]
        message_hash = Web3.keccak(message_bytes).hex()
        message_hex = "0x" + message_bytes.hex()
        if not message_hash.startswith("0x"):
            message_hash = "0x" + message_hash
        return message_hex, message_hash

    # ── Step 2: fetch attestation (off-chain) ────────────────────────────────

    def get_attestation(
        self,
        message_hash: str,
        timeout: int = 1200,
        poll_interval: float = 5.0,
        api_base: str = ATTESTATION_API,
    ) -> str:
        """Poll Circle's Iris service until the attestation is ``complete``.

        Returns the attestation hex string suitable for ``receiveMessage``.
        Raises ``TimeoutError`` if not ready within ``timeout`` seconds.
        """
        url = f"{api_base}/attestations/{message_hash}"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = httpx.get(url, timeout=30)
            except httpx.HTTPError:
                time.sleep(poll_interval)
                continue
            if resp.status_code == 200:
                body = resp.json()
                if body.get("status") == "complete" and body.get("attestation"):
                    return body["attestation"]
            time.sleep(poll_interval)
        raise TimeoutError(
            f"Attestation for {message_hash} not ready within {timeout}s"
        )

    # ── Step 3: mint on destination chain ────────────────────────────────────

    @staticmethod
    def mint(
        dest_chain_id: int,
        message: str,
        attestation: str,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit the attested message to the destination MessageTransmitter."""
        if dest_chain_id not in MESSAGE_TRANSMITTER:
            raise ValueError(f"No MessageTransmitter for chain {dest_chain_id}")
        transmitter_addr = Web3.to_checksum_address(MESSAGE_TRANSMITTER[dest_chain_id])
        w3 = get_w3(dest_chain_id)
        contract = w3.eth.contract(address=transmitter_addr, abi=MESSAGE_TRANSMITTER_ABI)

        msg_bytes = bytes.fromhex(message.removeprefix("0x"))
        att_bytes = bytes.fromhex(attestation.removeprefix("0x"))
        data = contract.encode_abi("receiveMessage", [msg_bytes, att_bytes])

        result = build_and_send_tx(
            chain_id=dest_chain_id,
            to=transmitter_addr,
            data=data,
            private_key=private_key,
        )
        return {"mint_tx": result["tx_hash"], "status": result.get("status")}

    # ── Orchestrated, resumable transfer ─────────────────────────────────────

    def transfer(
        self,
        amount: int,
        dest_chain_id: int,
        mint_recipient: Optional[str] = None,
        private_key: Optional[str] = None,
        run_id: Optional[str] = None,
        attestation_timeout: int = 1200,
    ) -> Dict[str, Any]:
        """Full burn → attest → mint flow, resumable via the state machine.

        Re-running with the same ``run_id`` after a crash resumes from the last
        checkpoint: if the burn already happened it skips straight to
        attestation + mint using the persisted message, never re-burning.
        """
        run_id = _resolve_run_id(run_id)
        # Make sure burn/mint audit lines correlate under one run_id.
        os.environ.setdefault("AUDIT_RUN_ID", run_id)

        chain_name = self.config.name.lower()
        human_amount = str(Decimal(amount) / Decimal(10**USDC_DECIMALS))

        action = state_machine.next_action(run_id)
        if action is None:
            raise RuntimeError(f"run {run_id} is in terminal state — cannot proceed")

        # ── PREFLIGHT + policy gate ──
        if action == state_machine.STATE_PREFLIGHT:
            pol = _policy.load_policy()
            recipient = mint_recipient or get_address(private_key)
            result = _policy.check(pol, {
                "amount": human_amount,
                "chain": chain_name,
                "receiver": recipient,
            })
            if not result.allowed:
                state_machine.transition(
                    run_id, state_machine.STATE_FAILED,
                    payload={"policy_violations": result.to_dict()["violations"]},
                )
                _audit.log_event(
                    event=_audit.EVENT_ERROR, chain=chain_name, wallet=recipient,
                    run_id=run_id, error_code="policy_rejected",
                    details={"violations": result.to_dict()["violations"]},
                )
                raise RuntimeError(
                    "Policy rejected: " + "; ".join(v.message for v in result.violations)
                )
            state_machine.transition(
                run_id, state_machine.STATE_PREFLIGHT,
                payload={"src": self.chain_id, "dest": dest_chain_id, "amount": amount},
            )

        # ── burn (skip if already broadcast) ──
        action = state_machine.next_action(run_id)
        if action in (state_machine.STATE_SIGNED,):
            state_machine.transition(run_id, state_machine.STATE_SIGNED)
            burn = self.burn(amount, dest_chain_id, mint_recipient, private_key)
            state_machine.transition(
                run_id, state_machine.STATE_BROADCAST,
                payload={
                    "burn_tx": burn["burn_tx"],
                    "message": burn["message"],
                    "message_hash": burn["message_hash"],
                    "dest": dest_chain_id,
                },
            )
        # Recover persisted burn data (covers both fresh + resumed runs).
        saved = state_machine.load_state(run_id) or {}
        payload = saved.get("payload", {})
        message = payload.get("message")
        message_hash = payload.get("message_hash")
        burn_tx = payload.get("burn_tx")
        if not message or not message_hash:
            raise RuntimeError(
                f"run {run_id}: missing burn message in state — cannot continue"
            )

        # ── attestation + mint ──
        attestation = self.get_attestation(message_hash, timeout=attestation_timeout)
        mint = self.mint(dest_chain_id, message, attestation, private_key)
        state_machine.transition(
            run_id, state_machine.STATE_CONFIRMED, payload={"mint_tx": mint["mint_tx"]}
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "src_chain_id": self.chain_id,
            "dest_chain_id": dest_chain_id,
            "amount": amount,
            "burn_tx": burn_tx,
            "mint_tx": mint["mint_tx"],
            "message_hash": message_hash,
        }
