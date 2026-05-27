"""
defi-autopilot CLI entry point

Usage:
  defi morpho supply   --market USDC-WETH-77 --amount 1000
  defi morpho borrow   --market USDC-WETH-77 --amount 500
  defi morpho repay    --market USDC-WETH-77 --amount 500
  defi morpho position --market USDC-WETH-77
  defi moonwell supply --token USDC --amount 1000
  defi moonwell borrow --token USDC --amount 500
  defi moonwell repay  --token USDC --amount 500
"""

import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Load .env
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

console = Console()


# ============================================================
# Main command group
# ============================================================

@click.group()
@click.option("--chain", "-c", default=8453, type=int, help="Chain ID (default 8453 = Base)")
@click.option("--dry-run", is_flag=True, help="Simulate only, do not send transaction")
@click.pass_context
def cli(ctx, chain, dry_run):
    """🚀 DeFi Autopilot — multi-chain multi-protocol DeFi automation tool"""
    ctx.ensure_object(dict)
    ctx.obj["chain_id"] = chain
    ctx.obj["dry_run"] = dry_run


# ============================================================
# Morpho commands
# ============================================================

@cli.group()
def morpho():
    """Morpho Blue lending protocol"""
    pass


@morpho.command("supply")
@click.option("--market", "-m", required=True, help="Market name (e.g. USDC-WETH-77) or market_id")
@click.option("--amount", "-a", required=True, type=int, help="Supply amount (wei)")
@click.option("--on-behalf", type=str, default=None, help="Address to supply on behalf of")
@click.pass_context
def morpho_supply(ctx, market, amount, on_behalf):
    """Supply assets to a Morpho market"""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS

    chain_id = ctx.obj["chain_id"]
    client = MorphoClient(chain_id)

    mp = BASE_MARKETS.get(market)
    if mp is None:
        console.print(f"[red]Unknown market: {market}[/red]")
        console.print(f"Available markets: {', '.join(BASE_MARKETS.keys())}")
        sys.exit(1)

    console.print(f"[cyan]Supplying {amount} to {market} market[/cyan]")

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN — no transaction sent[/yellow]")
        info = client.get_market_info(mp)
        console.print(f"Market utilization: {info['utilization']:.2%}")
        return

    result = client.supply(mp, amount, on_behalf=on_behalf)
    _print_tx_result(result)


@morpho.command("supply-collateral")
@click.option("--market", "-m", required=True, help="Market name")
@click.option("--amount", "-a", required=True, type=int, help="Collateral amount (wei)")
@click.pass_context
def morpho_supply_collateral(ctx, market, amount):
    """Deposit collateral"""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS

    chain_id = ctx.obj["chain_id"]
    client = MorphoClient(chain_id)

    mp = BASE_MARKETS.get(market)
    if mp is None:
        console.print(f"[red]Unknown market: {market}[/red]")
        sys.exit(1)

    result = client.supply_collateral(mp, amount)
    _print_tx_result(result)


@morpho.command("borrow")
@click.option("--market", "-m", required=True, help="Market name")
@click.option("--amount", "-a", required=True, type=int, help="Borrow amount (wei)")
@click.pass_context
def morpho_borrow(ctx, market, amount):
    """Borrow from a Morpho market"""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS

    chain_id = ctx.obj["chain_id"]
    client = MorphoClient(chain_id)

    mp = BASE_MARKETS.get(market)
    if mp is None:
        console.print(f"[red]Unknown market: {market}[/red]")
        sys.exit(1)

    result = client.borrow(mp, amount)
    _print_tx_result(result)


@morpho.command("repay")
@click.option("--market", "-m", required=True, help="Market name")
@click.option("--amount", "-a", type=int, default=0, help="Repay amount (wei)")
@click.option("--shares", "-s", type=int, default=0, help="Repay shares")
@click.pass_context
def morpho_repay(ctx, market, amount, shares):
    """Repay a Morpho loan"""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS

    chain_id = ctx.obj["chain_id"]
    client = MorphoClient(chain_id)

    mp = BASE_MARKETS.get(market)
    if mp is None:
        console.print(f"[red]Unknown market: {market}[/red]")
        sys.exit(1)

    result = client.repay(mp, amount=amount, shares=shares)
    _print_tx_result(result)


