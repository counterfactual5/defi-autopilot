"""MorphoClient 单元测试"""

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
    """测试 MarketParams 数据类"""

    def test_market_id_deterministic(self):
        """相同参数应产生相同 market ID"""
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
        """不同参数应产生不同 market ID"""
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
            lltv=800000000000000000,  # 不同的 LLTV
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
    """测试预置市场配置"""

    def test_base_markets_not_empty(self):
        assert len(BASE_MARKETS) > 0

    def test_base_markets_have_valid_addresses(self):
        for name, mp in BASE_MARKETS.items():
            assert Web3.is_address(mp.loan_token), f"{name}: loan_token 无效"
            assert Web3.is_address(mp.collateral_token), f"{name}: collateral_token 无效"
            assert Web3.is_address(mp.oracle), f"{name}: oracle 无效"
            assert Web3.is_address(mp.irm), f"{name}: irm 无效"
            assert 0 < mp.lltv < 10**18, f"{name}: lltv 超出范围"

    def test_base_tokens_addresses(self):
        for name, addr in BASE_TOKENS.items():
            assert Web3.is_address(addr), f"{name}: 地址无效"


class TestMorphoClient:
    """测试 MorphoClient 初始化"""

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
        mock_config.side_effect = ValueError("不支持的链 ID: 999")
        with pytest.raises(ValueError):
            MorphoClient(999)


class TestAbiIntegrity:
    """测试 ABI 完整性"""

    def test_morpho_abi_has_required_functions(self):
        function_names = [
            item["name"] for item in MORPHO_BLUE_ABI
            if item.get("type") == "function"
        ]
        required = ["supply", "withdraw", "supplyCollateral",
                     "withdrawCollateral", "borrow", "repay",
                     "position", "market"]
        for fn in required:
            assert fn in function_names, f"ABI 缺少函数: {fn}"
