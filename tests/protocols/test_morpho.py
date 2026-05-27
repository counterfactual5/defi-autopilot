"""MorphoClient unit tests"""

import pytest
from unittest.mock import MagicMock, patch
from web3 import Web3

from defi_autopilot.protocols.morpho import (
    MorphoClient,
    MarketParams,
    BASE_MARKETS,
    BASE_TOKENS,
    MORPHO_BLUE_ABI,
)


class TestMarketParams:
    """Test MarketParams dataclass"""

    def test_market_id_deterministic(self):
        """Same parameters should produce the same market ID"""
        mp = MarketParams(
            loan_token="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            collateral_token="0x4200000000000000000000000000000000000006",
            oracle="0x5c9e10a30610EfE425697e3b9145569cAcdA7A3f",
            irm="0x870aAcb0EB19c95DaE3Fb3e4047a8D7F28461141",
            lltv=770000000000000000,
        )
        id1 = mp.market_id
        id2 = mp.market_id
        assert id1 == id2
        assert isinstance(id1, bytes)
        assert len(id1) == 32

    def test_market_id_different_params(self):
        """Different parameters should produce different market IDs"""
        mp1 = MarketParams(
            loan_token="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            collateral_token="0x4200000000000000000000000000000000000006",
            oracle="0x5c9e10a30610EfE425697e3b9145569cAcdA7A3f",
            irm="0x870aAcb0EB19c95DaE3Fb3e4047a8D7F28461141",
            lltv=770000000000000000,
        )
        mp2 = MarketParams(
            loan_token="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            collateral_token="0x4200000000000000000000000000000000000006",
            oracle="0x5c9e10a30610EfE425697e3b9145569cAcdA7A3f",
            irm="0x870aAcb0EB19c95DaE3Fb3e4047a8D7F28461141",
            lltv=800000000000000000,  # Different LLTV
        )
        assert mp1.market_id != mp2.market_id

    def test_to_tuple(self):
        mp = MarketParams(
            loan_token="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            collateral_token="0x4200000000000000000000000000000000000006",
            oracle="0x5c9e10a30610EfE425697e3b9145569cAcdA7A3f",
            irm="0x870aAcb0EB19c95DaE3Fb3e4047a8D7F28461141",
            lltv=770000000000000000,
        )
        t = mp.to_tuple()
        assert len(t) == 5
        assert t[0] == Web3.to_checksum_address(mp.loan_token)
        assert t[4] == 770000000000000000


class TestBaseMarkets:
    """Test preset market configurations"""

    def test_base_markets_not_empty(self):
        assert len(BASE_MARKETS) > 0

    def test_base_markets_have_valid_addresses(self):
        for name, mp in BASE_MARKETS.items():
            assert Web3.is_address(mp.loan_token), f"{name}: invalid loan_token"
            assert Web3.is_address(mp.collateral_token), f"{name}: invalid collateral_token"
            assert Web3.is_address(mp.oracle), f"{name}: invalid oracle"
            assert Web3.is_address(mp.irm), f"{name}: invalid irm"
            assert 0 < mp.lltv < 10**18, f"{name}: lltv out of range"

    def test_base_tokens_addresses(self):
        for name, addr in BASE_TOKENS.items():
            assert Web3.is_address(addr), f"{name}: invalid address"


class TestMorphoClient:
    """Test MorphoClient initialization"""

    @patch("defi_autopilot.protocols.morpho.client.get_w3")
    @patch("defi_autopilot.protocols.morpho.client.get_chain_config")
    def test_client_init(self, mock_config, mock_w3):
        mock_config.return_value = MagicMock(morpho_blue="0xBBBBBBBBB9cC5e90e3b3af64bdAF62C37EEFFcBb")
        mock_w3.return_value = MagicMock()

        client = MorphoClient(8453)
        assert client.chain_id == 8453
        assert client._morpho_address == "0xBBBBBBBBB9cC5e90e3b3af64bdAF62C37EEFFcBb"

    @patch("defi_autopilot.protocols.morpho.client.get_w3")
    @patch("defi_autopilot.protocols.morpho.client.get_chain_config")
    def test_client_invalid_chain(self, mock_config, mock_w3):
        mock_config.side_effect = ValueError("Unsupported chain ID: 999")
        with pytest.raises(ValueError):
            MorphoClient(999)


class TestAbiIntegrity:
    """Test ABI completeness"""

    def test_morpho_abi_has_required_functions(self):
        function_names = [
            item["name"] for item in MORPHO_BLUE_ABI
            if item.get("type") == "function"
        ]
        required = ["supply", "withdraw", "supplyCollateral",
                     "withdrawCollateral", "borrow", "repay",
                     "position", "market"]
        for fn in required:
            assert fn in function_names, f"ABI missing function: {fn}"
