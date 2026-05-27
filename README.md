# defi-autopilot

> 多链多协议 DeFi 自动化工具集

一站式 DeFi 操作 CLI，覆盖供给、借贷、还款、抵押品管理。支持多链部署，可扩展协议架构。

## 🏗️ 架构

```
defi-autopilot/
├── defi_autopilot/
│   ├── core/              # 共享基础设施
│   │   ├── chains.py      # 多链配置
│   │   ├── rpc.py         # Web3 实例管理
│   │   ├── signer.py      # 签名器
│   │   └── tx.py          # 交易构建/签名/广播/ERC20 approval
│   ├── protocols/         # 协议实现
│   │   ├── morpho/        # Morpho Blue（隔离借贷市场）
│   │   └── moonwell/      # Moonwell（Compound V2 fork）
│   └── cli.py             # Click CLI 入口
└── tests/
```

## 📦 支持的协议

| 协议 | 类型 | 链 | 操作 |
|------|------|-----|------|
| **Morpho Blue** | 隔离借贷 | Base, Ethereum, Arbitrum | supply, supplyCollateral, borrow, repay, withdraw, withdrawCollateral |
| **Moonwell** | 借贷 (Compound V2) | Base | supply(mint), redeem, borrow, repayBorrow |

## 🚀 快速开始

### 安装

```bash
pip install -e ".[dev]"
```

### 配置

创建 `.env` 文件：

```env
# RPC 端点
RPC_BASE=https://mainnet.base.org
RPC_ETHEREUM=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
RPC_ARBITRUM=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY

# 签名私钥（勿提交到 Git）
SIGNER_PRIVATE_KEY=0x...
```

### 使用

```bash
# 列出可用市场
defi markets

# --- Morpho ---
# 查询头寸
defi morpho position --market USDC-WETH-77

# 供给 USDC 到市场（赚取利息）
defi morpho supply --market USDC-WETH-77 --amount 1000000000

# 存入 WETH 作为抵押品
defi morpho supply-collateral --market USDC-WETH-77 --amount 500000000000000000

# 借出 USDC（需要先存抵押品）
defi morpho borrow --market USDC-WETH-77 --amount 500000000

# 还款
defi morpho repay --market USDC-WETH-77 --amount 500000000

# 取出供给
defi morpho withdraw --market USDC-WETH-77 --amount 1000000000

# --- Moonwell ---
# 供给 USDC
defi moonwell supply --token USDC --amount 1000000000

# 借出 WETH
defi moonwell borrow --token WETH --amount 500000000000000000

# 还款
defi moonwell repay --token WETH --amount 500000000000000000

# 查询头寸
defi moonwell position --token USDC

# --- 通用 ---
# 指定链
defi -c 1 morpho position --market ...

# 模拟（不发交易）
defi --dry-run morpho supply --market USDC-WETH-77 --amount 1000
```

## 🧪 测试

```bash
pytest tests/ -v
```

## 🔧 作为 SDK 使用

```python
from defi_autopilot.protocols.morpho import MorphoClient, BASE_MARKETS

client = MorphoClient(8453)  # Base

# 供给
result = client.supply(
    market=BASE_MARKETS["USDC-WETH-77"],
    amount=1000000000,  # 1000 USDC (6 decimals)
)

# 查询头寸
supply_shares, borrow_shares, collateral = client.get_position(
    BASE_MARKETS["USDC-WETH-77"],
    user="0xYourAddress",
)
```

## 🛡️ 安全

- 私钥通过环境变量加载，不硬编码
- 交易需明确指定金额，无默认全仓操作
- Gas 估算自动加 10% buffer
- EIP-1559 费用自动获取

## 📄 License

MIT