@morpho.command("withdraw")
@click.option("--market", "-m", required=True, help="Market name")
@click.option("--amount", "-a", type=int, default=0, help="Withdraw amount (wei)")
@click.pass_context
def morpho_withdraw(ctx, market, amount):
    """Withdraw supplied assets"""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS

    chain_id = ctx.obj["chain_id"]
    client = MorphoClient(chain_id)

    mp = BASE_MARKETS.get(market)
    if mp is None:
        console.print(f"[red]Unknown market: {market}[/red]")
        sys.exit(1)

    result = client.withdraw(mp, amount=amount)
    _print_tx_result(result)


@morpho.command("position")
@click.option("--market", "-m", required=True, help="Market name")
@click.option("--user", "-u", type=str, default=None, help="Address to query")
@click.pass_context
def morpho_position(ctx, market, user):
    """Query Morpho position"""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS
    from defi_autopilot.core.signer import get_address

    chain_id = ctx.obj["chain_id"]
    client = MorphoClient(chain_id)

    mp = BASE_MARKETS.get(market)
    if mp is None:
        console.print(f"[red]Unknown market: {market}[/red]")
        sys.exit(1)

    user = user or get_address()
    supply_shares, borrow_shares, collateral = client.get_position(mp, user)
    info = client.get_market_info(mp)

    table = Table(title=f"Morpho Position — {market}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Supply Shares", str(supply_shares))
    table.add_row("Borrow Shares", str(borrow_shares))
    table.add_row("Collateral", str(collateral))
    table.add_row("—", "—")
    table.add_row("Total Supply", str(info["total_supply_assets"]))
    table.add_row("Total Borrow", str(info["total_borrow_assets"]))
    table.add_row("Utilization", f"{info['utilization']:.2%}")

    console.print(table)


# ============================================================
# Moonwell commands
# ============================================================

@cli.group()
def moonwell():
    """Moonwell lending protocol (Compound V2)"""
    pass


@moonwell.command("supply")
@click.option("--token", "-t", required=True, help="Token name (e.g. USDC, WETH)")
@click.option("--amount", "-a", required=True, type=int, help="Supply amount (wei)")
@click.option("--enter-market/--no-enter-market", default=True, help="Whether to enter market")
@click.pass_context
def moonwell_supply(ctx, token, amount, enter_market):
    """Supply assets to a Moonwell market"""
    from defi_autopilot.protocols.moonwell import MoonwellClient, BASE_MOONWELL

    chain_id = ctx.obj["chain_id"]
    client = MoonwellClient(chain_id)

    token_info = BASE_MOONWELL["tokens"].get(token.upper())
    if token_info is None:
        console.print(f"[red]Unknown token: {token}[/red]")
        console.print(f"Available: {', '.join(BASE_MOONWELL['tokens'].keys())}")
        sys.exit(1)

    result = client.supply(
        token_info["cToken"], amount,
        enter_market=enter_market,
    )
    _print_tx_result(result)


@moonwell.command("borrow")
@click.option("--token", "-t", required=True, help="Token name")
@click.option("--amount", "-a", required=True, type=int, help="Borrow amount (wei)")
@click.pass_context
def moonwell_borrow(ctx, token, amount):
    """Borrow from a Moonwell market"""
    from defi_autopilot.protocols.moonwell import MoonwellClient, BASE_MOONWELL

    chain_id = ctx.obj["chain_id"]
    client = MoonwellClient(chain_id)

    token_info = BASE_MOONWELL["tokens"].get(token.upper())
    if token_info is None:
        console.print(f"[red]Unknown token: {token}[/red]")
        sys.exit(1)

    result = client.borrow(token_info["cToken"], amount)
    _print_tx_result(result)


