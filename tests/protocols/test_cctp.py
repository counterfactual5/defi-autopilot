"""Tests for the Circle CCTP V1 client.

The valuable paths here are the resumable orchestration and anti-replay: a
transfer that already burned must never re-burn on resume, and a completed
transfer must return idempotently.  Network and signing are fully mocked.
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


# ── Pure helpers ──────────────────────────────────────────────────────────────

class TestStaticData:
    def test_key_domain_mappings(self):
        assert cctp.CCTP_DOMAINS[1] == 0       # Ethereum
        assert cctp.CCTP_DOMAINS[10] == 2      # Optimism
        assert cctp.CCTP_DOMAINS[42161] == 3   # Arbitrum
        assert cctp.CCTP_DOMAINS[8453] == 6    # Base
        assert cctp.CCTP_DOMAINS[137] == 7     # Polygon
        assert cctp.CCTP_DOMAINS[130] == 10    # Unichain

    def test_every_supported_chain_has_addresses(self):
        for chain_id in cctp.CCTP_DOMAINS:
            assert chain_id in cctp.USDC_ADDRESSES
            assert chain_id in cctp.TOKEN_MESSENGER
            assert chain_id in cctp.MESSAGE_TRANSMITTER

    def test_address_to_bytes32_left_pads(self):
        addr = "0x000000000000000000000000000000000000dEaD"
        out = cctp.address_to_bytes32(addr)
        assert len(out) == 32
        assert out[:12] == bytes(12)
        assert out[12:].hex() == "000000000000000000000000000000000000dead"


class TestClientInit:
    def test_unsupported_chain_raises_before_network(self):
        # The CCTP_DOMAINS guard runs before any RPC/config lookup.
        with pytest.raises(ValueError, match="CCTP not supported"):
            cctp.CCTPClient(999999)


# ── Orchestration: build an instance without touching the network ─────────────

def _fake_client(chain_id: int = 8453) -> cctp.CCTPClient:
    c = object.__new__(cctp.CCTPClient)
    c.chain_id = chain_id
    c.domain = cctp.CCTP_DOMAINS[chain_id]
    c.config = types.SimpleNamespace(name="base")
    c.w3 = mock.MagicMock()
    c.usdc = cctp.USDC_ADDRESSES[chain_id]
    c.token_messenger = cctp.TOKEN_MESSENGER[chain_id]
    c.message_transmitter = cctp.MESSAGE_TRANSMITTER[chain_id]
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


class TestTransferHappyPath:
    def test_full_flow_reaches_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = _permissive_env(tmp)
            client = _fake_client()
            recipient = "0x000000000000000000000000000000000000bEEF"

            client.burn = mock.MagicMock(return_value={
                "burn_tx": "0xburn",
                "message": "0xmsg",
                "message_hash": "0xhash",
            })
            client.get_attestation = mock.MagicMock(return_value="0xattestation")

            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(
                    cctp.CCTPClient, "mint", return_value={"mint_tx": "0xmint", "status": 1}
                ) as mock_mint:
                    result = client.transfer(
                        amount=1_000_000,
                        dest_chain_id=42161,
                        mint_recipient=recipient,
                        run_id="cctp-happy",
                    )

            assert result["status"] == "completed"
            assert result["burn_tx"] == "0xburn"
            assert result["mint_tx"] == "0xmint"
            client.burn.assert_called_once()
            client.get_attestation.assert_called_once_with("0xhash", timeout=1200)
            mock_mint.assert_called_once()

            with mock.patch.dict(os.environ, env, clear=True):
                final = state_machine.load_state("cctp-happy")
            assert final["current_state"] == state_machine.STATE_CONFIRMED
            assert final["payload"]["mint_tx"] == "0xmint"


class TestAntiReplayResume:
    def test_resume_after_burn_does_not_reburn(self):
        """A run already at BROADCAST must skip burn and only attest+mint."""
        with tempfile.TemporaryDirectory() as tmp:
            env = _permissive_env(tmp)
            run_id = "cctp-resume"

            # Pre-seed the checkpoint as if burn already broadcast.
            with mock.patch.dict(os.environ, env, clear=True):
                state_machine.transition(run_id, state_machine.STATE_PREFLIGHT)
                state_machine.transition(run_id, state_machine.STATE_SIGNED)
                state_machine.transition(
                    run_id, state_machine.STATE_BROADCAST,
                    payload={
                        "burn_tx": "0xpriorburn",
                        "message": "0xmsg",
                        "message_hash": "0xhash",
                        "dest": 42161,
                    },
                )

            client = _fake_client()
            client.burn = mock.MagicMock(side_effect=AssertionError("burn must not run on resume"))
            client.get_attestation = mock.MagicMock(return_value="0xattestation")

            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(
                    cctp.CCTPClient, "mint", return_value={"mint_tx": "0xmint2", "status": 1}
                ) as mock_mint:
                    result = client.transfer(
                        amount=1_000_000,
                        dest_chain_id=42161,
                        mint_recipient="0x000000000000000000000000000000000000bEEF",
                        run_id=run_id,
                    )

            client.burn.assert_not_called()
            mock_mint.assert_called_once()
            assert result["status"] == "completed"
            assert result["burn_tx"] == "0xpriorburn"

    def test_completed_run_returns_idempotently(self):
        """Re-running a CONFIRMED transfer never re-burns or re-mints."""
        with tempfile.TemporaryDirectory() as tmp:
            env = _permissive_env(tmp)
            run_id = "cctp-done"

            with mock.patch.dict(os.environ, env, clear=True):
                state_machine.transition(run_id, state_machine.STATE_PREFLIGHT)
                state_machine.transition(run_id, state_machine.STATE_SIGNED)
                state_machine.transition(
                    run_id, state_machine.STATE_BROADCAST,
                    payload={"burn_tx": "0xb", "message": "0xm", "message_hash": "0xh"},
                )
                state_machine.transition(
                    run_id, state_machine.STATE_CONFIRMED, payload={"mint_tx": "0xmt"}
                )

            client = _fake_client()
            client.burn = mock.MagicMock(side_effect=AssertionError("must not burn"))
            client.get_attestation = mock.MagicMock(side_effect=AssertionError("must not attest"))

            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(
                    cctp.CCTPClient, "mint", side_effect=AssertionError("must not mint")
                ):
                    result = client.transfer(
                        amount=1_000_000,
                        dest_chain_id=42161,
                        mint_recipient="0x000000000000000000000000000000000000bEEF",
                        run_id=run_id,
                    )

            assert result["status"] == "already_completed"
            assert result["burn_tx"] == "0xb"
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
                        amount=1_000_000,
                        dest_chain_id=42161,
                        mint_recipient="0x000000000000000000000000000000000000bEEF",
                        run_id="cctp-rejected",
                    )
                state = state_machine.load_state("cctp-rejected")

            client.burn.assert_not_called()
            assert state["current_state"] == state_machine.STATE_FAILED
