"""Policy + audit integration tests for the broadcast chokepoint.

``build_and_send_tx`` is the single point every protocol client funnels through.
These tests verify the policy gate rejects bad transactions *before* any signing
or broadcasting, and that the happy path emits the expected audit events.
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest import mock

import pytest

from defi_autopilot.core import tx as tx_mod


def _write_policy(tmpdir: str, section: dict) -> str:
    data = {"defi-autopilot": section}
    path = os.path.join(tmpdir, "policy.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


class TestPolicyGateRejects:
    """Rejection happens before get_w3 / signing — no network needed."""

    def test_disallowed_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = _write_policy(tmp, {"allowed_chains": ["ethereum"]})
            with mock.patch.dict(os.environ, {"POLICY_FILE": policy_path}, clear=True):
                # chain 8453 (base) not in allow-list
                with pytest.raises(RuntimeError, match="Policy rejected"):
                    tx_mod.build_and_send_tx(
                        chain_id=8453,
                        to="0x0000000000000000000000000000000000000001",
                    )

    def test_blacklisted_destination(self):
        bad = "0x000000000000000000000000000000000000dEaD"
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = _write_policy(tmp, {"blacklist_addresses": [bad.lower()]})
            with mock.patch.dict(os.environ, {"POLICY_FILE": policy_path}, clear=True):
                with pytest.raises(RuntimeError, match="Policy rejected"):
                    tx_mod.build_and_send_tx(chain_id=8453, to=bad)

    def test_native_amount_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = _write_policy(tmp, {"max_amount": 1})
            with mock.patch.dict(os.environ, {"POLICY_FILE": policy_path}, clear=True):
                # 2 ETH native value exceeds cap of 1
                with pytest.raises(RuntimeError, match="Policy rejected"):
                    tx_mod.build_and_send_tx(
                        chain_id=8453,
                        to="0x0000000000000000000000000000000000000001",
                        value=2 * 10**18,
                    )

    def test_gate_runs_before_web3(self):
        """If the gate rejects, get_w3 must never be called."""
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = _write_policy(tmp, {"allowed_chains": ["ethereum"]})
            with mock.patch.dict(os.environ, {"POLICY_FILE": policy_path}, clear=True):
                with mock.patch.object(tx_mod, "get_w3") as mock_w3:
                    with pytest.raises(RuntimeError, match="Policy rejected"):
                        tx_mod.build_and_send_tx(
                            chain_id=8453,
                            to="0x0000000000000000000000000000000000000001",
                        )
                    mock_w3.assert_not_called()


class TestHappyPathAudit:
    """Permissive policy → tx proceeds, audit events emitted."""

    def test_sign_broadcast_confirm_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = _write_policy(tmp, {})  # no restrictions
            audit_path = os.path.join(tmp, "audit.jsonl")
            env = {"POLICY_FILE": policy_path, "AUDIT_LOG_PATH": audit_path,
                   "AUDIT_RUN_ID": "defi-test-1"}

            # Build a fake web3 client.
            w3 = mock.MagicMock()
            w3.eth.get_transaction_count.return_value = 7
            w3.eth.estimate_gas.return_value = 100000
            w3.eth.get_block.return_value = {"baseFeePerGas": 10**9}
            w3.eth.max_priority_fee = 10**9
            signed = mock.MagicMock()
            signed.raw_transaction = b"\x01\x02"
            w3.eth.account.sign_transaction.return_value = signed
            w3.eth.send_raw_transaction.return_value = bytes.fromhex("ab" * 32)
            w3.eth.get_transaction_receipt.return_value = {
                "status": 1, "blockNumber": 123, "gasUsed": 90000,
            }

            signer = mock.MagicMock()
            signer.address = "0x000000000000000000000000000000000000bEEF"
            signer.key = b"\x11" * 32

            with mock.patch.dict(os.environ, env, clear=True):
                with (
                    mock.patch.object(tx_mod, "get_w3", return_value=w3),
                    mock.patch.object(tx_mod, "get_signer", return_value=signer),
                ):
                    result = tx_mod.build_and_send_tx(
                        chain_id=8453,
                        to="0x0000000000000000000000000000000000000001",
                        value=0,
                    )

            assert result["status"] == 1
            w3.eth.send_raw_transaction.assert_called_once()

            with open(audit_path, encoding="utf-8") as fh:
                events = [json.loads(line)["event"] for line in fh if line.strip()]
            assert "sign" in events
            assert "broadcast" in events
            assert "confirm" in events