@moonwell.command("repay")
@click.option("--token", "-t", required=True, help="Token name")
@click.option("--amount", "-a", required=True, type=int, help="Repay amount (wei)")
@click.pass_context
def moonwell_repay(ctx, token, amount):
    """Repay a Moonwell loan"""
    from defi_autopilot.protocols.moonwell import MoonwellClient, BASE_MOONWELL

    chain_id = ctx.obj["chain_id"]
    client = MoonwellClient(chain_id)

    token_info = BASE_MOONWELL["tokens"].get(token.upper())
    if token_info is None:
        console.print(f"[red]Unknown token: {token}[/red]")
        sys.exit(1)

    result = client.repay(token_info["cToken"], amount)
    _print_tx_result(result)


@moonwell.command("position")
@click.option("--token", "-t", required=True, help="Token name")
@click.option("--user", "-u", type=str, default=None, help="Address to query")
@click.pass_context
def moonwell_position(ctx, token, user):
    """Query Moonwell position"""
    from defi_autopilot.protocols.moonwell import MoonwellClient, BASE_MOONWELL
    from defi_autopilot.core.signer import get_address

    chain_id = ctx.obj["chain_id"]
    client = MoonwellClient(chain_id)

    token_info = BASE_MOONWELL["tokens"].get(token.upper())
    if token_info is None:
        console.print(f"[red]Unknown token: {token}[/red]")
        sys.exit(1)

    user = user or get_address()
    supply_bal = client.get_supply_balance(token_info["cToken"], user)
    borrow_bal = client.get_borrow_balance(token_info["cToken"], user)
    liquidity = client.get_account_liquidity(user)

    table = Table(title=f"Moonwell Position — {token}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Supply Balance (cToken)", str(supply_bal))
    table.add_row("Borrow Balance", str(borrow_bal))
    table.add_row("Account Liquidity", str(liquidity["liquidity"]))
    table.add_row("Account Shortfall", str(liquidity["shortfall"]))

    console.print(table)


# ============================================================
# Uniswap V3 Commands
# ============================================================

@cli.group()
def uniswap():
    """Uniswap V3 DEX"""
    pass


@uniswap.command("quote")
@click.option("--in", "-i", "token_in", required=True, help="Input token")
@click.option("--out", "-o", "token_out", required=True, help="Output token")
@click.option("--amount", "-n", required=True, type=int, help="Amount in wei")
@click.pass_context
def uniswap_quote(ctx, token_in, token_out, amount):
    """Get swap quote from Uniswap V3"""
    from defi_autopilot.protocols.uniswap import UniswapClient

    chain_id = ctx.obj["chain_id"]
    client = UniswapClient(chain_id)

    quote = client.get_quote(token_in, token_out, amount)
    console.print(f"[green]Quote:[/green] {quote.get('quote', 'N/A')}")
    console.print(f"  Route: {quote.get('route', 'N/A')}")
    console.print(f"  Gas estimate: {quote.get('gasEstimate', 'N/A')}")


@uniswap.command("swap")
@click.option("--in", "-i", "token_in", required=True, help="Input token")
@click.option("--out", "-o", "token_out", required=True, help="Output token")
@click.option("--amount", "-n", required=True, type=int, help="Amount in wei")
@click.option("--slippage", type=int, default=100, help="Max slippage in bps (default 100 = 1%)")
@click.pass_context
def uniswap_swap(ctx, token_in, token_out, amount, slippage):
    """Execute swap on Uniswap V3"""
    from defi_autopilot.protocols.uniswap import UniswapClient

    chain_id = ctx.obj["chain_id"]
    client = UniswapClient(chain_id)

    result = client.swap(token_in, token_out, amount, slippage_bps=slippage)
    _print_tx_result(result)


@uniswap.command("price")
@click.option("--in", "-i", "token_in", required=True, help="Input token")
@click.option("--out", "-o", "token_out", required=True, help="Output token")
@click.pass_context
def uniswap_price(ctx, token_in, token_out):
    """Get token price on Uniswap"""
    from defi_autopilot.protocols.uniswap import UniswapClient

    chain_id = ctx.obj["chain_id"]
    client = UniswapClient(chain_id)

    price = client.get_price(token_in, token_out)
    console.print(f"[green]Price:[/green] 1 {token_in} = {price:.6f} {token_out}")


# ============================================================
# Aave V3 Commands
# ============================================================

