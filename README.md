# defi-autopilot

> Multi-chain, multi-protocol DeFi automation toolkit

<p align="center">
  <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <a href="https://github.com/counterfactual5/defi-autopilot/actions/workflows/test.yml"><img src="https://github.com/counterfactual5/defi-autopilot/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
</p>

Supply, borrow, repay, collateral management, and DEX aggregation — all from one CLI. Extensible protocol architecture with Morpho Blue, Moonwell, Aave V3, and 1inch.

## Architecture

```
defi-autopilot/
├── defi_autopilot/
│   ├── core/              # Shared infrastructure
│   │   ├── chains.py      # Multi-chain configuration
│   │   ├── rpc.py         # Web3 instance management
│   │   ├── signer.py      # Transaction signer
│   │   └── tx.py          # TX build/sign/broadcast + ERC20 approval
│   ├── protocols/
│   │   ├── morpho/        # Morpho Blue (isolated lending markets)
│   │   ├── moonwell/      # Moonwell (Compound V2 fork)
│   │   ├── aave/          # Aave V3 (lending)
│   │   ├── uniswap/       # Uniswap V3 (DEX)
│   │   ├── oneinch/       # 1inch (DEX aggregator)
│   │   ├── lido/          # Lido (liquid staking)
│   │   ├── compound/      # Compound V3 (lending)
│   │   ├── curve/         # Curve Finance (DEX)
│   │   └── cctp/          # Circle CCTP (cross-chain USDC, resumable)
│   └── cli.py             # Click CLI entry point
└── tests/
```

## Supported Protocols

| Protocol | Type | Chains | Operations |
|----------|------|--------|------------|
| **Morpho Blue** | Isolated Lending | Base, Ethereum, Arbitrum | supply, supplyCollateral, borrow, repay, withdraw, withdrawCollateral |
| **Moonwell** | Lending (Compound V2) | Base | supply(mint), redeem, borrow, repayBorrow |
| **Aave V3** | Lending | Base, Ethereum, Arbitrum, Optimism, Polygon | supply, withdraw, borrow, repay, collateral toggle |
| **Uniswap V3** | DEX | Base, Ethereum, Arbitrum, Optimism, Polygon, Unichain | quote, swap, price |
| **1inch** | DEX Aggregator | Base, Ethereum, Arbitrum, Optimism, Polygon | quote, swap |
| **Lido** | Liquid Staking | Ethereum, Base, Arbitrum, Optimism, Polygon | stake ETH, wrap/unwrap stETH/wstETH |
| **Compound V3** | Lending | Ethereum, Base, Arbitrum, Polygon | supply, withdraw, supplyCollateral, borrow, repay |
| **Curve** | Stablecoin DEX | Ethereum, Base, Arbitrum, Optimism | swap, add/remove liquidity, quote |
| **Circle CCTP** | Cross-chain USDC bridge | Ethereum, Optimism, Arbitrum, Base, Polygon, Unichain, Avalanche | transfer (burn→attest→mint), resumable |

## Quick Start

### Install

```bash
pip install defi-autopilot
```

Or from source:

```bash
git clone https://github.com/counterfactual5/defi-autopilot.git
cd defi-autopilot
pip install -e .
```

### Configure

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
# RPC endpoints
RPC_BASE=https://mainnet.base.org
RPC_ETHEREUM=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
RPC_ARBITRUM=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY

# Signer private key (never commit to Git)
SIGNER_PRIVATE_KEY=***

# Optional: 1inch API key (free tier works without it)
INCH_API_KEY=
```

### Usage

```bash
# List all available markets
defi markets

# --- Morpho Blue ---
defi morpho position --market USDC-WETH-77
defi morpho supply --market USDC-WETH-77 --amount 1000000000
defi morpho supply-collateral --market USDC-WETH-77 --amount 500000000000000000
defi morpho borrow --market USDC-WETH-77 --amount 500000000
defi morpho repay --market USDC-WETH-77 --amount 500000000
defi morpho withdraw --market USDC-WETH-77 --amount 1000000000

