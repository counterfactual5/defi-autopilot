"""defi-autopilot core RPC management module"""

from typing import Dict, Optional
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from .chains import ChainConfig, CHAIN_PRESETS


# Cache of initialized Web3 instances
_w3_instances: Dict[int, Web3] = {}


def get_w3(chain_id: int, rpc_url: Optional[str] = None) -> Web3:
    """Get Web3 instance for the specified chain (singleton cache)"""
    if chain_id in _w3_instances and rpc_url is None:
        return _w3_instances[chain_id]

    config = CHAIN_PRESETS.get(chain_id)
    if config is None:
        raise ValueError(f"Unsupported chain ID: {chain_id}")

    url = rpc_url or config.rpc_url
    if not url:
        raise ValueError(f"Chain {config.name} (ID={chain_id}) has no RPC URL configured")

    w3 = Web3(Web3.HTTPProvider(url))

    # Base/Polygon and other PoA chains need extra data middleware
    if chain_id in (8453, 137):
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    _w3_instances[chain_id] = w3
    return w3


def get_chain_config(chain_id: int) -> ChainConfig:
    """Get chain configuration"""
    config = CHAIN_PRESETS.get(chain_id)
    if config is None:
        raise ValueError(f"Unsupported chain ID: {chain_id}")
    return config
