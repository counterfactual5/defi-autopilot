"""Tests for the Circle CCTP V2 client.

Covers the V2-specific bits (Fast/Standard fee resolution, single-call
attestation, 7-arg depositForBurn) plus the shared resumable/anti-replay
orchestration. Network and signing are fully mocked.
"""

from __future__ import annotations

import json
import os
import tempfile
import types
from unittest import mock

import pytest

from defi_autopilot import state_machine
from defi_autopilot.protocols import cctp
from defi_autopilot.protocols.cctp import client_v2 as v2


# ── Static data / config ──────────────────────────────────────────────────────

class TestStaticData:
    def test_v2_addresses_are_create2_uniform(self):
        assert set(v2.TOKEN_MESSENGER_V2.values()) == {v2.TOKEN_MESSENGER_V2_ADDRESS}
        assert set(v2.MESSAGE_TRANSMITTER_V2.values()) == {v2.MESSAGE_TRANSMITTER_V2_ADDRESS}

    def test_v2_distinct_from_v1(self):
        assert v2.TOKEN_MESSENGER_V2_ADDRESS not in cctp.TOKEN_MESSENGER.values()
        assert v2.MESSAGE_TRANSMITTER_V2_ADDRESS not in cctp.MESSAGE_TRANSMITTER.values()

    def test_depositforburn_has_seven_params(self):
        fn = next(a for a in v2.TOKEN_MESSENGER_V2_ABI if a["name"] == "depositForBurn")
        names = [i["name"] for i in fn["inputs"]]
        assert names == [
            "amount", "destinationDomain", "mintRecipient", "burnToken",
            "destinationCaller", "maxFee", "minFinalityThreshold",
        ]

    def test_finality_constants(self):
        assert v2.FINALITY_FAST == 1000
        assert v2.FINALITY_STANDARD == 2000

    def test_unsupported_chain_raises(self):
        with pytest.raises(ValueError, match="CCTP V2 not supported"):
            v2.CCTPv2Client(999999)


# ── Helpers to build an instance without touching the network ─────────────────

def _fake_client(chain_id: int = 8453) -> v2.CCTPv2Client:
    c = object.__new__(v2.CCTPv2Client)
    c.chain_id = chain_id
    c.domain = cctp.CCTP_DOMAINS[chain_id]
    c.config = types.SimpleNamespace(name="base")
    c.w3 = mock.MagicMock()
    c.usdc = cctp.USDC_ADDRESSES[chain_id]
    c.token_messenger = v2.TOKEN_MESSENGER_V2[chain_id]
    c.message_transmitter = v2.MESSAGE_TRANSMITTER_V2[chain_id]
    return c


def _permissive_env(tmp: str) -> dict:
    policy_path = os.path.join(tmp, "policy.json")
    with open(policy_path, "w", encoding="utf-8") as fh:
        json.dump({"defi-autopilot": {}}, fh)
    return {
        "POLICY_FILE": policy_path,
        "STAGEFORGE_STATE_DIR": os.path.join(tmp, "states"),
        "AUDIT_LOG_PATH": os.path.join(tmp, "audit.jsonl"),
    }


# ── Fee resolution ────────────────────────────────────────────────────────────

class TestMaxFeeResolution:
    def test_standard_is_free(self):
        client = _fake_client()
        assert client._resolve_max_fee(42161, fast=False, explicit_max_fee=None) == 0

    def test_explicit_fee_wins(self):
        client = _fake_client()
        assert client._resolve_max_fee(42161, fast=True, explicit_max_fee=42) == 42

    def test_fast_fee_from_cents(self):
        client = _fake_client()
        # API returns minimumFee=1 (1 USDC cent = 0.01 USDC).
        # Expected: 1 cent * 10_000 subunits/cent * 1.2 buffer = 12_000.
        client.get_fees = mock.MagicMock(return_value={v2.FINALITY_FAST: 1, v2.FINALITY_STANDARD: 0})
        fee = client._resolve_max_fee(42161, fast=True, explicit_max_fee=None)
        assert fee == 12_000  # 1 * 10_000 * 120 // 100

    def test_fast_fee_zero_cents(self):
        client = _fake_client()
        client.get_fees = mock.MagicMock(return_value={v2.FINALITY_FAST: 0})
        fee = client._resolve_max_fee(42161, fast=True, explicit_max_fee=None)
        assert fee == 0


# ── Attestation (single /v2/messages call) ────────────────────────────────────

class TestAttestation:
    def test_returns_message_and_attestation_when_complete(self):
        client = _fake_client()
        resp = mock.MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "messages": [{"status": "complete", "message": "0xmsg", "attestation": "0xatt"}]
        }
        with mock.patch.object(v2.httpx, "get", return_value=resp) as mock_get:
            out = client.get_attestation("0xburn", timeout=5)
        assert out == {"message": "0xmsg", "attestation": "0xatt"}
        mock_get.assert_called()

    def test_pending_then_timeout(self):
        client = _fake_client()
        resp = mock.MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"messages": [{"status": "pending", "attestation": "PENDING"}]}
        with mock.patch.object(v2.httpx, "get", return_value=resp):
            with mock.patch.object(v2.time, "sleep"):
                with pytest.raises(TimeoutError):
                    client.get_attestation("0xburn", timeout=0.01, poll_interval=0)


