"""defi-autopilot transaction broadcast module"""

import os
import time
from decimal import Decimal
from typing import Optional, Dict, Any
from web3 import Web3
from web3.types import TxReceipt, TxParams

from .rpc import get_w3
from .signer import get_signer
from .. import audit as _audit
from .. import policy as _policy

try:
    from .chains import CHAIN_PRESETS
except Exception:  # pragma: no cover - defensive
    CHAIN_PRESETS = {}


GAS_MULTIPLIER = 1.1  # Gas estimation markup: 10%


def _chain_name(chain_id: int) -> str:
    cfg = CHAIN_PRESETS.get(chain_id)
    return cfg.name.lower() if cfg else str(chain_id)


def _resolve_run_id() -> Optional[str]:
    for name in ("STAGEFORGE_RUN_ID", "AUDIT_RUN_ID", "RUN_ID"):
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return None


def _enforce_policy(chain_id: int, to: str, value: int, run_id: Optional[str]) -> None:
    """Stateless risk-control gate, applied to every broadcast.

    Enforces what is visible at the broadcast chokepoint: chain allow-list,
    blacklisted destination/spender, and native-value amount cap.  ERC-20
    notional caps are NOT enforced here (the amount lives inside calldata) —
    wire ``max_amount`` at the protocol-client layer if you need that.
    """
    chain_name = _chain_name(chain_id)
    pol = _policy.load_policy()
    ctx = {
        "chain": chain_name,
        "receiver": to,
        "spender": to,
        # Native value expressed in ether units (only meaningful for native sends).
        "amount": str(Decimal(value) / Decimal(10**18)) if value else "0",
    }
    result = _policy.check(pol, ctx)
    if not result.allowed:
        _audit.log_event(
            event=_audit.EVENT_ERROR,
            chain=chain_name,
            tx_hash=None,
            run_id=run_id,
            error_code="policy_rejected",
            details={"violations": result.to_dict()["violations"]},
        )
        raise RuntimeError(
            "Policy rejected: " + "; ".join(v.message for v in result.violations)
        )
    if result.warnings:
        _audit.log_event(
            event=_audit.EVENT_PREFLIGHT,
            chain=chain_name,
            run_id=run_id,
            details={"stage": "policy", "warnings": result.to_dict()["warnings"]},
        )


