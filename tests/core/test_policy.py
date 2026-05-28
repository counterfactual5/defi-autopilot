"""Tests for the shared risk-control policy engine in defi-autopilot."""

from __future__ import annotations

import json
import os
import tempfile
from decimal import Decimal

from defi_autopilot.policy import Policy, check, load_policy


class TestPermissiveDefault:
    def test_no_file_allows_everything(self):
        pol = load_policy("/nonexistent/policy.json")
        result = check(pol, {"amount": "999999", "chain": "base"})
        assert result.allowed
        assert result.violations == []


class TestMaxAmount:
    def test_under(self):
        pol = Policy(max_amount=Decimal("5"))
        assert check(pol, {"amount": "1"}).allowed

    def test_over(self):
        pol = Policy(max_amount=Decimal("5"))
        result = check(pol, {"amount": "10"})
        assert not result.allowed
        assert result.violations[0].rule == "max_amount"


class TestAllowedChains:
    def test_allowed(self):
        pol = Policy(allowed_chains=["base", "ethereum"])
        assert check(pol, {"chain": "base"}).allowed

    def test_rejected(self):
        pol = Policy(allowed_chains=["base"])
        result = check(pol, {"chain": "fantom"})
        assert not result.allowed
        assert result.violations[0].rule == "allowed_chains"


class TestBlacklist:
    def test_blocked_receiver(self):
        pol = Policy(blacklist_addresses=["0xbad"])
        result = check(pol, {"receiver": "0xBAD"})
        assert not result.allowed
        assert result.violations[0].rule == "blacklist_addresses"

    def test_blocked_spender(self):
        pol = Policy(blacklist_addresses=["0xbad"])
        result = check(pol, {"spender": "0xbad"})
        assert not result.allowed


class TestLoadProjectOverlay:
    def test_defi_section(self):
        data = {
            "global": {"max_amount": 1000},
            "defi-autopilot": {"max_amount": 5, "allowed_chains": ["base"]},
        }
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            pol = load_policy(path)  # default project = defi-autopilot
            assert pol.max_amount == Decimal("5")
            assert pol.allowed_chains == ["base"]
        finally:
            os.unlink(path)
