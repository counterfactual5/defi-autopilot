"""Circle CCTP — native cross-chain USDC transfers (burn & mint).

Two independent integrations live here:

* ``CCTPClient``   — CCTP **V1** (legacy), event-parsing attestation flow.
* ``CCTPv2Client`` — CCTP **V2**, Fast/Standard transfers + single-call API.

They share no contracts or endpoints, so both can be used side by side.
"""

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
from .client_v2 import (
    ATTESTATION_API_V2,
    FINALITY_FAST,
    FINALITY_STANDARD,
    MESSAGE_TRANSMITTER_V2,
    TOKEN_MESSENGER_V2,
    CCTPv2Client,
)

__all__ = [
    # V1
    "ATTESTATION_API",
    "CCTP_DOMAINS",
    "CCTPClient",
    "MESSAGE_TRANSMITTER",
    "TOKEN_MESSENGER",
    "USDC_ADDRESSES",
    "USDC_DECIMALS",
    "address_to_bytes32",
    # V2
    "ATTESTATION_API_V2",
    "CCTPv2Client",
    "FINALITY_FAST",
    "FINALITY_STANDARD",
    "MESSAGE_TRANSMITTER_V2",
    "TOKEN_MESSENGER_V2",
]