def build_and_send_tx(
    chain_id: int,
    to: str,
    data: bytes = b"",
    value: int = 0,
    gas_limit: Optional[int] = None,
    max_fee_per_gas: Optional[int] = None,
    max_priority_fee: Optional[int] = None,
    private_key: Optional[str] = None,
    wait_for_receipt: bool = True,
    timeout: int = 120,
) -> Dict[str, Any]:
    """
    Build, sign, send a transaction, and wait for receipt.

    Args:
        data: Transaction calldata as bytes. Hex strings (0x-prefixed) are
              automatically converted to bytes.
    """
    # Ensure data is bytes (accept hex strings too)
    if isinstance(data, str):
        data = bytes.fromhex(data.removeprefix("0x"))
    elif not isinstance(data, (bytes, bytearray)):
        data = b""

    run_id = _resolve_run_id()
    chain_name = _chain_name(chain_id)

    # ── policy gate (before any signing / broadcasting) ──
    _enforce_policy(chain_id, to, value, run_id)

    w3 = get_w3(chain_id)
    signer = get_signer(private_key)
    address = Web3.to_checksum_address(signer.address)

    # Get nonce
    nonce = w3.eth.get_transaction_count(address)

    # Estimate gas
    if gas_limit is None:
        try:
            estimated = w3.eth.estimate_gas({
                "from": address,
                "to": Web3.to_checksum_address(to),
                "data": data,
                "value": value,
            })
            gas_limit = int(estimated * GAS_MULTIPLIER)
        except Exception as e:
            raise RuntimeError(f"Gas estimation failed: {e}")

    # Get EIP-1559 fees
    if max_fee_per_gas is None:
        block = w3.eth.get_block("latest")
        base_fee = block.get("baseFeePerGas", w3.eth.gas_price)
        if max_priority_fee is None:
            max_priority_fee = w3.eth.max_priority_fee
        max_fee_per_gas = base_fee * 2 + max_priority_fee

    tx: TxParams = {
        "from": address,
        "to": Web3.to_checksum_address(to),
        "data": data,
        "value": value,
        "nonce": nonce,
        "gas": gas_limit,
        "maxFeePerGas": max_fee_per_gas,
        "maxPriorityFeePerGas": max_priority_fee,
        "chainId": chain_id,
    }

    # Sign
    _audit.log_event(
        event=_audit.EVENT_SIGN,
        chain=chain_name,
        wallet=address,
        run_id=run_id,
        details={"to": to, "value": str(value), "gasLimit": gas_limit, "nonce": nonce},
    )
    try:
        signed = w3.eth.account.sign_transaction(tx, signer.key)

        # Send
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    except Exception as exc:
        _audit.log_event(
            event=_audit.EVENT_ERROR,
            chain=chain_name,
            wallet=address,
            run_id=run_id,
            error_code="broadcast_failed",
            details={"to": to, "error": str(exc)},
        )
        raise

    tx_hash_hex = tx_hash.hex()
    _audit.log_event(
        event=_audit.EVENT_BROADCAST,
        chain=chain_name,
        wallet=address,
        tx_hash=tx_hash_hex,
        run_id=run_id,
        details={"to": to, "value": str(value)},
    )

    result = {
        "tx_hash": tx_hash_hex,
        "chain_id": chain_id,
        "from": address,
        "to": to,
    }

    if wait_for_receipt:
        try:
            receipt = wait_receipt(w3, tx_hash, timeout=timeout)
        except Exception as exc:
            _audit.log_event(
                event=_audit.EVENT_ERROR,
                chain=chain_name,
                wallet=address,
                tx_hash=tx_hash_hex,
                run_id=run_id,
                error_code="receipt_timeout",
                details={"error": str(exc)},
            )
            raise
        result["status"] = receipt.get("status")
        result["block_number"] = receipt.get("blockNumber")
        result["gas_used"] = receipt.get("gasUsed")
        _audit.log_event(
            event=_audit.EVENT_CONFIRM,
            chain=chain_name,
            wallet=address,
            tx_hash=tx_hash_hex,
            run_id=run_id,
            error_code=None if receipt.get("status") == 1 else "tx_reverted",
            details={"status": receipt.get("status"), "blockNumber": receipt.get("blockNumber")},
        )

    return result


def wait_receipt(
    w3: Web3, tx_hash: bytes, timeout: int = 120, poll_interval: float = 1.0
) -> TxReceipt:
    """Wait for transaction receipt"""
    start = time.time()
    while time.time() - start < timeout:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt is not None:
            return receipt
        time.sleep(poll_interval)
    raise TimeoutError(f"Transaction {tx_hash.hex()} not confirmed within {timeout}s")


def check_allowance(
    chain_id: int,
    token_address: str,
    owner: str,
    spender: str,
) -> int:
    """Query ERC20 allowance"""
    w3 = get_w3(chain_id)
    erc20_abi = [
        {
            "constant": True,
            "inputs": [
                {"name": "_owner", "type": "address"},
                {"name": "_spender", "type": "address"},
            ],
            "name": "allowance",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function",
        }
    ]
    token = w3.eth.contract(
        address=Web3.to_checksum_address(token_address), abi=erc20_abi
    )
    return token.functions.allowance(
        Web3.to_checksum_address(owner), Web3.to_checksum_address(spender)
    ).call()


def approve_token(
    chain_id: int,
    token_address: str,
    spender: str,
    amount: int,
    private_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Approve ERC20 token spending"""
    erc20_approve_abi = [
        {
            "constant": False,
            "inputs": [
                {"name": "_spender", "type": "address"},
                {"name": "_value", "type": "uint256"},
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function",
        }
    ]
    w3 = get_w3(chain_id)
    token = w3.eth.contract(
        address=Web3.to_checksum_address(token_address), abi=erc20_approve_abi
    )
    data = token.encode_abi("approve", [Web3.to_checksum_address(spender), amount])
    return build_and_send_tx(
        chain_id=chain_id,
        to=token_address,
        data=data,
        private_key=private_key,
    )