# ── Orchestration: happy path, anti-replay, idempotency, policy ───────────────

class TestTransferHappyPath:
    def test_standard_flow_reaches_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = _permissive_env(tmp)
            client = _fake_client()
            client.burn = mock.MagicMock(return_value={"burn_tx": "0xburn", "status": 1})
            client.get_attestation = mock.MagicMock(
                return_value={"message": "0xmsg", "attestation": "0xatt"}
            )

            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(
                    v2.CCTPv2Client, "mint", return_value={"mint_tx": "0xmint", "status": 1}
                ) as mock_mint:
                    result = client.transfer(
                        amount=1_000_000,
                        dest_chain_id=42161,
                        mint_recipient="0x000000000000000000000000000000000000bEEF",
                        fast=False,
                        run_id="cctpv2-happy",
                    )

            assert result["status"] == "completed"
            assert result["version"] == "v2"
            assert result["burn_tx"] == "0xburn"
            assert result["mint_tx"] == "0xmint"
            client.burn.assert_called_once()
            mock_mint.assert_called_once()

            with mock.patch.dict(os.environ, env, clear=True):
                final = state_machine.load_state("cctpv2-happy")
            assert final["current_state"] == state_machine.STATE_CONFIRMED


class TestAntiReplayResume:
    def test_resume_after_burn_does_not_reburn(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = _permissive_env(tmp)
            run_id = "cctpv2-resume"
            with mock.patch.dict(os.environ, env, clear=True):
                state_machine.transition(run_id, state_machine.STATE_PREFLIGHT)
                state_machine.transition(run_id, state_machine.STATE_SIGNED)
                state_machine.transition(
                    run_id, state_machine.STATE_BROADCAST,
                    payload={"burn_tx": "0xpriorburn", "dest": 42161, "max_fee": 0},
                )

            client = _fake_client()
            client.burn = mock.MagicMock(side_effect=AssertionError("must not re-burn"))
            client.get_attestation = mock.MagicMock(
                return_value={"message": "0xmsg", "attestation": "0xatt"}
            )

            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(
                    v2.CCTPv2Client, "mint", return_value={"mint_tx": "0xmint2", "status": 1}
                ) as mock_mint:
                    result = client.transfer(
                        amount=1_000_000, dest_chain_id=42161,
                        mint_recipient="0x000000000000000000000000000000000000bEEF",
                        fast=False, run_id=run_id,
                    )

            client.burn.assert_not_called()
            mock_mint.assert_called_once()
            assert result["burn_tx"] == "0xpriorburn"

    def test_completed_run_returns_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = _permissive_env(tmp)
            run_id = "cctpv2-done"
            with mock.patch.dict(os.environ, env, clear=True):
                state_machine.transition(run_id, state_machine.STATE_PREFLIGHT)
                state_machine.transition(run_id, state_machine.STATE_SIGNED)
                state_machine.transition(
                    run_id, state_machine.STATE_BROADCAST,
                    payload={"burn_tx": "0xb"},
                )
                state_machine.transition(
                    run_id, state_machine.STATE_CONFIRMED, payload={"mint_tx": "0xmt"}
                )

            client = _fake_client()
            client.burn = mock.MagicMock(side_effect=AssertionError("must not burn"))

            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(
                    v2.CCTPv2Client, "mint", side_effect=AssertionError("must not mint")
                ):
                    result = client.transfer(
                        amount=1_000_000, dest_chain_id=42161,
                        mint_recipient="0x000000000000000000000000000000000000bEEF",
                        fast=False, run_id=run_id,
                    )

            assert result["status"] == "already_completed"
            assert result["version"] == "v2"
            assert result["mint_tx"] == "0xmt"


class TestPolicyGate:
    def test_policy_rejection_fails_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = os.path.join(tmp, "policy.json")
            with open(policy_path, "w", encoding="utf-8") as fh:
                json.dump({"defi-autopilot": {"allowed_chains": ["ethereum"]}}, fh)
            env = {
                "POLICY_FILE": policy_path,
                "STAGEFORGE_STATE_DIR": os.path.join(tmp, "states"),
                "AUDIT_LOG_PATH": os.path.join(tmp, "audit.jsonl"),
            }
            client = _fake_client(8453)  # base, not in allow-list
            client.burn = mock.MagicMock(side_effect=AssertionError("must not burn"))

            with mock.patch.dict(os.environ, env, clear=True):
                with pytest.raises(RuntimeError, match="Policy rejected"):
                    client.transfer(
                        amount=1_000_000, dest_chain_id=42161,
                        mint_recipient="0x000000000000000000000000000000000000bEEF",
                        fast=False, run_id="cctpv2-rejected",
                    )
                state = state_machine.load_state("cctpv2-rejected")

            client.burn.assert_not_called()
            assert state["current_state"] == state_machine.STATE_FAILED
