"""Core tokens module tests"""

import pytest
from web3 import Web3

from defi_autopilot.core.tokens import (
    BASE_TOKENS,
    ETH_TOKENS,
    CHAIN_TOKENS,
    NATIVE_ETH,
    get_token_address,
)


class TestBaseTokens:
    """Test Base chain token addresses."""

    def test_usdc_valid(self):
        assert Web3.is_address(BASE_TOKENS["USDC"])

    def test_weth_valid(self):
        assert Web3.is_address(BASE_TOKENS["WETH"])

    def test_native_eth(self):
        assert BASE_TOKENS["ETH"] == NATIVE_ETH


class TestEthTokens:
    """Test Ethereum mainnet token addresses."""

    def test_usdc_valid(self):
        assert Web3.is_address(ETH_TOKENS["USDC"])

    def test_steth_valid(self):
        assert Web3.is_address(ETH_TOKENS["stETH"])


class TestAllChainTokens:
    """Test all chain token configs."""

    def test_all_chains_have_tokens(self):
        for chain_id in [1, 8453, 42161, 10, 137]:
            assert chain_id in CHAIN_TOKENS

    def test_all_addresses_checksummed(self):
        for chain_id, tokens in CHAIN_TOKENS.items():
            for name, addr in tokens.items():
                # Either native ETH sentinel or valid checksummed address
                if addr == NATIVE_ETH:
                    continue
                assert addr == Web3.to_checksum_address(addr), \
                    f"Chain {chain_id} {name}: not checksummed"


class TestGetTokenAddress:
    """Test token address lookup."""

    def test_known_token(self):
        addr = get_token_address(8453, "USDC")
        assert Web3.is_address(addr)

    def test_case_insensitive(self):
        assert get_token_address(8453, "usdc") == get_token_address(8453, "USDC")

    def test_unknown_token_raises(self):
        with pytest.raises(ValueError, match="not found"):
            get_token_address(8453, "NONEXISTENT")

    def test_unknown_chain_raises(self):
        with pytest.raises(ValueError, match="not found"):
            get_token_address(99999, "USDC")
