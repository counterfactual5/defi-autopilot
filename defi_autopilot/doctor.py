"""Top-level preflight health checks for any defi-autopilot operation.

Answers "is this chain/wallet ready to transact?" *before* a supply / borrow /
swap spends gas. Mirrors the structured-report shape of the CCTP doctor
(``protocols/cctp/doctor.py``) so the CLI and other tooling consume both the
same way:

    {"ok": bool, "chain_id": int, "checks": [{"name", "ok", "detail"}]}

Checks performed:

* chain supported (has an RPC preset)
* RPC reachable and reports the expected chain id
* signer address resolvable (only when --require-signer / a key is present)
* native balance available for gas
* (optional) policy file loads and the chain/amount passes the gate

No transactions are sent.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from web3 import Web3

from defi_autopilot import policy as _policy
from defi_autopilot.core.chains import CHAIN_PRESETS
from defi_autopilot.core.rpc import get_chain_config, get_w3
from defi_autopilot.core.signer import get_address


def run_doctor(
    chain_id: int,
    *,
    wallet: Optional[str] = None,
    require_signer: bool = False,
    policy_check: bool = False,
    policy_file: Optional[str] = None,
    amount: Optional[str] = None,
) -> Dict[str, Any]:
    """Run preflight checks for *chain_id* and return a structured report.

    ``wallet`` defaults to the signer address (if a key is available).
    ``amount`` is a human-units string used only for the optional policy gate.
    """
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    # ── chain supported ──
    if chain_id not in CHAIN_PRESETS:
        add("chain_supported", False, f"chain {chain_id} has no preset; supported: {sorted(CHAIN_PRESETS)}")
        return {"ok": False, "chain_id": chain_id, "checks": checks}
    config = get_chain_config(chain_id)
    add("chain_supported", True, f"{config.name} (id={chain_id})")

    # ── RPC reachable + chain id ──
    try:
        w3 = get_w3(chain_id)
        reported = int(w3.eth.chain_id)
        add("rpc_chain_id", reported == chain_id, f"reported {reported}, expected {chain_id}")
    except Exception as exc:  # noqa: BLE001 - surface any RPC failure as a check
        add("rpc_chain_id", False, f"RPC error: {exc}")
        # Without RPC the remaining on-chain checks cannot run.
        return {"ok": all(c["ok"] for c in checks), "chain_id": chain_id, "checks": checks}

    # ── signer address ──
    resolved_wallet = wallet
    if resolved_wallet is None:
        try:
            resolved_wallet = get_address()
            add("signer", True, f"signer {resolved_wallet}")
        except Exception as exc:  # noqa: BLE001
            add("signer", not require_signer, f"no signer key available: {exc}")
    else:
        add("signer", True, f"wallet {resolved_wallet} (explicit)")

    # ── native balance for gas ──
    if resolved_wallet:
        try:
            wei = int(w3.eth.get_balance(Web3.to_checksum_address(resolved_wallet)))
            eth = Decimal(wei) / Decimal(10**18)
            add("native_balance", wei > 0, f"{eth} {config.native_token} for gas")
        except Exception as exc:  # noqa: BLE001
            add("native_balance", False, f"balance query failed: {exc}")

    # ── gas price (informational) ──
    try:
        gas_wei = int(w3.eth.gas_price)
        gwei = Decimal(gas_wei) / Decimal(10**9)
        add("gas_price", True, f"{gwei} gwei")
    except Exception as exc:  # noqa: BLE001
        add("gas_price", True, f"gas price unavailable: {exc}")

    # ── optional policy gate ──
    if policy_check:
        try:
            pol = _policy.load_policy(policy_file)
            ctx: Dict[str, Any] = {"chain": config.name.lower()}
            if resolved_wallet:
                ctx["receiver"] = resolved_wallet
            if amount is not None:
                ctx["amount"] = amount
            result = _policy.check(pol, ctx)
            detail = "allowed" if result.allowed else "; ".join(
                v.message for v in result.violations
            )
            if result.warnings:
                detail += " | warnings: " + "; ".join(w.message for w in result.warnings)
            add("policy", result.allowed, detail)
        except Exception as exc:  # noqa: BLE001
            add("policy", False, f"policy load/eval failed: {exc}")

    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "chain_id": chain_id, "checks": checks}
