"""Core module unit tests"""

import pytest
from defi_autopilot.core.chains import CHAIN_PRESETS, ChainConfig


class TestChainPresets:
    """Test chain configurations"""

    def test_base_chain_exists(self):
        assert 8453 in CHAIN_PRESETS

    def test_ethereum_chain_exists(self):
        assert 1 in CHAIN_PRESETS

    def test_arbitrum_chain_exists(self):
        assert 42161 in CHAIN_PRESETS

    def test_all_presets_have_required_fields(self):
        for chain_id, config in CHAIN_PRESETS.items():
            assert config.chain_id == chain_id
            assert config.name
            assert config.explorer_url
            assert config.native_token

    def test_morpho_address_consistent(self):
        """Morpho Blue address should be the same across all chains"""
        morpho_addrs = set()
        for config in CHAIN_PRESETS.values():
            if config.morpho_blue:
                morpho_addrs.add(config.morpho_blue.lower())
        assert len(morpho_addrs) == 1, "Morpho address is inconsistent"
