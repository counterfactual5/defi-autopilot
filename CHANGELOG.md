# Changelog

## [0.3.1] — 2026-05-27

### Added
- Shared token registry (`core/tokens.py`) across all protocols
- Core tests: `test_rpc.py`, `test_tokens.py`, `test_tx.py`

### Fixed
- Missing imports in `defi markets` command (BASE_TOKENS_UNI, BASE_MARKETS, BASE_MOONWELL)
- Unused variable cleanup in aave and uniswap clients
- Version bump consistency across pyproject.toml + `__init__.py`

## [0.3.0] — 2026-05-27

### Added
- **Lido**: stake ETH, wrap/unwrap stETH/wstETH across 5 chains
- **Compound V3**: supply, withdraw, borrow, supplyCollateral, claim rewards
- **Curve**: swap, quote, add/remove liquidity via router

## [0.2.0] — 2026-05-27

### Added
- **Uniswap V3**: quote, swap, price via Trading API across 6 chains
- Chain: Unichain support

## [0.1.0] — 2026-05-27

### Added
- Core infrastructure: RPC management, EIP-1559 transaction signing/broadcasting, ERC20 approval
- Morpho Blue: supply, supplyCollateral, borrow, repay, withdraw, withdrawCollateral, position queries
- Moonwell (Compound V2): supply (mint), redeem, borrow, repayBorrow
- Aave V3: supply, withdraw, borrow, repay, collateral toggle, health factor queries
- 1inch: swap quote and execution with slippage control
- Multi-chain: Base, Ethereum, Arbitrum, Optimism, Polygon
- Click CLI with Rich output: `defi morpho supply`, `defi aave borrow`, `defi inch swap`
- Dry-run mode for all operations
- 40 tests covering market params, ABIs, client init, chain validation, and token mappings
- MIT License

[0.3.1]: https://github.com/counterfactual5/defi-autopilot/releases/tag/v0.3.1
[0.3.0]: https://github.com/counterfactual5/defi-autopilot/releases/tag/v0.3.0
[0.2.0]: https://github.com/counterfactual5/defi-autopilot/releases/tag/v0.2.0
[0.1.0]: https://github.com/counterfactual5/defi-autopilot/releases/tag/v0.1.0