@cli.group()
def aave():
    """Aave V3 lending protocol"""
    pass


@aave.command("supply")
@click.option("--asset", "-a", required=True, help="Token name (e.g. USDC, WETH)")
@click.option("--amount", "-n", required=True, type=int, help="Amount in wei")
@click.option("--collateral/--no-collateral", default=True, help="Use as collateral")
@click.pass_context
def aave_supply(ctx, asset, amount, collateral):
    """Supply assets to Aave V3 pool"""
    from defi_autopilot.protocols.aave import AaveV3Client, BASE_TOKENS_AAVE

    chain_id = ctx.obj["chain_id"]
    client = AaveV3Client(chain_id)

    token_addr = BASE_TOKENS_AAVE.get(asset.upper())
    if token_addr is None:
        console.print(f"[red]Unknown token: {asset}[/red]")
        console.print(f"Available: {', '.join(BASE_TOKENS_AAVE.keys())}")
        sys.exit(1)

    result = client.supply(token_addr, amount, use_as_collateral=collateral)
    _print_tx_result(result)


@aave.command("borrow")
@click.option("--asset", "-a", required=True, help="Token to borrow")
@click.option("--amount", "-n", required=True, type=int, help="Amount in wei")
@click.option("--stable", is_flag=True, help="Use stable rate (default: variable)")
@click.pass_context
def aave_borrow(ctx, asset, amount, stable):
    """Borrow assets from Aave V3 pool"""
    from defi_autopilot.protocols.aave import (
        AaveV3Client, BASE_TOKENS_AAVE,
        INTEREST_RATE_VARIABLE, INTEREST_RATE_STABLE,
    )

    chain_id = ctx.obj["chain_id"]
    client = AaveV3Client(chain_id)

    token_addr = BASE_TOKENS_AAVE.get(asset.upper())
    if token_addr is None:
        console.print(f"[red]Unknown token: {asset}[/red]")
        sys.exit(1)

    rate_mode = INTEREST_RATE_STABLE if stable else INTEREST_RATE_VARIABLE
    result = client.borrow(token_addr, amount, interest_rate_mode=rate_mode)
    _print_tx_result(result)


@aave.command("repay")
@click.option("--asset", "-a", required=True, help="Token to repay")
@click.option("--amount", "-n", type=int, default=2**256 - 1, help="Amount in wei (default: repay all)")
@click.pass_context
def aave_repay(ctx, asset, amount):
    """Repay borrowed assets to Aave V3"""
    from defi_autopilot.protocols.aave import AaveV3Client, BASE_TOKENS_AAVE

    chain_id = ctx.obj["chain_id"]
    client = AaveV3Client(chain_id)

    token_addr = BASE_TOKENS_AAVE.get(asset.upper())
    if token_addr is None:
        console.print(f"[red]Unknown token: {asset}[/red]")
        sys.exit(1)

    result = client.repay(token_addr, amount)
    _print_tx_result(result)


@aave.command("position")
@click.option("--user", "-u", type=str, default=None, help="Address to query")
@click.pass_context
def aave_position(ctx, user):
    """Query Aave V3 account data"""
    from defi_autopilot.protocols.aave import AaveV3Client
    from defi_autopilot.core.signer import get_address

    chain_id = ctx.obj["chain_id"]
    client = AaveV3Client(chain_id)

    user = user or get_address()
    data = client.get_user_account_data(user)

    table = Table(title=f"Aave V3 Account — Chain {chain_id}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Total Collateral (USD)", str(data["total_collateral_base"]))
    table.add_row("Total Debt (USD)", str(data["total_debt_base"]))
    table.add_row("Available Borrows (USD)", str(data["available_borrows_base"]))
    table.add_row("LTV", f"{data['ltv'] / 100:.2f}%")
    table.add_row("Health Factor", f"{data['health_factor'] / 1e18:.4f}")
    console.print(table)


# ============================================================
# 1inch Commands
# ============================================================

@cli.group()
def inch():
    """1inch DEX aggregator"""
    pass


