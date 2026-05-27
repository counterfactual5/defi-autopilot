"""defi-autopilot core chain configuration"""

from dataclasses import dataclass, field
from typing import Dict

# Multi-chain RPC endpoints (read from environment variables or .env)
CHAIN_CONFIG: Dict[int, "ChainConfig"] = {}

@dataclass
class ChainConfig:
    """Configuration for a single chain"""
    chain_id: int
    name: str
    rpc_url: str
    explorer_url: str
    native_token: str
    # Protocol addresses
    morpho_blue: str = "0xBBBBBBBBB9cC5e90e3b3af64bdAF62C37EEFFcBb"
    moonwell_comptroller: str = ""

# Preset chain configurations
CHAIN_PRESETS = {
    8453: ChainConfig(
        chain_id=8453,
        name="Base",
        rpc_url="",  # Filled from .env
        explorer_url="https://basescan.org",
        native_token="ETH",
        morpho_blue="0xBBBBBBBBB9cC5e90e3b3af64bdAF62C37EEFFcBb",
        moonwell_comptroller="0xfBb21d038542BA6Dc083e0E6e5aF33a7A7eA698F",
    ),
    1: ChainConfig(
        chain_id=1,
        name="Ethereum",
        rpc_url="",
        explorer_url="https://etherscan.io",
        native_token="ETH",
        morpho_blue="0xBBBBBBBBB9cC5e90e3b3af64bdAF62C37EEFFcBb",
    ),
    42161: ChainConfig(
        chain_id=42161,
        name="Arbitrum",
        rpc_url="",
        explorer_url="https://arbiscan.io",
        native_token="ETH",
        morpho_blue="0xBBBBBBBBB9cC5e90e3b3af64bdAF62C37EEFFcBb",
    ),
    10: ChainConfig(
        chain_id=10,
        name="Optimism",
        rpc_url="",
        explorer_url="https://optimistic.etherscan.io",
        native_token="ETH",
    ),
    137: ChainConfig(
        chain_id=137,
        name="Polygon",
        rpc_url="",
        explorer_url="https://polygonscan.com",
        native_token="MATIC",
    ),
}
