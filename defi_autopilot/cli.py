"""
defi-autopilot CLI 入口

用法:
  defi morpho supply   --market USDC-WETH-77 --amount 1000
  defi morpho borrow   --market USDC-WETH-77 --amount 500
  defi morpho repay    --market USDC-WETH-77 --amount 500
  defi morpho position --market USDC-WETH-77
  defi moonwell supply --token USDC --amount 1000
  defi moonwell borrow --token USDC --amount 500
  defi moonwell repay  --token USDC --amount 500
"""

import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# 加载 .env
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

console = Console()


# ============================================================
# 主命令组
# ============================================================

@click.group()
@click.option("--chain", "-c", default=8453, type=int, help="链 ID（默认 8453 = Base）")
@click.option("--dry-run", is_flag=True, help="只模拟，不发送交易")
@click.pass_context
def cli(ctx, chain, dry_run):
    """🚀 DeFi Autopilot — 多链多协议 DeFi 自动化工具"""
    ctx.ensure_object(dict)
    ctx.obj["chain_id"] = chain
    ctx.obj["dry_run"] = dry_run


# ============================================================
# Morpho 命令
# ============================================================

@cli.group()
def morpho():
    """Morpho Blue 借贷协议"""
    pass


@morpho.command("supply")
@click.option("--market", "-m", required=True, help="市场名称（如 USDC-WETH-77）或 market_id")
@click.option("--amount", "-a", required=True, type=int, help="供给数量（wei）")
@click.option("--on-behalf", type=str, default=None, help="代为供给的地址")
@click.pass_context
def morpho_supply(ctx, market, amount, on_behalf):
    """供给资产到 Morpho 市场"""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS

    chain_id = ctx.obj["chain_id"]
    client = MorphoClient(chain_id)

    mp = BASE_MARKETS.get(market)
    if mp is None:
        console.print(f"[red]未知市场: {market}[/red]")
        console.print(f"可用市场: {', '.join(BASE_MARKETS.keys())}")
        sys.exit(1)

    console.print(f"[cyan]供给 {amount} 到 {market} 市场[/cyan]")

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN — 不发送交易[/yellow]")
        info = client.get_market_info(mp)
        console.print(f"市场利用率: {info['utilization']:.2%}")
        return

    result = client.supply(mp, amount, on_behalf=on_behalf)
    _print_tx_result(result)


@morpho.command("supply-collateral")
@click.option("--market", "-m", required=True, help="市场名称")
@click.option("--amount", "-a", required=True, type=int, help="抵押品数量（wei）")
@click.pass_context
def morpho_supply_collateral(ctx, market, amount):
    """存入抵押品"""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS

    chain_id = ctx.obj["chain_id"]
    client = MorphoClient(chain_id)

    mp = BASE_MARKETS.get(market)
    if mp is None:
        console.print(f"[red]未知市场: {market}[/red]")
        sys.exit(1)

    result = client.supply_collateral(mp, amount)
    _print_tx_result(result)


@morpho.command("borrow")
@click.option("--market", "-m", required=True, help="市场名称")
@click.option("--amount", "-a", required=True, type=int, help="借出数量（wei）")
@click.pass_context
def morpho_borrow(ctx, market, amount):
    """从 Morpho 市场借款"""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS

    chain_id = ctx.obj["chain_id"]
    client = MorphoClient(chain_id)

    mp = BASE_MARKETS.get(market)
    if mp is None:
        console.print(f"[red]未知市场: {market}[/red]")
        sys.exit(1)

    result = client.borrow(mp, amount)
    _print_tx_result(result)


@morpho.command("repay")
@click.option("--market", "-m", required=True, help="市场名称")
@click.option("--amount", "-a", type=int, default=0, help="还款数量（wei）")
@click.option("--shares", "-s", type=int, default=0, help="还款份额")
@click.pass_context
def morpho_repay(ctx, market, amount, shares):
    """归还 Morpho 借款"""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS

    chain_id = ctx.obj["chain_id"]
    client = MorphoClient(chain_id)

    mp = BASE_MARKETS.get(market)
    if mp is None:
        console.print(f"[red]未知市场: {market}[/red]")
        sys.exit(1)

    result = client.repay(mp, amount=amount, shares=shares)
    _print_tx_result(result)


@morpho.command("withdraw")
@click.option("--market", "-m", required=True, help="市场名称")
@click.option("--amount", "-a", type=int, default=0, help="取出数量（wei）")
@click.pass_context
def morpho_withdraw(ctx, market, amount):
    """取出供给的资产"""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS

    chain_id = ctx.obj["chain_id"]
    client = MorphoClient(chain_id)

    mp = BASE_MARKETS.get(market)
    if mp is None:
        console.print(f"[red]未知市场: {market}[/red]")
        sys.exit(1)

    result = client.withdraw(mp, amount=amount)
    _print_tx_result(result)


@morpho.command("position")
@click.option("--market", "-m", required=True, help="市场名称")
@click.option("--user", "-u", type=str, default=None, help="查询地址")
@click.pass_context
def morpho_position(ctx, market, user):
    """查询 Morpho 头寸"""
    from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS
    from defi_autopilot.core.signer import get_address

    chain_id = ctx.obj["chain_id"]
    client = MorphoClient(chain_id)

    mp = BASE_MARKETS.get(market)
    if mp is None:
        console.print(f"[red]未知市场: {market}[/red]")
        sys.exit(1)

    user = user or get_address()
    supply_shares, borrow_shares, collateral = client.get_position(mp, user)
    info = client.get_market_info(mp)

    table = Table(title=f"Morpho 头寸 — {market}")
    table.add_column("指标", style="cyan")
    table.add_column("值", style="green")
    table.add_row("供给份额", str(supply_shares))
    table.add_row("借款份额", str(borrow_shares))
    table.add_row("抵押品", str(collateral))
    table.add_row("—", "—")
    table.add_row("市场总供给", str(info["total_supply_assets"]))
    table.add_row("市场总借款", str(info["total_borrow_assets"]))
    table.add_row("利用率", f"{info['utilization']:.2%}")

    console.print(table)


