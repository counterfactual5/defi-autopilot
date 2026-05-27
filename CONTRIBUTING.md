# Contributing to defi-autopilot

## Setup

```bash
git clone https://github.com/counterfactual5/defi-autopilot.git
cd defi-autopilot
uv pip install -e ".[dev]"
```

No API keys needed for development — tests use mocked RPC and signer.

## Running Tests

```bash
uv run pytest tests/ -v
```

40 tests covering chain config, Morpho Blue (market params, ABI, client), Moonwell, Aave V3, and 1inch protocol clients.

## Code Style

- Python 3.10+ compatible
- Public functions have docstrings
- Addresses use `Web3.to_checksum_address()` for validation
- Protocol clients follow a consistent pattern: init with chain_id → expose operation methods

## Project Structure

```
defi_autopilot/
├── core/              # RPC, signer, tx broadcast, chain config
├── protocols/         # Protocol-specific clients
│   ├── aave/          # Aave V3 lending
│   ├── moonwell/      # Moonwell (Compound V2 fork)
│   ├── morpho/        # Morpho Blue (isolated markets)
│   └── oneinch/       # 1inch DEX aggregator
└── cli.py             # Click CLI (defi command)
```

## Adding a New Protocol

1. Create `defi_autopilot/protocols/<name>/client.py`
2. Implement a client class that takes `chain_id` in `__init__`
3. Add ABI constants and chain-specific token/market mappings
4. Add tests in `tests/protocols/test_<name>.py`
5. Register CLI commands in `cli.py`

## Pull Requests

1. Fork → feature branch → changes + tests → PR to `main`
2. Keep PRs focused — one protocol or feature per PR
