"""defi-autopilot core RPC management module"""

import logging
from typing import Dict, Optional

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from .chains import ChainConfig, CHAIN_PRESETS, _RPC_ENV_KEYS

_log = logging.getLogger(__name__)

# Cache of initialized Web3 instances
_w3_instances: Dict[int, Web3] = {}

# Default retry policy for RPC providers:
# - 3 attempts with exponential backoff (0.5s → 1s → 2s)
# - Retry on connection errors, 429 (rate-limit), and 5xx server errors
# - Respect Retry-After header on 429s
_RPC_RETRY = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    respect_retry_after_header=True,
    allowed_methods=["POST"],  # JSON-RPC is always POST
)


def get_w3(chain_id: int, rpc_url: Optional[str] = None) -> Web3:
    """Get Web3 instance for the specified chain (singleton cache)"""
    if chain_id in _w3_instances and rpc_url is None:
        return _w3_instances[chain_id]

    config = CHAIN_PRESETS.get(chain_id)
    if config is None:
        raise ValueError(f"Unsupported chain ID: {chain_id}")

    url = rpc_url or config.rpc_url
    if not url:
        raise ValueError(
            f"Chain {config.name} (ID={chain_id}) has no RPC URL configured. "
            f"Set the {_RPC_ENV_KEYS.get(chain_id, 'RPC_URL')} environment variable "
            f"or pass rpc_url explicitly."
        )

    provider = Web3.HTTPProvider(url)
    # Inject retry logic into the underlying requests Session.
    session = provider._request_session_manager.cache_and_return_session(url)
    adapter = HTTPAdapter(max_retries=_RPC_RETRY)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    w3 = Web3(provider)

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
