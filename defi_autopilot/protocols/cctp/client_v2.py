"""Circle CCTP V2 client — Fast & Standard cross-chain USDC transfers.

CCTP V2 is *not* backward compatible with V1: separate contracts, separate API
endpoints, and a new transfer-speed dimension.  This module lives alongside the
V1 client (``client.py``) without conflict — different contract addresses,
different ABIs, a distinct ``CCTPv2Client`` class, and ``cctpv2-`` run-id
prefixes keep the two completely isolated.

What V2 adds over V1:

* **Fast Transfer** (``minFinalityThreshold <= 1000``): attestation in seconds
  instead of minutes, for a small variable fee (``maxFee``, in USDC units).
  **Standard Transfer** (``>= 2000``) waits for hard finality, usually fee-free.
* **Single-call attestation**: ``GET /v2/messages/{srcDomain}?transactionHash=``
  returns the message + attestation together, so we no longer parse the
  ``MessageSent`` event off the burn receipt.
* **destinationCaller / hooks** (not used here; left at the permissive default).

Flow (same resumable three-step shape as V1):

    1. burn   — TokenMessengerV2.depositForBurn(amount, dstDomain, recipient,
                USDC, destinationCaller=0, maxFee, minFinalityThreshold)
    2. attest — GET /v2/messages/{srcDomain}?transactionHash=<burnTx>
    3. mint   — MessageTransmitterV2.receiveMessage(message, attestation)

Reference: https://developers.circle.com/cctp (V2 interface)
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx
from web3 import Web3

from defi_autopilot import audit as _audit
from defi_autopilot import policy as _policy
from defi_autopilot import state_machine
from defi_autopilot.core.rpc import get_chain_config, get_w3
from defi_autopilot.core.signer import get_address
from defi_autopilot.core.tx import approve_token, build_and_send_tx, check_allowance

# Reuse the version-agnostic data from the V1 module: CCTP domain IDs and USDC
# token addresses are identical across V1/V2 for a given chain.
from .client import (
    CCTP_DOMAINS,
    USDC_ADDRESSES,
    USDC_DECIMALS,
    address_to_bytes32,
)

_log = logging.getLogger(__name__)

# One USDC cent (0.01 USDC) expressed in USDC base units (6 decimals).
_CENTS_TO_SUBUNITS = 10_000

# Buffer above the minimum fee to absorb short-term fluctuations (20%).
_FEE_BUFFER_NUMERATOR = 120
_FEE_BUFFER_DENOMINATOR = 100


# ── V2 contracts (CREATE2 — same address on every supported mainnet) ─────────
# Source: https://developers.circle.com/cctp/references/contract-addresses
TOKEN_MESSENGER_V2_ADDRESS = "0x28b5a0e9C621a5BadaA536219b3a228C8168cf5d"
MESSAGE_TRANSMITTER_V2_ADDRESS = "0x81D40F21F12A8F0E3252Bccb954D722d4c464B64"

# Restrict V2 to the chains this repo already has RPC presets for.
TOKEN_MESSENGER_V2: Dict[int, str] = {
    chain_id: TOKEN_MESSENGER_V2_ADDRESS for chain_id in CCTP_DOMAINS
}
MESSAGE_TRANSMITTER_V2: Dict[int, str] = {
    chain_id: MESSAGE_TRANSMITTER_V2_ADDRESS for chain_id in CCTP_DOMAINS
}

ATTESTATION_API_V2 = "https://iris-api.circle.com"

# Finality thresholds — the V2 transfer-speed selector.
FINALITY_FAST = 1000
FINALITY_STANDARD = 2000

# bytes32(0) destinationCaller → any address may call receiveMessage.
_ANY_CALLER = bytes(32)

TOKEN_MESSENGER_V2_ABI = [
    {
        "inputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "destinationDomain", "type": "uint32"},
            {"name": "mintRecipient", "type": "bytes32"},
            {"name": "burnToken", "type": "address"},
            {"name": "destinationCaller", "type": "bytes32"},
            {"name": "maxFee", "type": "uint256"},
            {"name": "minFinalityThreshold", "type": "uint32"},
        ],
        "name": "depositForBurn",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

MESSAGE_TRANSMITTER_V2_ABI = [
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
]


def _hex0x(value: str) -> str:
    return value if value.startswith("0x") else "0x" + value


def _resolve_run_id(explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    for name in ("STAGEFORGE_RUN_ID", "AUDIT_RUN_ID", "RUN_ID"):
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return f"cctpv2-{uuid.uuid4().hex[:12]}"


class CCTPv2Client:
    """Circle CCTP V2 client bound to a source chain."""

    def __init__(self, chain_id: int):
        if chain_id not in CCTP_DOMAINS:
            raise ValueError(
                f"CCTP V2 not supported on chain {chain_id}. "
                f"Supported: {sorted(CCTP_DOMAINS)}"
            )
        self.chain_id = chain_id
        self.domain = CCTP_DOMAINS[chain_id]
        self.config = get_chain_config(chain_id)
        self.w3 = get_w3(chain_id)
        self.usdc = Web3.to_checksum_address(USDC_ADDRESSES[chain_id])
        self.token_messenger = Web3.to_checksum_address(TOKEN_MESSENGER_V2[chain_id])
        self.message_transmitter = Web3.to_checksum_address(MESSAGE_TRANSMITTER_V2[chain_id])

    # ── Fees ─────────────────────────────────────────────────────────────────

    def get_fees(
        self,
        dest_chain_id: int,
        api_base: str = ATTESTATION_API_V2,
    ) -> Dict[int, int]:
        """Return ``{finalityThreshold: minimumFee}`` for src→dest.

        ``minimumFee`` is expressed in USDC cents (1 cent = 0.01 USDC).
        Multiply by 10_000 to convert to USDC base units (6 decimals).
        """
        dest_domain = CCTP_DOMAINS[dest_chain_id]
        url = f"{api_base}/v2/burn/USDC/fees/{self.domain}/{dest_domain}"
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        out: Dict[int, int] = {}
        for row in resp.json():
            threshold = int(row.get("finalityThreshold", 0))
            out[threshold] = int(row.get("minimumFee", 0))
        return out

    def _resolve_max_fee(
        self,
        dest_chain_id: int,
        fast: bool,
        explicit_max_fee: Optional[int],
    ) -> int:
        """Compute the maxFee (in USDC base units) to pass to depositForBurn.

        Follows the official conversion:
        ``feeSubunits = minimumFee_cents × 10_000``
        plus a 20% buffer to handle fee fluctuations.
        """
        if explicit_max_fee is not None:
            return explicit_max_fee
        if not fast:
            return 0
        try:
            fees = self.get_fees(dest_chain_id)
        except httpx.HTTPError:
            raise RuntimeError(
                "Could not fetch CCTP V2 fees; pass an explicit max_fee for Fast Transfer"
            )
        cents = fees.get(FINALITY_FAST, 0)
        # cents → USDC base units (6 decimals): 1 cent = 10_000 subunits.
        fee_subunits = cents * _CENTS_TO_SUBUNITS
        # Add 20% buffer per Circle recommendation.
        return (fee_subunits * _FEE_BUFFER_NUMERATOR) // _FEE_BUFFER_DENOMINATOR

    # ── Step 1: burn ─────────────────────────────────────────────────────────

    def burn(
        self,
        amount: int,
        dest_chain_id: int,
        max_fee: int,
        mint_recipient: Optional[str] = None,
        fast: bool = True,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Burn USDC on the source chain via TokenMessengerV2.depositForBurn."""
        if dest_chain_id not in CCTP_DOMAINS:
            raise ValueError(f"CCTP V2 destination chain {dest_chain_id} not supported")
        if dest_chain_id == self.chain_id:
            raise ValueError("source and destination chains must differ")

        signer_addr = get_address(private_key)
        recipient = mint_recipient or signer_addr
        dest_domain = CCTP_DOMAINS[dest_chain_id]
        finality = FINALITY_FAST if fast else FINALITY_STANDARD

        allowance = check_allowance(self.chain_id, self.usdc, signer_addr, self.token_messenger)
        if allowance < amount:
            approve_token(self.chain_id, self.usdc, self.token_messenger, 2**256 - 1, private_key)

        contract = self.w3.eth.contract(address=self.token_messenger, abi=TOKEN_MESSENGER_V2_ABI)
        data = contract.encode_abi(
            "depositForBurn",
            [
                amount,
                dest_domain,
                address_to_bytes32(recipient),
                self.usdc,
                _ANY_CALLER,
                max_fee,
                finality,
            ],
        )
        result = build_and_send_tx(
            chain_id=self.chain_id,
            to=self.token_messenger,
            data=data,
            private_key=private_key,
        )
        return {
            "burn_tx": result["tx_hash"],
            "status": result.get("status"),
            "src_chain_id": self.chain_id,
            "dest_chain_id": dest_chain_id,
            "amount": amount,
            "max_fee": max_fee,
            "fast": fast,
            "mint_recipient": recipient,
        }

    # ── Step 2: attestation (single call, no event parsing) ──────────────────

    def get_attestation(
        self,
        burn_tx: str,
        timeout: int = 300,
        poll_interval: float = 3.0,
        api_base: str = ATTESTATION_API_V2,
    ) -> Dict[str, str]:
        """Poll ``/v2/messages`` until the message is attested.

        Returns ``{"message": "0x..", "attestation": "0x.."}``.  Raises
        ``TimeoutError`` if not ready within ``timeout`` seconds.
        """
        url = f"{api_base}/v2/messages/{self.domain}"
        params = {"transactionHash": _hex0x(burn_tx)}
        deadline = time.time() + timeout
        last_status: Optional[str] = None
        while time.time() < deadline:
            try:
                resp = httpx.get(url, params=params, timeout=30)
            except httpx.HTTPError as exc:
                _log.warning("CCTP V2 attestation poll error (%s); retrying", exc)
                time.sleep(poll_interval)
                continue
            if resp.status_code == 429:
                _log.warning("CCTP attestation rate-limited (429); backing off")
                time.sleep(max(poll_interval, 5.0))
                continue
            # 404 = burn not observed yet; keep polling.
            if resp.status_code == 404:
                if last_status != "not_found":
                    _log.info("CCTP V2 burn %s not yet observed", burn_tx)
                    last_status = "not_found"
                time.sleep(poll_interval)
                continue
            if resp.status_code == 200:
                messages = resp.json().get("messages") or []
                if messages:
                    msg = messages[0]
                    status = msg.get("status")
                    if status != last_status:
                        _log.info(
                            "CCTP V2 attestation status=%s for burn %s", status, burn_tx
                        )
                        last_status = status
                    if status == "complete" and msg.get("attestation") not in (None, "PENDING"):
                        return {
                            "message": msg["message"],
                            "attestation": msg["attestation"],
                        }
            time.sleep(poll_interval)
        raise TimeoutError(
            f"CCTP V2 attestation for {burn_tx} not ready within {timeout}s "
            f"(last status: {last_status})"
        )

    # ── Step 3: mint ─────────────────────────────────────────────────────────

    @staticmethod
    def mint(
        dest_chain_id: int,
        message: str,
        attestation: str,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit the attested message to the destination MessageTransmitterV2."""
        if dest_chain_id not in MESSAGE_TRANSMITTER_V2:
            raise ValueError(f"No MessageTransmitterV2 for chain {dest_chain_id}")
        transmitter_addr = Web3.to_checksum_address(MESSAGE_TRANSMITTER_V2[dest_chain_id])
        w3 = get_w3(dest_chain_id)
        contract = w3.eth.contract(address=transmitter_addr, abi=MESSAGE_TRANSMITTER_V2_ABI)

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
        fast: bool = True,
        max_fee: Optional[int] = None,
        private_key: Optional[str] = None,
        run_id: Optional[str] = None,
        attestation_timeout: int = 300,
    ) -> Dict[str, Any]:
        """Full burn → attest → mint flow, resumable via the state machine.

        Re-running with the same ``run_id`` after a crash resumes from the last
        checkpoint; a burned-but-not-minted transfer continues at attest/mint
        without re-burning, and a finished transfer returns idempotently.
        """
        run_id = _resolve_run_id(run_id)
        os.environ.setdefault("AUDIT_RUN_ID", run_id)

        chain_name = self.config.name.lower()
        human_amount = str(Decimal(amount) / Decimal(10**USDC_DECIMALS))

        existing = state_machine.load_state(run_id)
        if existing and existing.get("current_state") == state_machine.STATE_CONFIRMED:
            p = existing.get("payload", {})
            return {
                "run_id": run_id,
                "status": "already_completed",
                "version": "v2",
                "src_chain_id": self.chain_id,
                "dest_chain_id": dest_chain_id,
                "amount": amount,
                "burn_tx": p.get("burn_tx"),
                "mint_tx": p.get("mint_tx"),
            }

        action = state_machine.next_action(run_id)
        if action is None:
            raise RuntimeError(
                f"run {run_id} is in a terminal state (failed/cancelled) — cannot proceed"
            )

        recipient = mint_recipient or get_address(private_key)
        if action == state_machine.STATE_PREFLIGHT:
            pol = _policy.load_policy()
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
            if result.warnings:
                _audit.log_event(
                    event=_audit.EVENT_PREFLIGHT, chain=chain_name, wallet=recipient,
                    run_id=run_id,
                    details={"stage": "policy", "warnings": result.to_dict()["warnings"]},
                )
            state_machine.transition(
                run_id, state_machine.STATE_PREFLIGHT,
                payload={"src": self.chain_id, "dest": dest_chain_id, "amount": amount,
                         "version": "v2", "fast": fast},
            )

        # ── burn (skip if a burn_tx is already checkpointed) ──
        saved = state_machine.load_state(run_id) or {}
        payload = saved.get("payload", {})
        if not payload.get("burn_tx"):
            resolved_fee = self._resolve_max_fee(dest_chain_id, fast, max_fee)
            state_machine.transition(run_id, state_machine.STATE_SIGNED)
            burn = self.burn(
                amount, dest_chain_id, resolved_fee, mint_recipient, fast, private_key
            )
            state_machine.transition(
                run_id, state_machine.STATE_BROADCAST,
                payload={"burn_tx": burn["burn_tx"], "dest": dest_chain_id,
                         "max_fee": resolved_fee},
            )
            saved = state_machine.load_state(run_id) or {}
            payload = saved.get("payload", {})

        burn_tx = payload.get("burn_tx")
        if not burn_tx:
            raise RuntimeError(f"run {run_id}: missing burn_tx in state — cannot continue")

        # ── attestation (single /v2/messages call) + mint ──
        att = self.get_attestation(burn_tx, timeout=attestation_timeout)
        mint = self.mint(dest_chain_id, att["message"], att["attestation"], private_key)
        state_machine.transition(
            run_id, state_machine.STATE_CONFIRMED, payload={"mint_tx": mint["mint_tx"]}
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "version": "v2",
            "fast": payload.get("fast", fast),
            "src_chain_id": self.chain_id,
            "dest_chain_id": dest_chain_id,
            "amount": amount,
            "max_fee": payload.get("max_fee"),
            "burn_tx": burn_tx,
            "mint_tx": mint["mint_tx"],
        }
