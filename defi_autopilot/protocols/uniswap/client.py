"""
Uniswap V3 Protocol Client

Interacts with Uniswap V3 via the Trading API (swap-api) for quoting and swapping.
Supports 6 chains: Base, Ethereum, Arbitrum, Optimism, Polygon, Unichain.

No dependency on OpenClaw runtime — standalone client.
"""

from typing import Optional, Dict, Any

import httpx

from defi_autopilot.core.rpc import get_w3, get_chain_config
from defi_autopilot.core.signer import get_address
from defi_autopilot.core.tx import build_and_send_tx, check_allowance, approve_token


# Uniswap Swap API base URL
UNISWAP_API_BASE = "https://swap-api.uniswap.org/v2"

# Supported chain IDs
UNISWAP_CHAIN_IDS = {
    1: 1,        # Ethereum
    8453: 8453,  # Base
    42161: 42161,  # Arbitrum
    10: 10,      # Optimism
    137: 137,    # Polygon
    130: 130,    # Unichain
}

# Common token addresses on Base
BASE_TOKENS_UNI = {
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "WETH": "0x4200000000000000000000000000000000000006",
    "cbBTC": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
    "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    "USDbC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",
    # Native ETH
    "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
}

# Ethereum mainnet tokens
ETH_TOKENS_UNI = {
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
}

# Uniswap Universal Router addresses per chain
UNIVERSAL_ROUTER = {
    1: "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
    8453: "0x6fF5693b99212Da162ad36493DdF5e268C2E624a",
    42161: "0x6fF5693b99212Da162ad36493DdF5e268C2E624a",
    10: "0x6fF5693b99212Da162ad36493DdF5e268C2E624a",
    137: "0x4c60051384bd2d3c01bfc845cf5f4b44bcbe9de5",
    130: "0x6fF5693b99212Da162ad36493DdF5e268C2E624a",
}

# Token resolver for chain
CHAIN_TOKENS = {
    8453: BASE_TOKENS_UNI,
    1: ETH_TOKENS_UNI,
}


class UniswapClient:
    """Uniswap V3 Protocol Client (via Trading API)"""

    def __init__(self, chain_id: int = 8453):
        self.chain_id = chain_id
        self.config = get_chain_config(chain_id)
        self.w3 = get_w3(chain_id)

        if chain_id not in UNISWAP_CHAIN_IDS:
            raise ValueError(f"Uniswap does not support chain {chain_id}")

        self._router = UNIVERSAL_ROUTER.get(chain_id, "")

    def _get_token_address(self, token: str) -> str:
        """Resolve token name to address."""
        tokens = CHAIN_TOKENS.get(self.chain_id, {})
        return tokens.get(token.upper(), token)

    # ---- Quote ----

    def get_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        slippage_bps: int = 100,  # 100 = 1%
    ) -> Dict[str, Any]:
        """
        Get a swap quote from Uniswap Trading API.

        Args:
            token_in: Input token address or name
            token_out: Output token address or name
            amount_in: Amount in wei
            slippage_bps: Max slippage in basis points (100 = 1%)

        Returns:
            Quote response with amount out, gas estimate, route
        """
        token_in_addr = self._get_token_address(token_in)
        token_out_addr = self._get_token_address(token_out)

        params = {
            "tokenInAddress": token_in_addr,
            "tokenOutAddress": token_out_addr,
            "amount": str(amount_in),
            "chainId": self.chain_id,
            "type": "EXACT_INPUT",
        }

        resp = httpx.get(
            f"{UNISWAP_API_BASE}/quote",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    # ---- Swap ----

    def swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        slippage_bps: int = 100,
        recipient: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a swap on Uniswap V3.

        Args:
            token_in: Input token address or name
            token_out: Output token address or name
            amount_in: Amount in wei
            slippage_bps: Max slippage in basis points
            recipient: Output recipient (defaults to signer)
            private_key: Private key for signing

        Returns:
            Transaction result dict
        """
        signer_addr = get_address(private_key)
        recipient = recipient or signer_addr

        token_in_addr = self._get_token_address(token_in)
        token_out_addr = self._get_token_address(token_out)

        # Get quote first
        _ = self.get_quote(token_in_addr, token_out_addr, amount_in, slippage_bps)

        # Get swap data
        swap_params = {
            "tokenInAddress": token_in_addr,
            "tokenOutAddress": token_out_addr,
            "amount": str(amount_in),
            "chainId": self.chain_id,
            "type": "EXACT_INPUT",
            "slippage": slippage_bps,
            "recipient": recipient,
        }

        resp = httpx.get(
            f"{UNISWAP_API_BASE}/swap",
            params=swap_params,
            timeout=15,
        )
        resp.raise_for_status()
        swap_data = resp.json()

        # Handle approval if needed (ERC20 → Universal Router)
        if token_in_addr != "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
            allowance = check_allowance(
                self.chain_id, token_in_addr, signer_addr, self._router
            )
            if allowance < amount_in:
                approve_token(
                    self.chain_id, token_in_addr,
                    self._router, 2**256 - 1,
                    private_key,
                )

        # Execute the swap transaction
        tx = swap_data.get("tx", {})
        tx_data = tx.get("data", "")
        if tx_data.startswith("0x"):
            tx_data = tx_data[2:]

        return build_and_send_tx(
            chain_id=self.chain_id,
            to=tx.get("to", self._router),
            data=bytes.fromhex(tx_data) if tx_data else b"",
            value=int(tx.get("value", 0)),
            gas_limit=int(tx.get("gas", 0)) or None,
            private_key=private_key,
        )

    # ---- Price Check ----

    def get_price(
        self,
        token_in: str,
        token_out: str,
        amount_in: int = 10**18,
    ) -> float:
        """Get approximate price of token_in in terms of token_out."""
        quote = self.get_quote(token_in, token_out, amount_in)
        amount_out = int(quote.get("quote", "0"))
        return amount_out / amount_in if amount_in > 0 else 0
