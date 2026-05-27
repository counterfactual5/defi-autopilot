"""defi-autopilot signer management"""

import os
from typing import Optional
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3


def get_signer(private_key: Optional[str] = None) -> LocalAccount:
    """
    Get the signing account.
    Uses the provided private_key first, otherwise reads SIGNER_PRIVATE_KEY from environment.
    """
    key = private_key or os.environ.get("SIGNER_PRIVATE_KEY")
    if not key:
        raise ValueError("No private key provided (via argument or SIGNER_PRIVATE_KEY env var)")

    if not key.startswith("0x"):
        key = "0x" + key

    return Account.from_key(key)


def get_address(private_key: Optional[str] = None) -> str:
    """Get the signer address (checksummed)"""
    signer = get_signer(private_key)
    return Web3.to_checksum_address(signer.address)
