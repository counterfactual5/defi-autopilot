"""UniswapClient unit tests"""

import pytest
from web3 import Web3

from defi_autopilot.protocols.uniswap import (
    UniswapClient,
    UNISWAP_CHAIN_IDS,
    UNIVERSAL_ROUTER,
    BASE_TOKENS_UNI,
    ETH_TOKENS_UNI,
)


class TestChainSupport:
    """Test Uniswap chain support."""

    def test_base_supported(self):
        assert 8453 in UNISWAP_CHAIN_IDS

    def test_ethereum_supported(self):
        assert 1 in UNISWAP_CHAIN_IDS

    def test_six_chains(self):
        assert len(UNISWAP_CHAIN_IDS) == 6


class TestRouterAddresses:
    """Test Universal Router addresses."""

    def test_all_routers_valid(self):
        for chain_id, addr in UNIVERSAL_ROUTER.items():
            assert Web3.is_address(addr), f"Chain {chain_id}: invalid router"

    def test_base_router(self):
        assert 8453 in UNIVERSAL_ROUTER


class TestTokenAddresses:
    """Test token address configurations."""

    def test_base_tokens_valid(self):
        for name, addr in BASE_TOKENS_UNI.items():
            assert Web3.is_address(addr), f"{name}: invalid address"

    def test_eth_tokens_valid(self):
        for name, addr in ETH_TOKENS_UNI.items():
            assert Web3.is_address(addr), f"{name}: invalid address"

    def test_native_eth_in_both(self):
        assert "ETH" in BASE_TOKENS_UNI
        assert "ETH" in ETH_TOKENS_UNI


class TestUniswapClient:
    """Test UniswapClient initialization."""

    def test_client_init_base(self):
        from unittest.mock import MagicMock, patch
        with patch("defi_autopilot.protocols.uniswap.client.get_w3") as mock_w3, \
             patch("defi_autopilot.protocols.uniswap.client.get_chain_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_w3.return_value = MagicMock()
            client = UniswapClient(8453)
            assert client.chain_id == 8453

    def test_client_unsupported_chain(self):
        with pytest.raises(ValueError, match="does not support"):
            from unittest.mock import MagicMock, patch
            with patch("defi_autopilot.protocols.uniswap.client.get_w3"), \
                 patch("defi_autopilot.protocols.uniswap.client.get_chain_config") as mock_cfg:
                mock_cfg.return_value = MagicMock()
                UniswapClient(99999)
