"""DeBridgeClient unit tests."""

import pytest

from defi_autopilot.protocols.debridge import (
    DeBridgeClient,
    DeBridgeError,
    DEBRIDGE_CHAIN_IDS,
    NATIVE_TOKEN,
)


class TestChainSupport:
    def test_common_evm_chains(self):
        for cid in (1, 8453, 42161, 10, 137):
            assert cid in DEBRIDGE_CHAIN_IDS

    def test_native_token_sentinel(self):
        assert NATIVE_TOKEN == "0x0000000000000000000000000000000000000000"


class TestClientInit:
    def test_init_ok(self):
        c = DeBridgeClient(8453, 42161)
        assert c.src_chain_id == 8453
        assert c.dst_chain_id == 42161

    def test_unsupported_src(self):
        with pytest.raises(ValueError, match="source chain"):
            DeBridgeClient(99999, 8453)

    def test_unsupported_dst(self):
        with pytest.raises(ValueError, match="destination chain"):
            DeBridgeClient(8453, 99999)

    def test_headers_with_key(self):
        c = DeBridgeClient(8453, 42161, api_key="k")
        assert c._headers()["Authorization"] == "Bearer k"

    def test_headers_without_key(self):
        c = DeBridgeClient(8453, 42161)
        assert "Authorization" not in c._headers()


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class TestQuoteAndOrder:
    def test_get_quote_builds_params(self, monkeypatch):
        captured = {}

        def fake_get(url, params=None, headers=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            return _Resp({"estimation": {"dstChainTokenOut": {"amount": "123"}}})

        monkeypatch.setattr("defi_autopilot.protocols.debridge.client.httpx.get", fake_get)

        c = DeBridgeClient(8453, 42161)
        out = c.get_quote("0xSRC", "0xDST", 1000)
        assert out["estimation"]["dstChainTokenOut"]["amount"] == "123"
        assert captured["url"].endswith("/dln/order/quote")
        assert captured["params"]["srcChainId"] == 8453
        assert captured["params"]["dstChainId"] == 42161
        assert captured["params"]["srcChainTokenInAmount"] == "1000"

    def test_api_error_raises(self, monkeypatch):
        def fake_get(url, params=None, headers=None, timeout=None):
            return _Resp({"errorId": "ERR_LOW_LIQUIDITY", "errorMessage": "no route"})

        monkeypatch.setattr("defi_autopilot.protocols.debridge.client.httpx.get", fake_get)
        c = DeBridgeClient(8453, 42161)
        with pytest.raises(DeBridgeError, match="no route"):
            c.get_quote("0xSRC", "0xDST", 1000)

    def test_create_order_dry_run_no_send(self, monkeypatch):
        def fake_get(url, params=None, headers=None, timeout=None):
            return _Resp({
                "orderId": "0xabc",
                "estimation": {"x": 1},
                "tx": {"to": "0xRouter", "data": "0xdead", "value": "0"},
            })

        monkeypatch.setattr("defi_autopilot.protocols.debridge.client.httpx.get", fake_get)

        # send=False must not touch signer/tx infrastructure.
        c = DeBridgeClient(8453, 42161)
        out = c.create_order(
            "0xSRC", "0xDST", 1000,
            recipient="0xRecipient", order_authority="0xAuth", from_addr="0xMe",
            send=False,
        )
        assert out["status"] == "prepared"
        assert out["tx"]["to"] == "0xRouter"
