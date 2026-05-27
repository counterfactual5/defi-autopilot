"""AaveV3Client unit tests"""

import pytest
from unittest.mock import MagicMock, patch
from web3 import Web3

from defi_autopilot.protocols.aave import (
    AaveV3Client,
    AAVE_V3_POOLS,
    AAVE_V3_POOL_ABI,
    BASE_TOKENS_AAVE,
    INTEREST_RATE_VARIABLE,
    INTEREST_RATE_STABLE,
)


class TestPoolAddresses:
    """Test Aave V3 pool address configuration."""

    def test_base_pool_exists(self):
        assert 8453 in AAVE_V3_POOLS

    def test_ethereum_pool_exists(self):
        assert 1 in AAVE_V3_POOLS

    def test_arbitrum_pool_exists(self):
        assert 42161 in AAVE_V3_POOLS

    def test_all_pool_addresses_valid(self):
        for chain_id, addr in AAVE_V3_POOLS.items():
            assert Web3.is_address(addr), f"Chain {chain_id}: invalid pool address"

    def test_base_tokens_valid(self):
        for name, addr in BASE_TOKENS_AAVE.items():
            assert Web3.is_address(addr), f"{name}: invalid address"


class TestAbiIntegrity:
    """Test Aave V3 Pool ABI completeness."""

    def test_pool_abi_has_required_functions(self):
        function_names = [
            item["name"] for item in AAVE_V3_POOL_ABI
            if item.get("type") == "function"
        ]
        required = [
            "supply", "withdraw", "borrow", "repay",
            "setUserUseReserveAsCollateral",
            "getUserAccountData", "getReserveData",
        ]
        for fn in required:
            assert fn in function_names, f"Pool ABI missing: {fn}"


class TestInterestRateConstants:
    """Test interest rate mode constants."""

    def test_variable_mode(self):
        assert INTEREST_RATE_VARIABLE == 2

    def test_stable_mode(self):
        assert INTEREST_RATE_STABLE == 1


class TestAaveV3Client:
    """Test AaveV3Client initialization."""

    @patch("defi_autopilot.protocols.aave.client.get_w3")
    @patch("defi_autopilot.protocols.aave.client.get_chain_config")
    def test_client_init_base(self, mock_config, mock_w3):
        mock_config.return_value = MagicMock()
        mock_w3.return_value = MagicMock()
        client = AaveV3Client(8453)
        assert client.chain_id == 8453

    def test_client_unsupported_chain(self):
        with pytest.raises(ValueError):
            AaveV3Client(99999)
