#!/usr/bin/env python3
"""Check lending position and health factor across Morpho, Moonwell, and Aave.

Usage:
    python examples/check_positions.py 0xYourWalletAddress

Environment:
    RPC_BASE  — RPC URL for Base chain
"""

import os
import sys

from web3 import Web3
from defi_autopilot.core.rpc import get_w3, get_chain_config


def check_morpho(w3, chain, address):
    """Query Morpho Blue market positions."""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS, MorphoClient as MC
    print(f"\n  Morpho Blue ({chain['name']}):")
    try:
        client = MorphoClient(chain['chain_id'])
        for name, mp in BASE_MARKETS.items():
            try:
                pos = client.get_position(mp, address)
                supply = pos.get('supplyShares', 0)
                borrow = pos.get('borrowShares', 0)
                collateral = pos.get('collateral', 0)
                if supply or borrow or collateral:
                    print(f"    {name}: supply={supply}, borrow={borrow}, collateral={collateral}")
            except Exception:
                pass
    except Exception as e:
        print(f"    Error: {e}")


def check_aave(w3, chain, address):
    """Query Aave V3 health factor."""
    from defi_autopilot.protocols.aave import AaveV3Client
    print(f"\n  Aave V3 ({chain['name']}):")
    try:
        client = AaveV3Client(chain['chain_id'])
        data = client.get_user_account_data(address)
        health = data.get('healthFactor', '?')
        total_collateral = data.get('totalCollateralBase', '?')
        total_debt = data.get('totalDebtBase', '?')
        print(f"    Health factor: {health}")
        print(f"    Collateral: {total_collateral}  Debt: {total_debt}")
    except Exception as e:
        print(f"    Not available: {e}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <wallet_address>")
        sys.exit(1)

    address = Web3.to_checksum_address(sys.argv[1])

    # Base chain
    base = {"chain_id": 8453, "name": "Base"}
    w3 = get_w3(base["chain_id"])

    print(f"📊 DeFi Position Report: {address}")
    print(f"   Chain: {base['name']} (ID {base['chain_id']})")

    check_morpho(w3, base, address)
    check_aave(w3, base, address)

    print()


if __name__ == "__main__":
    main()
