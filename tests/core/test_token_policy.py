"""Tests for the protocol-layer ERC-20 notional gate (enforce_token_policy).

The broadcast chokepoint can only see native value; this gate lets protocol
clients enforce ``max_amount`` against an ERC-20 notional. Decimals lookup is
mocked so no network is needed.
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest import mock

import pytest

from defi_autopilot.core import tx as tx_mod


def _write_policy(tmpdir: str, section: dict) -> str:
    path = os.path.join(tmpdir, "policy.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"defi-autopilot": section}, fh)
    return path


# A 6-decimal token (USDC-like) on Base.
_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


class TestEnforceTokenPolicy:
    def test_rejects_over_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = _write_policy(tmp, {"max_amount": 100})
            env = {"POLICY_FILE": policy_path, "AUDIT_LOG_PATH": os.path.join(tmp, "a.jsonl")}
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(tx_mod, "get_token_decimals", return_value=6):
                    # 1000 USDC (1000 * 10**6) exceeds cap of 100.
                    with pytest.raises(RuntimeError, match="Policy rejected"):
                        tx_mod.enforce_token_policy(8453, _USDC, 1000 * 10**6)

    def test_allows_under_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = _write_policy(tmp, {"max_amount": 100})
            env = {"POLICY_FILE": policy_path, "AUDIT_LOG_PATH": os.path.join(tmp, "a.jsonl")}
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(tx_mod, "get_token_decimals", return_value=6):
                    # 50 USDC is within cap; should not raise.
                    tx_mod.enforce_token_policy(8453, _USDC, 50 * 10**6)

    def test_skips_zero_and_max_sentinel(self):
        # No decimals lookup / policy load should even be attempted for these.
        with mock.patch.object(tx_mod, "get_token_decimals", side_effect=AssertionError("no lookup")):
            tx_mod.enforce_token_policy(8453, _USDC, 0)
            tx_mod.enforce_token_policy(8453, _USDC, 2**256 - 1)  # withdraw/repay-all

    def test_decimals_conversion_uses_token_decimals(self):
        # An 18-decimal token: 2 tokens = 2 * 10**18 base units, cap = 1 → reject.
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = _write_policy(tmp, {"max_amount": 1})
            env = {"POLICY_FILE": policy_path, "AUDIT_LOG_PATH": os.path.join(tmp, "a.jsonl")}
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(tx_mod, "get_token_decimals", return_value=18):
                    with pytest.raises(RuntimeError, match="Policy rejected"):
                        tx_mod.enforce_token_policy(8453, _USDC, 2 * 10**18)
                    # 0.5 token is under the cap of 1.
                    tx_mod.enforce_token_policy(8453, _USDC, 5 * 10**17)


class TestGetTokenDecimalsCache:
    def test_caches_per_token(self):
        tx_mod._decimals_cache.clear()
        fake_w3 = mock.MagicMock()
        fake_w3.eth.contract.return_value.functions.decimals.return_value.call.return_value = 6
        with mock.patch.object(tx_mod, "get_w3", return_value=fake_w3) as mock_get_w3:
            d1 = tx_mod.get_token_decimals(8453, _USDC)
            d2 = tx_mod.get_token_decimals(8453, _USDC)
        assert d1 == 6 and d2 == 6
        # Second call served from cache → get_w3 called only once.
        mock_get_w3.assert_called_once()