# ============================================================
# Moonwell 命令
# ============================================================

@cli.group()
def moonwell():
    """Moonwell 借贷协议（Compound V2）"""
    pass


@moonwell.command("supply")
@click.option("--token", "-t", required=True, help="代币名称（如 USDC, WETH）")
@click.option("--amount", "-a", required=True, type=int, help="供给数量（wei）")
@click.option("--enter-market/--no-enter-market", default=True, help="是否进入市场")
@click.pass_context
def moonwell_supply(ctx, token, amount, enter_market):
    """供给资产到 Moonwell 市场"""
    from defi_autopilot.protocols.moonwell import MoonwellClient, BASE_MOONWELL

    chain_id = ctx.obj["chain_id"]
    client = MoonwellClient(chain_id)

    token_info = BASE_MOONWELL["tokens"].get(token.upper())
    if token_info is None:
        console.print(f"[red]未知代币: {token}[/red]")
        console.print(f"可用: {', '.join(BASE_MOONWELL['tokens'].keys())}")
        sys.exit(1)

    result = client.supply(
        token_info["cToken"], amount,
        enter_market=enter_market,
    )
    _print_tx_result(result)


@moonwell.command("borrow")
@click.option("--token", "-t", required=True, help="代币名称")
@click.option("--amount", "-a", required=True, type=int, help="借出数量（wei）")
@click.pass_context
def moonwell_borrow(ctx, token, amount):
    """从 Moonwell 市场借款"""
    from defi_autopilot.protocols.moonwell import MoonwellClient, BASE_MOONWELL

    chain_id = ctx.obj["chain_id"]
    client = MoonwellClient(chain_id)

    token_info = BASE_MOONWELL["tokens"].get(token.upper())
    if token_info is None:
        console.print(f"[red]未知代币: {token}[/red]")
        sys.exit(1)

    result = client.borrow(token_info["cToken"], amount)
    _print_tx_result(result)


@moonwell.command("repay")
@click.option("--token", "-t", required=True, help="代币名称")
@click.option("--amount", "-a", required=True, type=int, help="还款数量（wei）")
@click.pass_context
def moonwell_repay(ctx, token, amount):
    """归还 Moonwell 借款"""
    from defi_autopilot.protocols.moonwell import MoonwellClient, BASE_MOONWELL

    chain_id = ctx.obj["chain_id"]
    client = MoonwellClient(chain_id)

    token_info = BASE_MOONWELL["tokens"].get(token.upper())
    if token_info is None:
        console.print(f"[red]未知代币: {token}[/red]")
        sys.exit(1)

    result = client.repay(token_info["cToken"], amount)
    _print_tx_result(result)


@moonwell.command("position")
@click.option("--token", "-t", required=True, help="代币名称")
@click.option("--user", "-u", type=str, default=None, help="查询地址")
@click.pass_context
def moonwell_position(ctx, token, user):
    """查询 Moonwell 头寸"""
    from defi_autopilot.protocols.moonwell import MoonwellClient, BASE_MOONWELL
    from defi_autopilot.core.signer import get_address

    chain_id = ctx.obj["chain_id"]
    client = MoonwellClient(chain_id)

    token_info = BASE_MOONWELL["tokens"].get(token.upper())
    if token_info is None:
        console.print(f"[red]未知代币: {token}[/red]")
        sys.exit(1)

    user = user or get_address()
    supply_bal = client.get_supply_balance(token_info["cToken"], user)
    borrow_bal = client.get_borrow_balance(token_info["cToken"], user)
    liquidity = client.get_account_liquidity(user)

    table = Table(title=f"Moonwell 头寸 — {token}")
    table.add_column("指标", style="cyan")
    table.add_column("值", style="green")
    table.add_row("供给余额 (cToken)", str(supply_bal))
    table.add_row("借款余额", str(borrow_bal))
    table.add_row("账户流动性", str(liquidity["liquidity"]))
    table.add_row("账户短缺", str(liquidity["shortfall"]))

    console.print(table)


# ============================================================
# 工具命令
# ============================================================

@cli.command("markets")
@click.pass_context
def list_markets(ctx):
    """列出可用的协议和市场"""
    table = Table(title="可用市场")
    table.add_column("协议", style="cyan")
    table.add_column("市场/代币", style="green")
    table.add_column("类型", style="yellow")
    table.add_column("链", style="magenta")

    # Morpho
    for name in sorted(BASE_MARKETS.keys()):
        table.add_row("Morpho", name, "借贷", "Base")

    # Moonwell
    for name in sorted(BASE_MOONWELL["tokens"].keys()):
        table.add_row("Moonwell", name, "借贷", "Base")

    console.print(table)


# ============================================================
# 辅助函数
# ============================================================

def _print_tx_result(result: dict):
    """打印交易结果"""
    if result.get("status") == 1:
        console.print(f"[green]✅ 交易成功[/green]")
    else:
        console.print(f"[red]❌ 交易失败[/red]")

    console.print(f"  TX: {result.get('tx_hash', 'N/A')}")
    if "block_number" in result:
        console.print(f"  Block: {result['block_number']}")
    if "gas_used" in result:
        console.print(f"  Gas: {result['gas_used']}")


if __name__ == "__main__":
    cli()
