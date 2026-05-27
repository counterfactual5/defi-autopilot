"""OneInchClient unit tests"""

import pytest
from defi_autopilot.protocols.oneinch import (
    OneInchClient,
    INCH_CHAIN_IDS,
    BASE_TOKENS_INCH,
)


class TestChainSupport:
    """Test 1inch chain support configuration."""

    def test_base_supported(self):
        assert 8453 in INCH_CHAIN_IDS

    def test_ethereum_supported(self):
        assert 1 in INCH_CHAIN_IDS

    def test_all_supported_chains(self):
        expected = [1, 8453, 42161, 10, 137]
        for cid in expected:
            assert cid in INCH_CHAIN_IDS


class TestBaseTokens:
    """Test Base chain token addresses."""

    def test_tokens_valid(self):
        for name, addr in BASE_TOKENS_INCH.items():
            assert addr.startswith("0x"), f"{name}: not an address"
            assert len(addr) == 42, f"{name}: wrong length"

    def test_eth_native_address(self):
        # 1inch uses the zero-like address for native ETH
        assert "ETH" in BASE_TOKENS_INCH


class TestOneInchClient:
    """Test OneInchClient initialization."""

    def test_client_init_base(self):
        client = OneInchClient(8453)
        assert client.chain_id == 8453

    def test_client_with_api_key(self):
        client = OneInchClient(8453, api_key="test_key")
        assert client._api_key == "test_key"

    def test_client_unsupported_chain(self):
        with pytest.raises(ValueError, match="does not support"):
            OneInchClient(99999)

    def test_headers_with_key(self):
        client = OneInchClient(8453, api_key="mykey")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer mykey"

    def test_headers_without_key(self):
        client = OneInchClient(8453)
        headers = client._headers()
        assert "Authorization" not in headers
