"""Preflight health checks for a CCTP transfer.

Answers "will this CCTP transfer actually go through?" *before* burning USDC:

* route supported (both chains have a CCTP domain, and they differ)
* RPC reachable and reports the expected chain id
* wallet holds enough USDC to cover the amount
* USDC is approved to the right TokenMessenger (V1 or V2)
* (V2 Fast only) Circle's fee endpoint is reachable

Returns a structured report so both the CLI and other tooling can consume it.
No transactions are sent.
"""

from __future__ import annotations

from typing import Any, Dict, List

from web3 import Web3

from defi_autopilot.core.rpc import get_w3
from defi_autopilot.core.tx import check_allowance

from .client import CCTP_DOMAINS, TOKEN_MESSENGER, USDC_ADDRESSES
from .client_v2 import TOKEN_MESSENGER_V2, CCTPv2Client

_ERC20_BALANCE_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    }
]


def usdc_balance(chain_id: int, wallet: str) -> int:
    """Return the wallet's USDC balance (base units) on *chain_id*."""
    w3 = get_w3(chain_id)
    token = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_ADDRESSES[chain_id]),
        abi=_ERC20_BALANCE_ABI,
    )
    return int(token.functions.balanceOf(Web3.to_checksum_address(wallet)).call())


def run_doctor(
    src_chain: int,
    dest_chain: int,
    amount: int,
    wallet: str,
    *,
    v2: bool = False,
    fast: bool = True,
) -> Dict[str, Any]:
    """Run all CCTP preflight checks and return a structured report.

    ``amount`` is in USDC base units (6 decimals). The report has shape
    ``{"ok": bool, "version": "v1"|"v2", "checks": [{"name", "ok", "detail"}]}``.
    """
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    # ── route ──
    src_supported = src_chain in CCTP_DOMAINS
    dst_supported = dest_chain in CCTP_DOMAINS
    route_ok = src_supported and dst_supported and src_chain != dest_chain
    add(
        "route_supported",
        route_ok,
        f"src={src_chain}({'ok' if src_supported else 'unsupported'}) "
        f"dest={dest_chain}({'ok' if dst_supported else 'unsupported'})",
    )
    if not (src_supported and dst_supported):
        return {"ok": False, "version": "v2" if v2 else "v1", "checks": checks}

    # ── RPC / chain id ──
    try:
        w3 = get_w3(src_chain)
        reported = int(w3.eth.chain_id)
        add("rpc_chain_id", reported == src_chain, f"reported {reported}, expected {src_chain}")
    except Exception as exc:  # noqa: BLE001 - surface any RPC failure as a check
        add("rpc_chain_id", False, f"RPC error: {exc}")

    # ── USDC balance ──
    try:
        bal = usdc_balance(src_chain, wallet)
        add("usdc_balance", bal >= amount, f"balance {bal} vs required {amount}")
    except Exception as exc:  # noqa: BLE001
        add("usdc_balance", False, f"balance query failed: {exc}")

    # ── USDC allowance to the right messenger ──
    messenger = (TOKEN_MESSENGER_V2 if v2 else TOKEN_MESSENGER)[src_chain]
    try:
        allowance = check_allowance(src_chain, USDC_ADDRESSES[src_chain], wallet, messenger)
        needs_approve = allowance < amount
        add(
            "usdc_allowance",
            not needs_approve,
            f"allowance {allowance} vs required {amount}"
            + (" (approve needed before transfer)" if needs_approve else ""),
        )
    except Exception as exc:  # noqa: BLE001
        add("usdc_allowance", False, f"allowance query failed: {exc}")

    # ── V2 Fast fee quote ──
    if v2 and fast:
        try:
            fees = CCTPv2Client(src_chain).get_fees(dest_chain)
            add("v2_fee_quote", True, f"fees (cents by finality): {fees}")
        except Exception as exc:  # noqa: BLE001
            add("v2_fee_quote", False, f"fee quote failed: {exc}")

    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "version": "v2" if v2 else "v1", "checks": checks}
