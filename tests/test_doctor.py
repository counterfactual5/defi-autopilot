"""Tests for the top-level preflight doctor."""

from __future__ import annotations

import json
import os
import tempfile
from unittest import mock

from defi_autopilot import doctor as doc


def _checks(report: dict) -> dict:
    return {c["name"]: c for c in report["checks"]}


_WALLET = "0x000000000000000000000000000000000000bEEF"


class TestChainSupport:
    def test_unsupported_chain_short_circuits(self):
        report = doc.run_doctor(999999, wallet=_WALLET)
        assert report["ok"] is False
        names = _checks(report)
        assert names["chain_supported"]["ok"] is False
        # Short-circuits before any RPC check.
        assert "rpc_chain_id" not in names


class TestRpc:
    def test_rpc_error_stops_onchain_checks(self):
        with mock.patch.object(doc, "get_w3", side_effect=ConnectionError("boom")):
            report = doc.run_doctor(8453, wallet=_WALLET)
        names = _checks(report)
        assert names["rpc_chain_id"]["ok"] is False
        assert "native_balance" not in names

    def test_chain_id_mismatch_fails(self):
        w3 = mock.MagicMock()
        w3.eth.chain_id = 1  # wrong network for src=8453
        w3.eth.get_balance.return_value = 10**18
        w3.eth.gas_price = 10**9
        with mock.patch.object(doc, "get_w3", return_value=w3):
            report = doc.run_doctor(8453, wallet=_WALLET)
        assert _checks(report)["rpc_chain_id"]["ok"] is False


class TestSignerAndBalance:
    def _w3(self, *, balance: int = 10**18):
        w3 = mock.MagicMock()
        w3.eth.chain_id = 8453
        w3.eth.get_balance.return_value = balance
        w3.eth.gas_price = 10**9
        return w3

    def test_all_pass_with_explicit_wallet(self):
        with mock.patch.object(doc, "get_w3", return_value=self._w3()):
            report = doc.run_doctor(8453, wallet=_WALLET)
        assert report["ok"] is True
        names = _checks(report)
        assert names["signer"]["ok"]
        assert names["native_balance"]["ok"]
        assert names["gas_price"]["ok"]

    def test_zero_gas_balance_fails(self):
        with mock.patch.object(doc, "get_w3", return_value=self._w3(balance=0)):
            report = doc.run_doctor(8453, wallet=_WALLET)
        assert _checks(report)["native_balance"]["ok"] is False

    def test_missing_signer_optional_passes(self):
        with mock.patch.object(doc, "get_w3", return_value=self._w3()):
            with mock.patch.object(doc, "get_address", side_effect=ValueError("no key")):
                report = doc.run_doctor(8453, wallet=None, require_signer=False)
        # Without a wallet, signer check is a soft pass and balance is skipped.
        names = _checks(report)
        assert names["signer"]["ok"] is True
        assert "native_balance" not in names

    def test_missing_signer_required_fails(self):
        with mock.patch.object(doc, "get_w3", return_value=self._w3()):
            with mock.patch.object(doc, "get_address", side_effect=ValueError("no key")):
                report = doc.run_doctor(8453, wallet=None, require_signer=True)
        assert _checks(report)["signer"]["ok"] is False


class TestPolicyGate:
    def _w3(self):
        w3 = mock.MagicMock()
        w3.eth.chain_id = 8453
        w3.eth.get_balance.return_value = 10**18
        w3.eth.gas_price = 10**9
        return w3

    def test_policy_allows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "policy.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"defi-autopilot": {"allowed_chains": ["base"]}}, fh)
            with mock.patch.object(doc, "get_w3", return_value=self._w3()):
                report = doc.run_doctor(
                    8453, wallet=_WALLET, policy_check=True, policy_file=path
                )
        assert _checks(report)["policy"]["ok"] is True

    def test_policy_rejects_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "policy.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"defi-autopilot": {"allowed_chains": ["ethereum"]}}, fh)
            with mock.patch.object(doc, "get_w3", return_value=self._w3()):
                report = doc.run_doctor(
                    8453, wallet=_WALLET, policy_check=True, policy_file=path
                )
        assert report["ok"] is False
        assert _checks(report)["policy"]["ok"] is False

    def test_policy_amount_over_cap_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "policy.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"defi-autopilot": {"max_amount": 100}}, fh)
            with mock.patch.object(doc, "get_w3", return_value=self._w3()):
                report = doc.run_doctor(
                    8453, wallet=_WALLET, policy_check=True, policy_file=path, amount="1000"
                )
        assert _checks(report)["policy"]["ok"] is False
