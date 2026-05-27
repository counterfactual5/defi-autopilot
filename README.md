# defi-autopilot

> Multi-chain, multi-protocol DeFi automation toolkit

A one-stop DeFi operations CLI covering supply, borrow, repay, collateral management, and DEX aggregation. Multi-chain deployment with extensible protocol architecture.

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
│   │   └── oneinch/       # 1inch (DEX aggregator)
│   └── cli.py             # Click CLI entry point
└── tests/
```

## Supported Protocols

| Protocol | Type | Chains | Operations |
|----------|------|--------|------------|
| **Morpho Blue** | Isolated Lending | Base, Ethereum, Arbitrum | supply, supplyCollateral, borrow, repay, withdraw, withdrawCollateral |
| **Moonwell** | Lending (Compound V2) | Base | supply(mint), redeem, borrow, repayBorrow |
| **Aave V3** | Lending | Base, Ethereum, Arbitrum, Optimism, Polygon | supply, withdraw, borrow, repay, collateral toggle |
| **1inch** | DEX Aggregator | Base, Ethereum, Arbitrum, Optimism, Polygon | quote, swap |

## Quick Start

### Install

```bash
pip install -e ".[dev]"
```

### Configure

Create a `.env` file:

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

# --- 1inch ---
defi inch quote --src USDC --dst WETH --amount 1000000000
defi inch swap --src USDC --dst WETH --amount 1000000000 --slippage 1.0

# --- General ---
defi -c 1 morpho position --market ...  # specify chain
defi --dry-run morpho supply ...         # simulate only
```

## SDK Usage

```python
from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS
from defi_autopilot.protocols.aave import AaveV3Client, BASE_TOKENS_AAVE
from defi_autopilot.protocols.oneinch import OneInchClient, BASE_TOKENS_INCH

# Morpho Blue
morpho = MorphoClient(8453)
result = morpho.supply(BASE_MARKETS["USDC-WETH-77"], amount=1000000000)

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
```

## Testing

```bash
pytest tests/ -v
```

## Security

- Private keys loaded from environment variables (never hardcoded)
- Transactions require explicit amounts (no default all-in operations)
- Gas estimation with 10% buffer
- EIP-1559 fee auto-fetch

## License

MIT
