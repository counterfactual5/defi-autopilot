"""CurveClient unit tests"""

import pytest
from web3 import Web3

from defi_autopilot.protocols.curve import (
    CurveClient,
    CURVE_POOLS,
    CURVE_POOL_ABI,
)


class TestCurvePools:
    """Test Curve pool configuration."""

    def test_ethereum_has_pools(self):
        assert 1 in CURVE_POOLS
        assert "3pool" in CURVE_POOLS[1]
        assert "steth" in CURVE_POOLS[1]

    def test_base_has_pool(self):
        assert 8453 in CURVE_POOLS

    def test_arbitrum_has_pool(self):
        assert 42161 in CURVE_POOLS

    def test_optimism_has_pool(self):
        assert 10 in CURVE_POOLS

    def test_all_pool_addresses_valid(self):
        for chain_id, pools in CURVE_POOLS.items():
            for pool_name, pool in pools.items():
                assert Web3.is_address(pool["address"]), \
                    f"Chain {chain_id} {pool_name}: invalid pool address"
                assert Web3.is_address(pool["lp_token"]), \
                    f"Chain {chain_id} {pool_name}: invalid lp_token"
                for i, coin in enumerate(pool["coins"]):
                    if coin != "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                        assert Web3.is_address(coin), \
                            f"Chain {chain_id} {pool_name} coin[{i}]: invalid"


class TestAbiIntegrity:
    """Test Curve pool ABI completeness."""

    def test_pool_abi_has_required_functions(self):
        names = [item["name"] for item in CURVE_POOL_ABI if item.get("type") == "function"]
        required = [
            "exchange", "get_dy", "add_liquidity",
            "remove_liquidity", "remove_liquidity_one_coin",
            "coins", "balances", "lp_token",
        ]
        for fn in required:
            assert fn in names, f"Curve ABI missing: {fn}"


class TestCurveClient:
    """Test CurveClient initialization."""

    def test_client_init_base(self):
        from unittest.mock import MagicMock, patch
        with patch("defi_autopilot.protocols.curve.client.get_w3") as mock_w3, \
             patch("defi_autopilot.protocols.curve.client.get_chain_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_w3.return_value = MagicMock()
            client = CurveClient(8453, "usdc-usdbc")
            assert client.chain_id == 8453

    def test_client_unsupported_chain(self):
        with pytest.raises(ValueError, match="not configured"):
            from unittest.mock import MagicMock, patch
            with patch("defi_autopilot.protocols.curve.client.get_w3"), \
                 patch("defi_autopilot.protocols.curve.client.get_chain_config") as mock_cfg:
                mock_cfg.return_value = MagicMock()
                CurveClient(99999, "3pool")

    def test_client_unknown_pool(self):
        with pytest.raises(ValueError, match="not found"):
            from unittest.mock import MagicMock, patch
            with patch("defi_autopilot.protocols.curve.client.get_w3"), \
                 patch("defi_autopilot.protocols.curve.client.get_chain_config") as mock_cfg:
                mock_cfg.return_value = MagicMock()
                CurveClient(1, "nonexistent")
