# Changelog

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

[0.1.0]: https://github.com/counterfactual5/defi-autopilot/releases/tag/v0.1.0
