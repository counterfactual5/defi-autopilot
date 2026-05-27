"""MoonwellClient unit tests"""

import pytest
from unittest.mock import MagicMock, patch
from web3 import Web3

from defi_autopilot.protocols.moonwell import (
    MoonwellClient,
    BASE_MOONWELL,
    CTOKEN_ABI,
    COMPTROLLER_ABI,
)


class TestBaseMoonwell:
    """Test Base chain Moonwell configuration"""

    def test_comptroller_address_valid(self):
        assert Web3.is_address(BASE_MOONWELL["comptroller"])

    def test_tokens_have_valid_addresses(self):
        for name, info in BASE_MOONWELL["tokens"].items():
            assert Web3.is_address(info["cToken"]), f"{name}: invalid cToken"
            assert Web3.is_address(info["underlying"]), f"{name}: invalid underlying"

    def test_at_least_one_token(self):
        assert len(BASE_MOONWELL["tokens"]) >= 1


class TestAbiIntegrity:
    """Test ABI completeness"""

    def test_ctoken_abi_has_required_functions(self):
        function_names = [
            item["name"] for item in CTOKEN_ABI
            if item.get("type") == "function"
        ]
        required = ["mint", "redeem", "redeemUnderlying", "borrow", "repayBorrow",
                     "balanceOf", "borrowBalanceCurrent", "exchangeRateCurrent", "underlying"]
        for fn in required:
            assert fn in function_names, f"cToken ABI missing: {fn}"

    def test_comptroller_abi_has_required_functions(self):
        function_names = [
            item["name"] for item in COMPTROLLER_ABI
            if item.get("type") == "function"
        ]
        required = ["enterMarkets", "getAccountLiquidity", "markets"]
        for fn in required:
            assert fn in function_names, f"Comptroller ABI missing: {fn}"


class TestMoonwellClient:
    """Test MoonwellClient"""

    @patch("defi_autopilot.protocols.moonwell.client.get_w3")
    @patch("defi_autopilot.protocols.moonwell.client.get_chain_config")
    def test_client_init(self, mock_config, mock_w3):
        mock_config.return_value = MagicMock()
        mock_w3.return_value = MagicMock()
        client = MoonwellClient(8453)
        assert client.chain_id == 8453
