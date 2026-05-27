"""Aave V3 Protocol Module"""

from .client import (
    AaveV3Client,
    AAVE_V3_POOLS,
    AAVE_V3_POOL_ABI,
    BASE_TOKENS_AAVE,
    INTEREST_RATE_VARIABLE,
    INTEREST_RATE_STABLE,
)

__all__ = [
    "AaveV3Client",
    "AAVE_V3_POOLS",
    "AAVE_V3_POOL_ABI",
    "BASE_TOKENS_AAVE",
    "INTEREST_RATE_VARIABLE",
    "INTEREST_RATE_STABLE",
]
