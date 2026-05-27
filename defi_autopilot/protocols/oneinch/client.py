"""
1inch DEX Aggregator Client

Uses the 1inch Swap API (v6.0) to find optimal swap routes across multiple DEXes.
No contract interaction needed — pure REST API.

API docs: https://docs.1inch.io/docs/swap-api/v6.0/
"""

from typing import Optional, Dict, Any

import httpx

from defi_autopilot.core.signer import get_address
from defi_autopilot.core.tx import build_and_send_tx


# 1inch API base URL (free tier)
INCH_API_BASE = "https://api.1inch.dev/swap/v6.0"

# Chain ID to 1inch chain mapping
INCH_CHAIN_IDS = {
    1: 1,       # Ethereum
    8453: 8453, # Base
    42161: 42161,  # Arbitrum
    10: 10,     # Optimism
    137: 137,   # Polygon
}

# Common token addresses on Base
BASE_TOKENS_INCH = {
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "WETH": "0x4200000000000000000000000000000000000006",
    "cbBTC": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
    "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    "USDbC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",
    # Native ETH (1inch uses zero address)
    "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
}


class OneInchClient:
    """1inch DEX Aggregator Client (REST API)"""

    def __init__(self, chain_id: int = 8453, api_key: Optional[str] = None):
        self.chain_id = chain_id
        self._api_key = api_key

        if chain_id not in INCH_CHAIN_IDS:
            raise ValueError(f"1inch does not support chain {chain_id}")

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _url(self, endpoint: str) -> str:
        return f"{INCH_API_BASE}/{self.chain_id}/{endpoint}"

    # ---- Quote ----

    def get_quote(
        self,
        src: str,
        dst: str,
        amount: int,
        fee: float = 0.0,
    ) -> Dict[str, Any]:
        """Get a swap quote (no gas, no route data)."""
        params = {
            "src": src,
            "dst": dst,
            "amount": amount,
        }
        if fee > 0:
            params["fee"] = int(fee * 100)  # fee in basis points (1 = 0.01%)

        resp = httpx.get(
            self._url("quote"),
            params=params,
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    # ---- Swap ----

    def get_swap(
        self,
        src: str,
        dst: str,
        amount: int,
        from_addr: Optional[str] = None,
        slippage: float = 1.0,
        fee: float = 0.0,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get swap data and execute the transaction.

        Args:
            src: Source token address
            dst: Destination token address
            amount: Amount in wei
            from_addr: Sender address (defaults to signer)
            slippage: Max slippage in percent (default 1%)
            fee: Fee in percent (default 0)
            private_key: Private key for signing

        Returns:
            Transaction result dict
        """
        from_addr = from_addr or get_address(private_key)

        params = {
            "src": src,
            "dst": dst,
            "amount": amount,
            "from": from_addr,
            "slippage": slippage,
        }
        if fee > 0:
            params["fee"] = int(fee * 100)

        resp = httpx.get(
            self._url("swap"),
            params=params,
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        swap_data = resp.json()

        # Execute the swap transaction
        tx_data = swap_data.get("tx", {})
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=tx_data["to"],
            data=bytes.fromhex(tx_data["data"].replace("0x", "")),
            value=int(tx_data.get("value", 0)),
            gas_limit=int(tx_data.get("gas", 0)) or None,
            private_key=private_key,
        )

    # ---- Approve Spender ----

    def get_spender(self) -> str:
        """Get the 1inch router address (for approval)."""
        resp = httpx.get(
            self._url("approve/spender"),
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["address"]

    # ---- Token Info ----

    def get_tokens(self) -> Dict[str, Any]:
        """Get all supported tokens for the chain."""
        resp = httpx.get(
            self._url("tokens"),
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
