"""
Moonwell 协议交互模块

Moonwell 是 Compound V2 fork，部署在 Base 和 Optimism 上。
标准接口：supply(mint) → redeem → borrow → repay

Base Comptroller: 0xfBb21d038542BA6Dc083e0E6e5aF33a7A7eA698F
"""

from typing import Optional, Dict, Any

from web3 import Web3

from defi_autopilot.core.rpc import get_w3, get_chain_config
from defi_autopilot.core.signer import get_signer, get_address
from defi_autopilot.core.tx import build_and_send_tx, check_allowance, approve_token


# Compound V2 标准 cToken ABI（精简版）
CTOKEN_ABI = [
    # mint（supply）
    {
        "inputs": [{"name": "mintAmount", "type": "uint256"}],
        "name": "mint",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # redeem（取出供给）
    {
        "inputs": [{"name": "redeemTokens", "type": "uint256"}],
        "name": "redeem",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # redeemUnderlying（按底层资产数量取出）
    {
        "inputs": [{"name": "redeemAmount", "type": "uint256"}],
        "name": "redeemUnderlying",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # borrow
    {
        "inputs": [{"name": "borrowAmount", "type": "uint256"}],
        "name": "borrow",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # repayBorrow
    {
        "inputs": [{"name": "repayAmount", "type": "uint256"}],
        "name": "repayBorrow",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # balanceOf
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # borrowBalanceCurrent
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "borrowBalanceCurrent",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # exchangeRateCurrent
    {
        "inputs": [],
        "name": "exchangeRateCurrent",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # underlying
    {
        "inputs": [],
        "name": "underlying",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# Comptroller ABI（精简）
COMPTROLLER_ABI = [
    # enterMarkets
    {
        "inputs": [{"name": "cTokens", "type": "address[]"}],
        "name": "enterMarkets",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # getAccountLiquidity
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "getAccountLiquidity",
        "outputs": [
            {"name": "error", "type": "uint256"},
            {"name": "liquidity", "type": "uint256"},
            {"name": "shortfall", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # markets
    {
        "inputs": [{"name": "", "type": "address"}],
        "name": "markets",
        "outputs": [
            {"name": "isListed", "type": "bool"},
            {"name": "collateralFactorMantissa", "type": "uint256"},
            {"name": "marketBorrowCaps", "type": "uint256"},
            {"name": "marketSupplyCaps", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# Base 链 Moonwell 合约地址
# ============================================================

BASE_MOONWELL = {
    "comptroller": "0xfBb21d038542BA6Dc083e0E6e5aF33a7A7eA698F",
    "tokens": {
        "USDC": {
            "cToken": "0xEdc8bA77559C438a653DBF954aB2EbdF6da372FE",
            "underlying": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        },
        "WETH": {
            "cToken": "0x340003Ad46e589F77689387B4E3Be43284E38CCc",
            "underlying": "0x4200000000000000000000000000000000000006",
        },
        "cbBTC": {
            "cToken": "0x432BAfBc540a32515164d7C6578a440034Cd3fb2",
            "underlying": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
        },
        "EURC": {
            "cToken": "0x97782bBe51093C1169C4ba9c03492a709a196e32",
            "underlying": "0x60a3E35Cc302bFA44Cb288Bc5a4F316Fdb1adb42",
        },
    },
}


class MoonwellClient:
    """Moonwell 协议客户端（Compound V2 接口）"""

    def __init__(self, chain_id: int = 8453):
        self.chain_id = chain_id
        self.config = get_chain_config(chain_id)
        self.w3 = get_w3(chain_id)
        self._contracts: Dict[str, object] = {}

    def _get_ctoken(self, ctoken_address: str):
        """获取 cToken 合约实例"""
        addr = Web3.to_checksum_address(ctoken_address)
        return self.w3.eth.contract(address=addr, abi=CTOKEN_ABI)

    def _get_comptroller(self, comptroller_address: str):
        """获取 Comptroller 合约实例"""
        addr = Web3.to_checksum_address(comptroller_address)
        return self.w3.eth.contract(address=addr, abi=COMPTROLLER_ABI)

    # ---- 供给 (mint) ----

    def supply(
        self,
        ctoken_address: str,
        amount: int,
        enter_market: bool = True,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        供给资产到 Moonwell 市场。
        Compound V2 里 supply = mint。
        """
        signer_addr = get_address(private_key)
        ctoken = self._get_ctoken(ctoken_address)
        underlying_addr = ctoken.functions.underlying().call()

        # 先 approve 底层代币
        allowance = check_allowance(
            self.chain_id, underlying_addr, signer_addr, ctoken_address
        )
        if allowance < amount:
            approve_token(
                self.chain_id, underlying_addr,
                ctoken_address, 2**256 - 1,
                private_key,
            )

        # 进入市场（作为抵押品）
        if enter_market:
            comptroller = BASE_MOONWELL["comptroller"]
            comp = self._get_comptroller(comptroller)
            # 检查是否已在市场
            try:
                data_enter = comp.encode_abi(
                    "enterMarkets", [[Web3.to_checksum_address(ctoken_address)]]
                )
                build_and_send_tx(
                    chain_id=self.chain_id,
                    to=comptroller,
                    data=data_enter,
                    private_key=private_key,
                )
            except Exception:
                pass  # 可能已在市场中

        # 执行 mint
        data = ctoken.encode_abi("mint", [amount])
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=ctoken_address,
            data=data,
            private_key=private_key,
        )

    # ---- 取出 (redeem) ----

    def redeem(
        self,
        ctoken_address: str,
        ctoken_amount: int = 0,
        underlying_amount: int = 0,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        取出供给的资产。
        ctoken_amount > 0 → 按 cToken 数量赎回
        underlying_amount > 0 → 按底层资产数量赎回
        """
        ctoken = self._get_ctoken(ctoken_address)
        if underlying_amount > 0:
            data = ctoken.encode_abi("redeemUnderlying", [underlying_amount])
        else:
            data = ctoken.encode_abi("redeem", [ctoken_amount])

        return build_and_send_tx(
            chain_id=self.chain_id,
            to=ctoken_address,
            data=data,
            private_key=private_key,
        )

    # ---- 借款 ----

    def borrow(
        self,
        ctoken_address: str,
        amount: int,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """从市场借出资产"""
        ctoken = self._get_ctoken(ctoken_address)
        data = ctoken.encode_abi("borrow", [amount])
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=ctoken_address,
            data=data,
            private_key=private_key,
        )

    # ---- 还款 ----

    def repay(
        self,
        ctoken_address: str,
        amount: int,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """归还借款。amount = 2^256-1 表示全还"""
        signer_addr = get_address(private_key)
        ctoken = self._get_ctoken(ctoken_address)
        underlying_addr = ctoken.functions.underlying().call()

        # approve 底层代币
        if amount < 2**256 - 1:
            allowance = check_allowance(
                self.chain_id, underlying_addr, signer_addr, ctoken_address
            )
            if allowance < amount:
                approve_token(
                    self.chain_id, underlying_addr,
                    ctoken_address, amount, private_key,
                )

        data = ctoken.encode_abi("repayBorrow", [amount])
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=ctoken_address,
            data=data,
            private_key=private_key,
        )

    # ---- 查询 ----

    def get_supply_balance(self, ctoken_address: str, user: str) -> int:
        """查询供给余额（cToken 数量）"""
        ctoken = self._get_ctoken(ctoken_address)
        return ctoken.functions.balanceOf(Web3.to_checksum_address(user)).call()

    def get_borrow_balance(self, ctoken_address: str, user: str) -> int:
        """查询借款余额"""
        ctoken = self._get_ctoken(ctoken_address)
        return ctoken.functions.borrowBalanceCurrent(
            Web3.to_checksum_address(user)
        ).call()

    def get_account_liquidity(self, user: str) -> Dict[str, int]:
        """查询账户流动性"""
        comp = self._get_comptroller(BASE_MOONWELL["comptroller"])
        error, liquidity, shortfall = comp.functions.getAccountLiquidity(
            Web3.to_checksum_address(user)
        ).call()
        return {
            "error": error,
            "liquidity": liquidity,
            "shortfall": shortfall,
        }
