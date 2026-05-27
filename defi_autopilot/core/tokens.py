"""
Shared token address registry.

All protocol modules reference these addresses instead of duplicating them.
Single source of truth — update here, all protocols see the change.
"""

from web3 import Web3


def _chain_tokens(mapping: dict) -> dict:
    """Ensure all addresses are checksummed."""
    return {k: Web3.to_checksum_address(v) for k, v in mapping.items()}


# ============================================================
# Native ETH (used by 1inch, Uniswap, Curve)
# ============================================================
NATIVE_ETH = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"

# ============================================================
# Ethereum Mainnet
# ============================================================
ETH_TOKENS = _chain_tokens({
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    "stETH": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
    "wstETH": "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0",
    "ETH": NATIVE_ETH,
})

# ============================================================
# Base
# ============================================================
BASE_TOKENS = _chain_tokens({
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "WETH": "0x4200000000000000000000000000000000000006",
    "cbBTC": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
    "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    "USDbC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",
    "wstETH": "0xc1CBa3fCea347f7fDCaB627dA9aF9e97D0e01e7D",
    "GHO": "0x9eA346d24BAe85E1350521b3293e718180B014E2",
    "EURC": "0x60a3E35Cc302bFA44Cb288Bc5a4F316Fdb1adb42",
    "ETH": NATIVE_ETH,
})

# ============================================================
# Arbitrum
# ============================================================
ARB_TOKENS = _chain_tokens({
    "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    "USDT": "0xFd086bD7e825dcE0D0f7a02b84D9EFA4BB76c2A9",
    "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    "WBTC": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
    "wstETH": "0x5979D7b546E38E414F7E9822514be443A4800529",
    "ETH": NATIVE_ETH,
})

# ============================================================
# Optimism
# ============================================================
OP_TOKENS = _chain_tokens({
    "USDC": "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",
    "USDT": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
    "WETH": "0x4200000000000000000000000000000000000006",
    "wstETH": "0x1F32b1c2345538c0c6f582fCB022739c4A194Ebb",
    "ETH": NATIVE_ETH,
})

# ============================================================
# Polygon
# ============================================================
POLY_TOKENS = _chain_tokens({
    "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
    "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
    "WBTC": "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
    "wstETH": "0x03b54A6e9a984069379fae1a4fC4dBAE93B9BD0B",
    "ETH": NATIVE_ETH,
})

# ============================================================
# Unichain
# ============================================================
UNI_TOKENS = _chain_tokens({
    "ETH": NATIVE_ETH,
})

# ============================================================
# Lookup helper
# ============================================================
CHAIN_TOKENS = {
    1: ETH_TOKENS,
    8453: BASE_TOKENS,
    42161: ARB_TOKENS,
    10: OP_TOKENS,
    137: POLY_TOKENS,
    130: UNI_TOKENS,
}


def get_token_address(chain_id: int, name: str) -> str:
    """Resolve token name to checksummed address on a given chain."""
    tokens = CHAIN_TOKENS.get(chain_id, {})
    addr = tokens.get(name.upper())
    if addr is None:
        raise ValueError(f"Token '{name}' not found on chain {chain_id}")
    return addr
