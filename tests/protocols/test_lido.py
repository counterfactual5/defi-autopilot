"""LidoClient unit tests"""

import pytest
from web3 import Web3

from defi_autopilot.protocols.lido import (
    LidoClient,
    LIDO_ADDRESSES,
    LIDO_ABI,
    WSTETH_ABI,
)


class TestLidoAddresses:
    """Test Lido contract addresses."""

    def test_ethereum_has_native_staking(self):
        addrs = LIDO_ADDRESSES[1]
        assert "lido" in addrs
        assert "wstETH" in addrs

    def test_base_has_wsteth(self):
        assert "wstETH" in LIDO_ADDRESSES[8453]

    def test_arbitrum_has_wsteth(self):
        assert "wstETH" in LIDO_ADDRESSES[42161]

    def test_optimism_has_wsteth(self):
        assert "wstETH" in LIDO_ADDRESSES[10]

    def test_polygon_has_wsteth(self):
        assert "wstETH" in LIDO_ADDRESSES[137]

    def test_all_addresses_valid(self):
        for chain_id, addrs in LIDO_ADDRESSES.items():
            for name, addr in addrs.items():
                assert Web3.is_address(addr), f"Chain {chain_id} {name}: invalid address"


class TestAbiIntegrity:
    """Test Lido ABI completeness."""

    def test_lido_abi_has_submit(self):
        names = [item["name"] for item in LIDO_ABI if item.get("type") == "function"]
        assert "submit" in names
        assert "balanceOf" in names
        assert "getTotalPooledEther" in names

    def test_wsteth_abi_has_wrap_unwrap(self):
        names = [item["name"] for item in WSTETH_ABI if item.get("type") == "function"]
        assert "wrap" in names
        assert "unwrap" in names
        assert "stEthPerToken" in names


class TestLidoClient:
    """Test LidoClient initialization."""

    def test_ethereum_supports_staking(self):
        from unittest.mock import MagicMock, patch
        with patch("defi_autopilot.protocols.lido.client.get_w3") as mock_w3, \
             patch("defi_autopilot.protocols.lido.client.get_chain_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_w3.return_value = MagicMock()
            client = LidoClient(1)
            assert client.supports_native_staking is True

    def test_base_no_staking(self):
        from unittest.mock import MagicMock, patch
        with patch("defi_autopilot.protocols.lido.client.get_w3") as mock_w3, \
             patch("defi_autopilot.protocols.lido.client.get_chain_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_w3.return_value = MagicMock()
            client = LidoClient(8453)
            assert client.supports_native_staking is False

    def test_unsupported_chain(self):
        with pytest.raises(ValueError, match="not deployed"):
            from unittest.mock import MagicMock, patch
            with patch("defi_autopilot.protocols.lido.client.get_w3"), \
                 patch("defi_autopilot.protocols.lido.client.get_chain_config") as mock_cfg:
                mock_cfg.return_value = MagicMock()
                LidoClient(99999)
