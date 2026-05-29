# Changelog

## [0.8.1] — 2026-05-29

### Added
- **RPC retry/backoff**: `get_w3` mounts a retry-capable HTTP adapter — 3
  attempts with exponential backoff on connection errors, HTTP 429, and 5xx,
  respecting `Retry-After`.
- **Configurable receipt timeout**: `TX_RECEIPT_TIMEOUT` env var (default 120s)
  overrides how long `build_and_send_tx` waits for a receipt.
- Tests for retry policy and timeout env parsing (167 tests total).

## [0.8.0] — 2026-05-29

### Added
- **estimateGas simulation gate**: a reverting tx is caught at gas estimation,
  logged as a `simulation_failed` audit event with the revert reason, before
  any broadcast or gas spend.
- **Gas-balance preflight**: a zero-native-balance signer is rejected with a
  `no_gas` audit event before estimation.

## [0.7.1] — 2026-05-29

### Added
- **Top-level `defi doctor`**: preflight a chain/wallet (RPC, chainId, signer,
  gas balance, optional policy) sharing the CCTP doctor report shape.

## [0.7.0] — 2026-05-28

### Added
- **ERC-20 policy gate** (`enforce_token_policy`): `max_amount` enforced on
  token notionals in Aave/Morpho/Compound supply/borrow.
- **CCTP V2** client (Fast/Standard transfers) alongside V1, plus
  `cctp doctor` preflight and richer attestation observability.

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
