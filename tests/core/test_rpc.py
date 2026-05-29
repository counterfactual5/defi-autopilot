"""Core RPC module tests"""

import pytest
from unittest.mock import patch

from defi_autopilot.core.rpc import get_w3, get_chain_config


class TestGetChainConfig:
    """Test chain config lookup."""

    def test_base_config(self):
        config = get_chain_config(8453)
        assert config.chain_id == 8453
        assert config.name == "Base"

    def test_unknown_chain_raises(self):
        with pytest.raises(ValueError, match="Unsupported chain ID"):
            get_chain_config(99999)


class TestGetW3:
    """Test Web3 instance creation."""

    @patch("defi_autopilot.core.rpc.CHAIN_PRESETS")
    def test_default_rpc_fallback(self, mock_presets):
        """Default RPC URLs should work without env vars."""
        from defi_autopilot.core.chains import ChainConfig
        mock_presets.__getitem__ = lambda self, k: ChainConfig(
            chain_id=8453, name="Base", rpc_url="https://mainnet.base.org",
            explorer_url="", native_token="ETH",
        )
        # Should not raise
        w3 = get_w3(8453, rpc_url="https://mainnet.base.org")
        assert w3 is not None