@inch.command("quote")
@click.option("--src", "-s", required=True, help="Source token")
@click.option("--dst", "-d", required=True, help="Destination token")
@click.option("--amount", "-n", required=True, type=int, help="Amount in wei")
@click.pass_context
def inch_quote(ctx, src, dst, amount):
    """Get swap quote from 1inch"""
    from defi_autopilot.protocols.oneinch import OneInchClient, BASE_TOKENS_INCH

    chain_id = ctx.obj["chain_id"]
    client = OneInchClient(chain_id)

    src_addr = BASE_TOKENS_INCH.get(src.upper(), src)
    dst_addr = BASE_TOKENS_INCH.get(dst.upper(), dst)

    quote = client.get_quote(src_addr, dst_addr, amount)
    console.print(f"[green]Quote:[/green] {quote.get('toAmount', 'N/A')}")
    console.print(f"  SRC: {src_addr}")
    console.print(f"  DST: {dst_addr}")


@inch.command("swap")
@click.option("--src", "-s", required=True, help="Source token")
@click.option("--dst", "-d", required=True, help="Destination token")
@click.option("--amount", "-n", required=True, type=int, help="Amount in wei")
@click.option("--slippage", type=float, default=1.0, help="Max slippage %")
@click.pass_context
def inch_swap(ctx, src, dst, amount, slippage):
    """Execute swap via 1inch aggregator"""
    from defi_autopilot.protocols.oneinch import OneInchClient, BASE_TOKENS_INCH

    chain_id = ctx.obj["chain_id"]
    client = OneInchClient(chain_id)

    src_addr = BASE_TOKENS_INCH.get(src.upper(), src)
    dst_addr = BASE_TOKENS_INCH.get(dst.upper(), dst)

    result = client.get_swap(src_addr, dst_addr, amount, slippage=slippage)
    _print_tx_result(result)


# ============================================================
# Lido Commands
# ============================================================

@cli.group()
def lido():
    """Lido liquid staking"""
    pass


@lido.command("stake")
@click.option("--amount", "-n", required=True, type=int, help="ETH amount in wei")
@click.pass_context
def lido_stake(ctx, amount):
    """Stake ETH to receive stETH (Ethereum only)"""
    from defi_autopilot.protocols.lido import LidoClient

    chain_id = ctx.obj["chain_id"]
    client = LidoClient(chain_id)

    if not client.supports_native_staking:
        console.print("[red]Native staking only available on Ethereum mainnet[/red]")
        sys.exit(1)

    result = client.stake(amount)
    _print_tx_result(result)


@lido.command("wrap")
@click.option("--amount", "-n", required=True, type=int, help="stETH amount in wei")
@click.pass_context
def lido_wrap(ctx, amount):
    """Wrap stETH to wstETH"""
    from defi_autopilot.protocols.lido import LidoClient

    chain_id = ctx.obj["chain_id"]
    client = LidoClient(chain_id)
    result = client.wrap(amount)
    _print_tx_result(result)


@lido.command("unwrap")
@click.option("--amount", "-n", required=True, type=int, help="wstETH amount in wei")
@click.pass_context
def lido_unwrap(ctx, amount):
    """Unwrap wstETH to stETH"""
    from defi_autopilot.protocols.lido import LidoClient

    chain_id = ctx.obj["chain_id"]
    client = LidoClient(chain_id)
    result = client.unwrap(amount)
    _print_tx_result(result)


@lido.command("balance")
@click.option("--user", "-u", type=str, default=None, help="Address to query")
@click.pass_context
def lido_balance(ctx, user):
    """Query stETH/wstETH balance"""
    from defi_autopilot.protocols.lido import LidoClient
    from defi_autopilot.core.signer import get_address

    chain_id = ctx.obj["chain_id"]
    client = LidoClient(chain_id)
    user = user or get_address()

    table = Table(title=f"Lido Balance — Chain {chain_id}")
    table.add_column("Token", style="cyan")
    table.add_column("Balance", style="green")

    if client.supports_native_staking:
        try:
            steth = client.get_steth_balance(user)
            table.add_row("stETH", str(steth))
        except Exception:
            pass

    wsteth = client.get_wsteth_balance(user)
    rate = client.get_steth_per_wsteth()
    table.add_row("wstETH", str(wsteth))
    table.add_row("stETH/wstETH rate", str(rate))

    console.print(table)


