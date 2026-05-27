"""defi-autopilot 核心 RPC 管理模块"""

from typing import Dict, Optional
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from .chains import ChainConfig, CHAIN_PRESETS


# 缓存已初始化的 Web3 实例
_w3_instances: Dict[int, Web3] = {}


def get_w3(chain_id: int, rpc_url: Optional[str] = None) -> Web3:
    """获取指定链的 Web3 实例（单例缓存）"""
    if chain_id in _w3_instances and rpc_url is None:
        return _w3_instances[chain_id]

    config = CHAIN_PRESETS.get(chain_id)
    if config is None:
        raise ValueError(f"不支持的链 ID: {chain_id}")

    url = rpc_url or config.rpc_url
    if not url:
        raise ValueError(f"链 {config.name} (ID={chain_id}) 未配置 RPC URL")

    w3 = Web3(Web3.HTTPProvider(url))

    # Base/Polygon 等 PoA 链需要 extra data middleware
    if chain_id in (8453, 137):
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    _w3_instances[chain_id] = w3
    return w3


def get_chain_config(chain_id: int) -> ChainConfig:
    """获取链配置"""
    config = CHAIN_PRESETS.get(chain_id)
    if config is None:
        raise ValueError(f"不支持的链 ID: {chain_id}")
    return config
