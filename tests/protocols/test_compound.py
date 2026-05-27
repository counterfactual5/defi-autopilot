"""CompoundV3Client unit tests"""

import pytest
from web3 import Web3

from defi_autopilot.protocols.compound import (
    CompoundV3Client,
    COMET_MARKETS,
    COMET_ABI,
)


class TestCometMarkets:
    """Test Compound V3 market configuration."""

    def test_ethereum_has_markets(self):
        assert 1 in COMET_MARKETS
        assert "USDC" in COMET_MARKETS[1]
        assert "WETH" in COMET_MARKETS[1]

    def test_base_has_usdc(self):
        assert 8453 in COMET_MARKETS
        assert "USDC" in COMET_MARKETS[8453]

    def test_arbitrum_has_usdc(self):
        assert 42161 in COMET_MARKETS
        assert "USDC" in COMET_MARKETS[42161]

    def test_polygon_has_usdc(self):
        assert 137 in COMET_MARKETS

    def test_all_addresses_valid(self):
        for chain_id, markets in COMET_MARKETS.items():
            for market_name, market in markets.items():
                assert Web3.is_address(market["comet"]), \
                    f"Chain {chain_id} {market_name}: invalid comet"
                assert Web3.is_address(market["base_token"]), \
                    f"Chain {chain_id} {market_name}: invalid base_token"
                for coll_name, coll_addr in market["collaterals"].items():
                    assert Web3.is_address(coll_addr), \
                        f"Chain {chain_id} {market_name} {coll_name}: invalid"


class TestAbiIntegrity:
    """Test Comet ABI completeness."""

    def test_comet_abi_has_required_functions(self):
        names = [item["name"] for item in COMET_ABI if item.get("type") == "function"]
        required = [
            "supply", "withdraw", "supplyCollateral", "withdrawCollateral",
            "balanceOf", "borrowBalanceOf", "getAssetInfo",
            "getUserCollateral", "baseToken", "numAssets",
        ]
        for fn in required:
            assert fn in names, f"Comet ABI missing: {fn}"


class TestCompoundV3Client:
    """Test CompoundV3Client initialization."""

    def test_client_init_base_usdc(self):
        from unittest.mock import MagicMock, patch
        with patch("defi_autopilot.protocols.compound.client.get_w3") as mock_w3, \
             patch("defi_autopilot.protocols.compound.client.get_chain_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_w3.return_value = MagicMock()
            client = CompoundV3Client(8453, "USDC")
            assert client.chain_id == 8453

    def test_client_unsupported_chain(self):
        with pytest.raises(ValueError, match="not deployed"):
            from unittest.mock import MagicMock, patch
            with patch("defi_autopilot.protocols.compound.client.get_w3"), \
                 patch("defi_autopilot.protocols.compound.client.get_chain_config") as mock_cfg:
                mock_cfg.return_value = MagicMock()
                CompoundV3Client(99999, "USDC")

    def test_client_unknown_market(self):
        with pytest.raises(ValueError, match="not found"):
            from unittest.mock import MagicMock, patch
            with patch("defi_autopilot.protocols.compound.client.get_w3"), \
                 patch("defi_autopilot.protocols.compound.client.get_chain_config") as mock_cfg:
                mock_cfg.return_value = MagicMock()
                CompoundV3Client(8453, "UNKNOWN")