# ============================================================
# Compound V3 Commands
# ============================================================

@cli.group()
def compound():
    """Compound V3 lending protocol"""
    pass


@compound.command("supply")
@click.option("--market", "-m", default="USDC", help="Market name (default USDC)")
@click.option("--amount", "-n", required=True, type=int, help="Amount in wei")
@click.pass_context
def compound_supply(ctx, market, amount):
    """Supply base asset to Compound V3"""
    from defi_autopilot.protocols.compound import CompoundV3Client

    chain_id = ctx.obj["chain_id"]
    client = CompoundV3Client(chain_id, market)
    result = client.supply(amount)
    _print_tx_result(result)


@compound.command("supply-collateral")
@click.option("--market", "-m", default="USDC", help="Market name")
@click.option("--asset", "-a", required=True, help="Collateral asset name (e.g. WETH)")
@click.option("--amount", "-n", required=True, type=int, help="Amount in wei")
@click.pass_context
def compound_supply_collateral(ctx, market, asset, amount):
    """Supply collateral to Compound V3"""
    from defi_autopilot.protocols.compound import CompoundV3Client

    chain_id = ctx.obj["chain_id"]
    client = CompoundV3Client(chain_id, market)
    result = client.supply_collateral(asset, amount)
    _print_tx_result(result)


@compound.command("borrow")
@click.option("--market", "-m", default="USDC", help="Market name")
@click.option("--amount", "-n", required=True, type=int, help="Amount in wei")
@click.pass_context
def compound_borrow(ctx, market, amount):
    """Borrow base asset from Compound V3"""
    from defi_autopilot.protocols.compound import CompoundV3Client

    chain_id = ctx.obj["chain_id"]
    client = CompoundV3Client(chain_id, market)
    result = client.borrow(amount)
    _print_tx_result(result)


@compound.command("repay")
@click.option("--market", "-m", default="USDC", help="Market name")
@click.option("--amount", "-n", required=True, type=int, help="Amount in wei")
@click.pass_context
def compound_repay(ctx, market, amount):
    """Repay borrowed asset to Compound V3"""
    from defi_autopilot.protocols.compound import CompoundV3Client

    chain_id = ctx.obj["chain_id"]
    client = CompoundV3Client(chain_id, market)
    result = client.repay(amount)
    _print_tx_result(result)


@compound.command("position")
@click.option("--market", "-m", default="USDC", help="Market name")
@click.option("--user", "-u", type=str, default=None, help="Address to query")
@click.pass_context
def compound_position(ctx, market, user):
    """Query Compound V3 position"""
    from defi_autopilot.protocols.compound import CompoundV3Client
    from defi_autopilot.core.signer import get_address

    chain_id = ctx.obj["chain_id"]
    client = CompoundV3Client(chain_id, market)
    user = user or get_address()

    supply_bal = client.get_supply_balance(user)
    borrow_bal = client.get_borrow_balance(user)

    table = Table(title=f"Compound V3 — {market} Market")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Supply", str(supply_bal))
    table.add_row("Borrow", str(borrow_bal))

    for coll_name in client._market["collaterals"]:
        coll_bal = client.get_collateral_balance(user, coll_name)
        table.add_row(f"Collateral ({coll_name})", str(coll_bal))

    console.print(table)


# ============================================================
# Curve Commands
# ============================================================

@cli.group()
def curve():
    """Curve Finance DEX"""
    pass


@curve.command("quote")
@click.option("--pool", "-p", required=True, help="Pool name")
@click.option("--in", "-i", "token_in", required=True, help="Input token address")
@click.option("--out", "-o", "token_out", required=True, help="Output token address")
@click.option("--amount", "-n", required=True, type=int, help="Amount in wei")
@click.pass_context
def curve_quote(ctx, pool, token_in, token_out, amount):
    """Get swap quote from Curve pool"""
    from defi_autopilot.protocols.curve import CurveClient

    chain_id = ctx.obj["chain_id"]
    client = CurveClient(chain_id, pool)
    dy = client.get_dy(token_in, token_out, amount)
    console.print(f"[green]Quote:[/green] {dy}")


