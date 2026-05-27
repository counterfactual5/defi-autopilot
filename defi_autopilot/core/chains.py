"""defi-autopilot 核心链配置"""

from dataclasses import dataclass, field
from typing import Dict

# 多链 RPC 端点（从环境变量或 .env 读取）
CHAIN_CONFIG: Dict[int, "ChainConfig"] = {}

@dataclass
class ChainConfig:
    """单条链的配置"""
    chain_id: int
    name: str
    rpc_url: str
    explorer_url: str
    native_token: str
    # 协议地址
    morpho_blue: str = "0xBBBBBBBBB9cC5e90e3b3af64bdAF62C37EEFFcBb"
    moonwell_comptroller: str = ""

# 预置链配置
CHAIN_PRESETS = {
    8453: ChainConfig(
        chain_id=8453,
        name="Base",
        rpc_url="",  # 从 .env 填充
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
