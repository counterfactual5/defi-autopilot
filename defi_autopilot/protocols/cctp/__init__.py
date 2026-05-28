"""Circle CCTP V1 — native cross-chain USDC transfers (burn & mint)."""

from .client import (
    ATTESTATION_API,
    CCTP_DOMAINS,
    MESSAGE_TRANSMITTER,
    TOKEN_MESSENGER,
    USDC_ADDRESSES,
    USDC_DECIMALS,
    CCTPClient,
    address_to_bytes32,
)

__all__ = [
    "ATTESTATION_API",
    "CCTP_DOMAINS",
    "CCTPClient",
    "MESSAGE_TRANSMITTER",
    "TOKEN_MESSENGER",
    "USDC_ADDRESSES",
    "USDC_DECIMALS",
    "address_to_bytes32",
]