# --- Moonwell ---
defi moonwell supply --token USDC --amount 1000000000
defi moonwell borrow --token WETH --amount 500000000000000000
defi moonwell repay --token WETH --amount 500000000000000000
defi moonwell position --token USDC

# --- Aave V3 ---
defi aave supply --asset USDC --amount 1000000000
defi aave borrow --asset WETH --amount 500000000000000000
defi aave repay --asset WETH
defi aave position

# --- Uniswap V3 ---
defi uniswap quote --in USDC --out WETH --amount 1000000000
defi uniswap swap --in USDC --out WETH --amount 1000000000
defi uniswap price --in WETH --out USDC

# --- 1inch ---
defi inch quote --src USDC --dst WETH --amount 1000000000
defi inch swap --src USDC --dst WETH --amount 1000000000 --slippage 1.0

# --- Circle CCTP (native cross-chain USDC) ---
defi cctp domains                                    # list supported chains + domain IDs
# Burn 10 USDC on Base (-c 8453) and mint on Arbitrum (--to 42161).
# Amount is in USDC base units (6 decimals): 10 USDC = 10000000
defi -c 8453 cctp transfer --to 42161 --amount 10000000 --run-id move-usdc-1
defi cctp status --run-id move-usdc-1                 # inspect checkpoint
# Interrupted mid-flight? Re-run the SAME command — it resumes at attest/mint,
# never re-burning.
defi -c 8453 cctp transfer --to 42161 --amount 10000000 --run-id move-usdc-1

# --- General ---
defi -c 1 morpho position --market ...  # specify chain
defi --dry-run morpho supply ...         # simulate only
```

## SDK Usage

```python
from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS
from defi_autopilot.protocols.moonwell import MoonwellClient
from defi_autopilot.protocols.aave import AaveV3Client, BASE_TOKENS_AAVE
from defi_autopilot.protocols.oneinch import OneInchClient, BASE_TOKENS_INCH

# Morpho Blue
morpho = MorphoClient(8453)
result = morpho.supply(BASE_MARKETS["USDC-WETH-77"], amount=1000000000)

# Moonwell
moonwell = MoonwellClient(8453)
result = moonwell.supply("USDC", amount=1000000000)

# Aave V3
aave = AaveV3Client(8453)
result = aave.supply(BASE_TOKENS_AAVE["USDC"], amount=1000000000)
health = aave.get_user_account_data("0xYourAddress")

# 1inch
inch = OneInchClient(8453)
quote = inch.get_quote(
    BASE_TOKENS_INCH["USDC"],
    BASE_TOKENS_INCH["WETH"],
    amount=1000000000,
)

# Circle CCTP — native cross-chain USDC, resumable via state machine
from defi_autopilot.protocols.cctp import CCTPClient

cctp = CCTPClient(8453)  # source = Base
result = cctp.transfer(
    amount=10_000_000,        # 10 USDC (6 decimals)
    dest_chain_id=42161,      # Arbitrum
    run_id="move-usdc-1",     # re-run with same id to resume after a crash
)
# {"status": "completed", "burn_tx": ..., "mint_tx": ...}
```

## 🛠️ Development

```bash
git clone https://github.com/counterfactual5/defi-autopilot.git
cd defi-autopilot
uv pip install -e ".[dev]"
uv run pytest tests/ -v
```

40 tests covering chain config, market params, ABI validation, client initialization, and token mappings.

## 🗺️ Roadmap

- [x] Morpho Blue lending operations
- [x] Moonwell supply/borrow/repay
- [x] Aave V3 lending + health factor
- [x] 1inch DEX aggregation
- [x] Multi-chain (Base, Ethereum, Arbitrum, Optimism, Polygon)
- [x] Compound V3 integration
- [x] Circle CCTP cross-chain USDC (resumable burn & mint)
- [ ] Uniswap V3/V4 LP management
- [ ] Strategy automation (auto-compound, yield optimization)
- [ ] Position monitoring & alerting
- [ ] WebSocket support for real-time data

## Security

- Private keys loaded from environment variables (never hardcoded)
- Transactions require explicit amounts (no default all-in operations)
- Gas estimation with 10% buffer
- EIP-1559 fee auto-fetch

## License

MIT
