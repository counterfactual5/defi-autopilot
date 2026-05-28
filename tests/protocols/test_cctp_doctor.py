"""Tests for the CCTP preflight doctor."""

from __future__ import annotations

from unittest import mock

from defi_autopilot.protocols.cctp import doctor as doc


def _checks_by_name(report: dict) -> dict:
    return {c["name"]: c for c in report["checks"]}


class TestRoute:
    def test_unsupported_destination_short_circuits(self):
        report = doc.run_doctor(8453, 999999, 1_000_000, "0x" + "00" * 19 + "01")
        assert report["ok"] is False
        assert _checks_by_name(report)["route_supported"]["ok"] is False

    def test_same_chain_rejected(self):
        # src == dest is not a valid CCTP route.
        with mock.patch.object(doc, "get_w3") as mock_w3:
            mock_w3.return_value.eth.chain_id = 8453
            with mock.patch.object(doc, "usdc_balance", return_value=10**9):
                with mock.patch.object(doc, "check_allowance", return_value=10**9):
                    report = doc.run_doctor(8453, 8453, 1_000_000, "0x" + "00" * 19 + "01")
        assert _checks_by_name(report)["route_supported"]["ok"] is False


class TestHealthyAndUnhealthy:
    _WALLET = "0x000000000000000000000000000000000000bEEF"

    def test_all_pass(self):
        with mock.patch.object(doc, "get_w3") as mock_w3:
            mock_w3.return_value.eth.chain_id = 8453
            with mock.patch.object(doc, "usdc_balance", return_value=5 * 10**6):
                with mock.patch.object(doc, "check_allowance", return_value=10 * 10**6):
                    report = doc.run_doctor(8453, 42161, 1_000_000, self._WALLET)
        assert report["ok"] is True
        assert report["version"] == "v1"
        names = _checks_by_name(report)
        assert names["rpc_chain_id"]["ok"]
        assert names["usdc_balance"]["ok"]
        assert names["usdc_allowance"]["ok"]

    def test_insufficient_balance_fails(self):
        with mock.patch.object(doc, "get_w3") as mock_w3:
            mock_w3.return_value.eth.chain_id = 8453
            with mock.patch.object(doc, "usdc_balance", return_value=100):
                with mock.patch.object(doc, "check_allowance", return_value=10**9):
                    report = doc.run_doctor(8453, 42161, 1_000_000, self._WALLET)
        assert report["ok"] is False
        assert _checks_by_name(report)["usdc_balance"]["ok"] is False

    def test_allowance_shortfall_fails(self):
        with mock.patch.object(doc, "get_w3") as mock_w3:
            mock_w3.return_value.eth.chain_id = 8453
            with mock.patch.object(doc, "usdc_balance", return_value=10**9):
                with mock.patch.object(doc, "check_allowance", return_value=0):
                    report = doc.run_doctor(8453, 42161, 1_000_000, self._WALLET)
        assert report["ok"] is False
        assert _checks_by_name(report)["usdc_allowance"]["ok"] is False

    def test_chain_id_mismatch_fails(self):
        with mock.patch.object(doc, "get_w3") as mock_w3:
            mock_w3.return_value.eth.chain_id = 1  # wrong network for src=8453
            with mock.patch.object(doc, "usdc_balance", return_value=10**9):
                with mock.patch.object(doc, "check_allowance", return_value=10**9):
                    report = doc.run_doctor(8453, 42161, 1_000_000, self._WALLET)
        assert _checks_by_name(report)["rpc_chain_id"]["ok"] is False


class TestV2FeeCheck:
    _WALLET = "0x000000000000000000000000000000000000bEEF"

    def test_v2_fast_includes_fee_quote(self):
        with mock.patch.object(doc, "get_w3") as mock_w3:
            mock_w3.return_value.eth.chain_id = 8453
            with mock.patch.object(doc, "usdc_balance", return_value=10**9):
                with mock.patch.object(doc, "check_allowance", return_value=10**9):
                    with mock.patch.object(
                        doc.CCTPv2Client, "get_fees", return_value={1000: 1, 2000: 0}
                    ):
                        report = doc.run_doctor(
                            8453, 42161, 1_000_000, self._WALLET, v2=True, fast=True
                        )
        assert report["version"] == "v2"
        assert _checks_by_name(report)["v2_fee_quote"]["ok"] is True
