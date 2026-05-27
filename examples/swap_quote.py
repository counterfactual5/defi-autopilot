#!/usr/bin/env python3
"""Get a 1inch swap quote and compare with market rate.

Usage:
    python examples/swap_quote.py <src_token> <dst_token> <amount>

Example:
    python examples/swap_quote.py USDC WETH 1000000000

Environment:
    INCH_API_KEY  — optional, free tier works without it
"""

import os
import sys

from defi_autopilot.protocols.oneinch import OneInchClient, BASE_TOKENS_INCH
from defi_autopilot.core.rpc import get_w3


def main():
    if len(sys.argv) < 4:
        print(f"Usage: python {sys.argv[0]} <src_token> <dst_token> <amount>")
        print(f"Example: python {sys.argv[0]} USDC WETH 1000000000")
        print(f"\nAvailable tokens on Base: {', '.join(BASE_TOKENS_INCH.keys())}")
        sys.exit(1)

    src = sys.argv[1].upper()
    dst = sys.argv[2].upper()
    amount = int(sys.argv[3])

    src_addr = BASE_TOKENS_INCH.get(src)
    dst_addr = BASE_TOKENS_INCH.get(dst)

    if not src_addr:
        print(f"❌ Unknown source token: {src}")
        sys.exit(1)
    if not dst_addr:
        print(f"❌ Unknown dest token: {dst}")
        sys.exit(1)

    chain_id = 8453  # Base
    client = OneInchClient(chain_id)

    quote = client.get_quote(src_addr, dst_addr, amount)

    src_amount = float(amount) / (10**18 if src == "WETH" else 10**6)
    dst_amount = float(quote.get("toAmount", 0)) / (10**18 if dst == "WETH" else 10**6)

    print(f"💱 1inch Swap Quote (Base)")
    print(f"   {src}: {src_amount:,.6f}")
    print(f"     → {dst}: {dst_amount:,.6f}")
    print(f"   Estimated gas: {quote.get('estimatedGas', '?')}")
    print()

    if "protocols" in quote:
        print(f"   Route:")
        for p in quote["protocols"][0][0]:
            print(f"     {p['name']}: {p['part']:.0%} via {p.get('fromTokenAddress', '?')[:10]}")

    print()
    print("💡 To execute: defi inch swap --src USDC --dst WETH --amount 1000000000 --slippage 1.0")


if __name__ == "__main__":
    main()
