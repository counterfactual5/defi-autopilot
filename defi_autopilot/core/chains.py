"""
defi-autopilot core chain configuration

Chain presets define RPC URLs, explorer URLs, and protocol addresses.
RPC URLs are loaded from environment variables at import time.
"""

import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ChainConfig:
    """Configuration for a single chain"""
    chain_id: int
    name: str
    rpc_url: str
    explorer_url: str
    native_token: str
    # Protocol addresses
    morpho_blue: str = ""
    moonwell_comptroller: str = ""


# Mapping: chain_id → environment variable name for RPC URL
_RPC_ENV_KEYS: Dict[int, str] = {
    8453: "RPC_BASE",
    1: "RPC_ETHEREUM",
    42161: "RPC_ARBITRUM",
    10: "RPC_OPTIMISM",
    137: "RPC_POLYGON",
    130: "RPC_UNICHAIN",
}

# Default public RPC URLs (fallback when env var is not set)
_DEFAULT_RPCS: Dict[int, str] = {
    8453: "https://mainnet.base.org",
    1: "https://eth.llamarpc.com",
    42161: "https://arb1.arbitrum.io/rpc",
    10: "https://mainnet.optimism.io",
    137: "https://polygon-rpc.com",
}


def _get_rpc_url(chain_id: int) -> str:
    """Resolve RPC URL: env var > default > empty string."""
    env_key = _RPC_ENV_KEYS.get(chain_id, "")
    if env_key:
        url = os.environ.get(env_key, "")
        if url:
            return url
    return _DEFAULT_RPCS.get(chain_id, "")


# ============================================================
# Preset chain configurations
# ============================================================

CHAIN_PRESETS: Dict[int, ChainConfig] = {
    8453: ChainConfig(
        chain_id=8453,
        name="Base",
        rpc_url=_get_rpc_url(8453),
        explorer_url="https://basescan.org",
        native_token="ETH",
        morpho_blue="0xBBBBBBBBB9cC5e90e3b3af64bdAF62C37EEFFcBb",
        moonwell_comptroller="0xfBb21d038542BA6Dc083e0E6e5aF33a7A7eA698F",
    ),
    1: ChainConfig(
        chain_id=1,
        name="Ethereum",
        rpc_url=_get_rpc_url(1),
        explorer_url="https://etherscan.io",
        native_token="ETH",
        morpho_blue="0xBBBBBBBBB9cC5e90e3b3af64bdAF62C37EEFFcBb",
    ),
    42161: ChainConfig(
        chain_id=42161,
        name="Arbitrum",
        rpc_url=_get_rpc_url(42161),
        explorer_url="https://arbiscan.io",
        native_token="ETH",
        morpho_blue="0xBBBBBBBBB9cC5e90e3b3af64bdAF62C37EEFFcBb",
    ),
    10: ChainConfig(
        chain_id=10,
        name="Optimism",
        rpc_url=_get_rpc_url(10),
        explorer_url="https://optimistic.etherscan.io",
        native_token="ETH",
    ),
    137: ChainConfig(
        chain_id=137,
        name="Polygon",
        rpc_url=_get_rpc_url(137),
        explorer_url="https://polygonscan.com",
        native_token="MATIC",
    ),
}