@curve.command("swap")
@click.option("--pool", "-p", required=True, help="Pool name")
@click.option("--in", "-i", "token_in", required=True, help="Input token address")
@click.option("--out", "-o", "token_out", required=True, help="Output token address")
@click.option("--amount", "-n", required=True, type=int, help="Amount in wei")
@click.pass_context
def curve_swap(ctx, pool, token_in, token_out, amount):
    """Swap tokens on Curve"""
    from defi_autopilot.protocols.curve import CurveClient

    chain_id = ctx.obj["chain_id"]
    client = CurveClient(chain_id, pool)
    result = client.swap(token_in, token_out, amount)
    _print_tx_result(result)


@curve.command("pools")
@click.pass_context
def curve_pools(ctx):
    """List available Curve pools"""
    from defi_autopilot.protocols.curve import CURVE_POOLS

    chain_id = ctx.obj["chain_id"]
    pools = CURVE_POOLS.get(chain_id, {})

    table = Table(title=f"Curve Pools — Chain {chain_id}")
    table.add_column("Pool", style="cyan")
    table.add_column("Address", style="green")
    table.add_column("Coins", style="yellow")

    for name, info in pools.items():
        coins = ", ".join(info["coins"][:3])
        table.add_row(name, info["address"][:12] + "...", coins)

    console.print(table)


# ============================================================
# Utility Commands
# ============================================================

@cli.command("markets")
@click.pass_context
def list_markets(ctx):
    """List available protocols and markets"""
    from defi_autopilot.protocols.aave import BASE_TOKENS_AAVE
    from defi_autopilot.protocols.oneinch import BASE_TOKENS_INCH
    from defi_autopilot.protocols.uniswap import BASE_TOKENS_UNI
    from defi_autopilot.protocols.morpho import BASE_MARKETS
    from defi_autopilot.protocols.moonwell import BASE_MOONWELL

    table = Table(title="Available Markets")
    table.add_column("Protocol", style="cyan")
    table.add_column("Market/Token", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Chain", style="magenta")

    from defi_autopilot.protocols.compound import COMET_MARKETS
    from defi_autopilot.protocols.curve import CURVE_POOLS
    from defi_autopilot.protocols.lido import LIDO_ADDRESSES

    for name in sorted(BASE_TOKENS_UNI.keys()):
        table.add_row("Uniswap V3", name, "DEX", "Multi-chain")

    for name in sorted(BASE_MARKETS.keys()):
        table.add_row("Morpho Blue", name, "Lending", "Base")

    for name in sorted(BASE_MOONWELL["tokens"].keys()):
        table.add_row("Moonwell", name, "Lending", "Base")

    for name in sorted(BASE_TOKENS_AAVE.keys()):
        table.add_row("Aave V3", name, "Lending", "Multi-chain")

    for name in sorted(BASE_TOKENS_INCH.keys()):
        table.add_row("1inch", name, "DEX Aggregator", "Multi-chain")

    for chain_id, markets in COMET_MARKETS.items():
        for name in markets:
            table.add_row("Compound V3", name, "Lending", f"Chain {chain_id}")

    for chain_id, pools in CURVE_POOLS.items():
        for name in pools:
            table.add_row("Curve", name, "DEX", f"Chain {chain_id}")

    for chain_id in LIDO_ADDRESSES:
        table.add_row("Lido", "stETH/wstETH", "Liquid Staking", f"Chain {chain_id}")

    console.print(table)


# ============================================================
# Helper functions
# ============================================================

def _print_tx_result(result: dict):
    """Print transaction result"""
    if result.get("status") == 1:
        console.print("[green]TX Success[/green]")
    else:
        console.print("[red]TX Failed[/red]")

    console.print(f"  TX: {result.get('tx_hash', 'N/A')}")
    if "block_number" in result:
        console.print(f"  Block: {result['block_number']}")
    if "gas_used" in result:
        console.print(f"  Gas: {result['gas_used']}")


if __name__ == "__main__":
    cli()
