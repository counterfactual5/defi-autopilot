"""
Moonwell protocol interaction module

Moonwell is a Compound V2 fork deployed on Base and Optimism.
Standard interface: supply(mint) → redeem → borrow → repay

Base Comptroller: 0xfBb21d038542BA6Dc083e0E6e5aF33a7A7eA698F
"""

from typing import Optional, Dict, Any

from web3 import Web3

from defi_autopilot.core.rpc import get_w3, get_chain_config
from defi_autopilot.core.signer import get_signer, get_address
from defi_autopilot.core.tx import build_and_send_tx, check_allowance, approve_token


# Compound V2 standard cToken ABI (abbreviated)
CTOKEN_ABI = [
    # mint (supply)
    {
        "inputs": [{"name": "mintAmount", "type": "uint256"}],
        "name": "mint",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # redeem (withdraw supply)
    {
        "inputs": [{"name": "redeemTokens", "type": "uint256"}],
        "name": "redeem",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # redeemUnderlying (withdraw by underlying asset amount)
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

# Comptroller ABI (abbreviated)
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
# Base chain Moonwell contract addresses
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
    """Moonwell protocol client (Compound V2 interface)"""

    def __init__(self, chain_id: int = 8453):
        self.chain_id = chain_id
        self.config = get_chain_config(chain_id)
        self.w3 = get_w3(chain_id)
        self._contracts: Dict[str, object] = {}

    def _get_ctoken(self, ctoken_address: str):
        """Get cToken contract instance"""
        addr = Web3.to_checksum_address(ctoken_address)
        return self.w3.eth.contract(address=addr, abi=CTOKEN_ABI)

    def _get_comptroller(self, comptroller_address: str):
        """Get Comptroller contract instance"""
        addr = Web3.to_checksum_address(comptroller_address)
        return self.w3.eth.contract(address=addr, abi=COMPTROLLER_ABI)

    # ---- Supply (mint) ----

    def supply(
        self,
        ctoken_address: str,
        amount: int,
        enter_market: bool = True,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Supply assets to a Moonwell market.
        In Compound V2, supply = mint.
        """
        signer_addr = get_address(private_key)
        ctoken = self._get_ctoken(ctoken_address)
        underlying_addr = ctoken.functions.underlying().call()

        # Approve underlying token first
        allowance = check_allowance(
            self.chain_id, underlying_addr, signer_addr, ctoken_address
        )
        if allowance < amount:
            approve_token(
                self.chain_id, underlying_addr,
                ctoken_address, 2**256 - 1,
                private_key,
            )

        # Enter market (use as collateral)
        if enter_market:
            comptroller = BASE_MOONWELL["comptroller"]
            comp = self._get_comptroller(comptroller)
            # Check if already in market
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
                pass  # May already be in market

        # Execute mint
        data = ctoken.encode_abi("mint", [amount])
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=ctoken_address,
            data=data,
            private_key=private_key,
        )

    # ---- Withdraw (redeem) ----

    def redeem(
        self,
        ctoken_address: str,
        ctoken_amount: int = 0,
        underlying_amount: int = 0,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Withdraw supplied assets.
        ctoken_amount > 0 → redeem by cToken amount
        underlying_amount > 0 → redeem by underlying asset amount
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

    # ---- Borrow ----

    def borrow(
        self,
        ctoken_address: str,
        amount: int,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Borrow assets from the market"""
        ctoken = self._get_ctoken(ctoken_address)
        data = ctoken.encode_abi("borrow", [amount])
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=ctoken_address,
            data=data,
            private_key=private_key,
        )

    # ---- Repay ----

    def repay(
        self,
        ctoken_address: str,
        amount: int,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Repay borrowed assets. amount = 2^256-1 means repay all"""
        signer_addr = get_address(private_key)
        ctoken = self._get_ctoken(ctoken_address)
        underlying_addr = ctoken.functions.underlying().call()

        # Approve underlying token
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

    # ---- Queries ----

    def get_supply_balance(self, ctoken_address: str, user: str) -> int:
        """Query supply balance (cToken amount)"""
        ctoken = self._get_ctoken(ctoken_address)
        return ctoken.functions.balanceOf(Web3.to_checksum_address(user)).call()

    def get_borrow_balance(self, ctoken_address: str, user: str) -> int:
        """Query borrow balance"""
        ctoken = self._get_ctoken(ctoken_address)
        return ctoken.functions.borrowBalanceCurrent(
            Web3.to_checksum_address(user)
        ).call()

    def get_account_liquidity(self, user: str) -> Dict[str, int]:
        """Query account liquidity"""
        comp = self._get_comptroller(BASE_MOONWELL["comptroller"])
        error, liquidity, shortfall = comp.functions.getAccountLiquidity(
            Web3.to_checksum_address(user)
        ).call()
        return {
            "error": error,
            "liquidity": liquidity,
            "shortfall": shortfall,
        }
