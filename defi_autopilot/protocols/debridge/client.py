"""
deBridge DLN Client — arbitrary-token cross-chain swaps.

deBridge's DLN (deSwap Liquidity Network) settles cross-chain orders for any
supported token pair, complementing the CCTP path (which only moves USDC).
Like the 1inch client this is a thin REST wrapper: the DLN API returns a ready
-to-broadcast transaction, so no protocol contract ABI is needed locally.

API docs: https://dln.debridge.finance/v1.0/ (Swagger)

Two calls:
  - ``get_quote``    -> GET /dln/order/quote     (estimation only, read-only)
  - ``create_order`` -> GET /dln/order/create-tx (estimation + tx, then send)
"""

from typing import Any, Dict, Optional

import httpx

from defi_autopilot.core.signer import get_address
from defi_autopilot.core.tx import build_and_send_tx

# Public DLN API (no key required; an optional referral/affiliate can be added).
DLN_API_BASE = "https://dln.debridge.finance/v1.0"

# deBridge chain IDs match EVM chain IDs for EVM networks. Solana is the one
# notable exception (kept here for reference / future use).
DEBRIDGE_CHAIN_IDS = {
    1: 1,           # Ethereum
    8453: 8453,     # Base
    42161: 42161,   # Arbitrum
    10: 10,         # Optimism
    137: 137,       # Polygon
    43114: 43114,   # Avalanche
    130: 130,       # Unichain
    7565164: 7565164,  # Solana (non-EVM; tx-building path differs)
}

# deBridge uses the zero address as the native-token sentinel on EVM chains.
NATIVE_TOKEN = "0x0000000000000000000000000000000000000000"


class DeBridgeError(RuntimeError):
    """Raised when the DLN API rejects a quote/order request."""


class DeBridgeClient:
    """deBridge DLN cross-chain swap client (REST API)."""

    def __init__(
        self,
        src_chain_id: int,
        dst_chain_id: int,
        api_key: Optional[str] = None,
    ):
        if src_chain_id not in DEBRIDGE_CHAIN_IDS:
            raise ValueError(f"deBridge does not support source chain {src_chain_id}")
        if dst_chain_id not in DEBRIDGE_CHAIN_IDS:
            raise ValueError(f"deBridge does not support destination chain {dst_chain_id}")
        self.src_chain_id = src_chain_id
        self.dst_chain_id = dst_chain_id
        self._api_key = api_key

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        resp = httpx.get(
            f"{DLN_API_BASE}/{endpoint}",
            params=params,
            headers=self._headers(),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        # DLN returns 200 with an errorId/errorMessage body on logical failures.
        if isinstance(data, dict) and data.get("errorId"):
            raise DeBridgeError(
                f"{data.get('errorId')}: {data.get('errorMessage', 'unknown error')}"
            )
        return data

    # ---- Quote (read-only estimation) ----

    def get_quote(
        self,
        src_token: str,
        dst_token: str,
        amount: int,
        *,
        prepend_operating_expenses: bool = True,
    ) -> Dict[str, Any]:
        """Estimate a cross-chain swap without building a transaction.

        ``amount`` is the source-token amount in its smallest unit (wei).
        Returns the DLN ``estimation`` payload (expected output, fees, etc.).
        """
        params = {
            "srcChainId": self.src_chain_id,
            "srcChainTokenIn": src_token,
            "srcChainTokenInAmount": str(amount),
            "dstChainId": self.dst_chain_id,
            "dstChainTokenOut": dst_token,
            "prependOperatingExpenses": str(prepend_operating_expenses).lower(),
        }
        return self._get("dln/order/quote", params)

    # ---- Create order (estimation + tx, then broadcast) ----

    def create_order(
        self,
        src_token: str,
        dst_token: str,
        amount: int,
        *,
        recipient: Optional[str] = None,
        order_authority: Optional[str] = None,
        from_addr: Optional[str] = None,
        private_key: Optional[str] = None,
        send: bool = True,
    ) -> Dict[str, Any]:
        """Create a DLN cross-chain order and (optionally) broadcast its tx.

        ``recipient`` / ``order_authority`` default to the signer address. When
        ``send`` is False the prepared ``estimation`` + ``tx`` are returned
        without broadcasting (useful for dry runs and tests).
        """
        from_addr = from_addr or get_address(private_key)
        recipient = recipient or from_addr
        order_authority = order_authority or from_addr

        params = {
            "srcChainId": self.src_chain_id,
            "srcChainTokenIn": src_token,
            "srcChainTokenInAmount": str(amount),
            "dstChainId": self.dst_chain_id,
            "dstChainTokenOut": dst_token,
            "dstChainTokenOutRecipient": recipient,
            "srcChainOrderAuthorityAddress": from_addr,
            "dstChainOrderAuthorityAddress": order_authority,
            "prependOperatingExpenses": "true",
        }
        order = self._get("dln/order/create-tx", params)

        tx_data = order.get("tx") or {}
        if not send:
            return {"status": "prepared", "estimation": order.get("estimation"), "tx": tx_data}

        if not tx_data.get("to"):
            raise DeBridgeError("DLN response did not include a transaction to send")

        receipt = build_and_send_tx(
            chain_id=self.src_chain_id,
            to=tx_data["to"],
            data=bytes.fromhex(str(tx_data.get("data", "0x")).replace("0x", "")),
            value=int(tx_data.get("value", 0) or 0),
            private_key=private_key,
        )
        return {
            "status": "sent",
            "estimation": order.get("estimation"),
            "orderId": order.get("orderId"),
            "tx": receipt,
        }
