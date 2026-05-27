"""
Aave V3 Protocol Client

Aave V3 is a decentralized lending/borrowing protocol deployed on multiple chains.
Core operations: supply, withdraw, borrow, repay, setUserUseReserveAsCollateral

Key contracts per chain:
  - Pool: main lending pool
  - PoolAddressesProvider: registry for pool addresses
"""

from typing import Optional, Dict, Any, List

from web3 import Web3

from defi_autopilot.core.rpc import get_w3, get_chain_config
from defi_autopilot.core.signer import get_signer, get_address
from defi_autopilot.core.tx import build_and_send_tx, check_allowance, approve_token


# Aave V3 Pool ABI (core functions only)
AAVE_V3_POOL_ABI = [
    # supply(asset, amount, onBehalfOf, referralCode)
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "onBehalfOf", "type": "address"},
            {"name": "referralCode", "type": "uint16"},
        ],
        "name": "supply",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # withdraw(asset, amount, to)
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "to", "type": "address"},
        ],
        "name": "withdraw",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # borrow(asset, amount, interestRateMode, referralCode, onBehalfOf)
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "interestRateMode", "type": "uint256"},
            {"name": "referralCode", "type": "uint16"},
            {"name": "onBehalfOf", "type": "address"},
        ],
        "name": "borrow",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # repay(asset, amount, interestRateMode, onBehalfOf)
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "interestRateMode", "type": "uint256"},
            {"name": "onBehalfOf", "type": "address"},
        ],
        "name": "repay",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # setUserUseReserveAsCollateral(asset, useAsCollateral)
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "useAsCollateral", "type": "bool"},
        ],
        "name": "setUserUseReserveAsCollateral",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # getUserAccountData(user)
    {
        "inputs": [{"name": "user", "type": "address"}],
        "name": "getUserAccountData",
        "outputs": [
            {"name": "totalCollateralBase", "type": "uint256"},
            {"name": "totalDebtBase", "type": "uint256"},
            {"name": "availableBorrowsBase", "type": "uint256"},
            {"name": "currentLiquidationThreshold", "type": "uint256"},
            {"name": "ltv", "type": "uint256"},
            {"name": "healthFactor", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # getReserveData(asset)
    {
        "inputs": [{"name": "asset", "type": "address"}],
        "name": "getReserveData",
        "outputs": [
            {"name": "configuration", "type": "uint256"},
            {"name": "liquidityIndex", "type": "uint128"},
            {"name": "currentLiquidityRate", "type": "uint128"},
            {"name": "variableBorrowIndex", "type": "uint128"},
            {"name": "currentVariableBorrowRate", "type": "uint128"},
            {"name": "currentStableBorrowRate", "type": "uint128"},
            {"name": "lastUpdateTimestamp", "type": "uint40"},
            {"name": "id", "type": "uint16"},
            {"name": "aTokenAddress", "type": "address"},
            {"name": "stableDebtTokenAddress", "type": "address"},
            {"name": "variableDebtTokenAddress", "type": "address"},
            {"name": "interestRateStrategyAddress", "type": "address"},
            {"name": "accruedToTreasury", "type": "uint128"},
            {"name": "unbacked", "type": "uint128"},
            {"name": "isolationModeTotalDebt", "type": "uint128"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

# Interest rate modes
INTEREST_RATE_VARIABLE = 2
INTEREST_RATE_STABLE = 1

# ============================================================
# Aave V3 Pool Addresses Per Chain
# ============================================================

AAVE_V3_POOLS = {
    # Base
    8453: "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5",
    # Ethereum Mainnet
    1: "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
    # Arbitrum
    42161: "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
    # Optimism
    10: "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
    # Polygon
    137: "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
}

# Common token addresses on Base (shared with Morpho config)
BASE_TOKENS_AAVE = {
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "WETH": "0x4200000000000000000000000000000000000006",
    "cbBTC": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
    "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    "USDbC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",
    "GHO": "0x9eA346d24BAe85E1350521b3293e718180B014E2",
}


class AaveV3Client:
    """Aave V3 Protocol Client"""

    def __init__(self, chain_id: int = 8453):
        self.chain_id = chain_id
        self.config = get_chain_config(chain_id)
        self.w3 = get_w3(chain_id)

        pool_addr = AAVE_V3_POOLS.get(chain_id)
        if pool_addr is None:
            raise ValueError(f"Aave V3 not deployed on chain {chain_id}")

        self.pool_address = Web3.to_checksum_address(pool_addr)
        self.pool = self.w3.eth.contract(
            address=self.pool_address, abi=AAVE_V3_POOL_ABI
        )

    # ---- Supply ----

    def supply(
        self,
        asset: str,
        amount: int,
        on_behalf: Optional[str] = None,
        use_as_collateral: bool = True,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Supply assets to Aave V3 pool."""
        signer_addr = get_address(private_key)
        on_behalf = on_behalf or signer_addr

        # Check and handle approval (approve aToken)
        reserve_data = self.pool.functions.getReserveData(
            Web3.to_checksum_address(asset)
        ).call()
        a_token = reserve_data[8]  # aTokenAddress

        allowance = check_allowance(self.chain_id, asset, signer_addr, self.pool_address)
        if allowance < amount:
            approve_token(self.chain_id, asset, self.pool_address, 2**256 - 1, private_key)

        data = self.pool.encode_abi(
            "supply",
            [
                Web3.to_checksum_address(asset),
                amount,
                Web3.to_checksum_address(on_behalf),
                0,  # referralCode (deprecated, use 0)
            ],
        )
        result = build_and_send_tx(
            chain_id=self.chain_id,
            to=self.pool_address,
            data=data,
            private_key=private_key,
        )

        # Set as collateral in a separate tx (after supply succeeds)
        if use_as_collateral:
            try:
                self._set_collateral(asset, True, private_key)
            except Exception:
                pass  # May already be collateralized

        return result

    # ---- Withdraw ----

    def withdraw(
        self,
        asset: str,
        amount: int = 2**256 - 1,  # max = withdraw all
        to: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Withdraw supplied assets from Aave V3 pool."""
        signer_addr = get_address(private_key)
        to = to or signer_addr

        data = self.pool.encode_abi(
            "withdraw",
            [
                Web3.to_checksum_address(asset),
                amount,
                Web3.to_checksum_address(to),
            ],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self.pool_address,
            data=data,
            private_key=private_key,
        )

    # ---- Borrow ----

    def borrow(
        self,
        asset: str,
        amount: int,
        interest_rate_mode: int = INTEREST_RATE_VARIABLE,
        on_behalf: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Borrow assets from Aave V3 pool."""
        signer_addr = get_address(private_key)
        on_behalf = on_behalf or signer_addr

        data = self.pool.encode_abi(
            "borrow",
            [
                Web3.to_checksum_address(asset),
                amount,
                interest_rate_mode,
                0,  # referralCode
                Web3.to_checksum_address(on_behalf),
            ],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self.pool_address,
            data=data,
            private_key=private_key,
        )

    # ---- Repay ----

    def repay(
        self,
        asset: str,
        amount: int = 2**256 - 1,  # max = repay all
        interest_rate_mode: int = INTEREST_RATE_VARIABLE,
        on_behalf: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Repay borrowed assets to Aave V3 pool."""
        signer_addr = get_address(private_key)
        on_behalf = on_behalf or signer_addr

        # Approve pool to spend
        if amount < 2**256 - 1:
            allowance = check_allowance(
                self.chain_id, asset, signer_addr, self.pool_address
            )
            if allowance < amount:
                approve_token(
                    self.chain_id, asset, self.pool_address, amount, private_key
                )

        data = self.pool.encode_abi(
            "repay",
            [
                Web3.to_checksum_address(asset),
                amount,
                interest_rate_mode,
                Web3.to_checksum_address(on_behalf),
            ],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self.pool_address,
            data=data,
            private_key=private_key,
        )

    # ---- Collateral Toggle ----

    def _set_collateral(
        self, asset: str, use_as_collateral: bool, private_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enable/disable an asset as collateral."""
        data = self.pool.encode_abi(
            "setUserUseReserveAsCollateral",
            [Web3.to_checksum_address(asset), use_as_collateral],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self.pool_address,
            data=data,
            private_key=private_key,
        )

    # ---- Queries ----

    def get_user_account_data(self, user: str) -> Dict[str, Any]:
        """Get user account data (collateral, debt, health factor)."""
        result = self.pool.functions.getUserAccountData(
            Web3.to_checksum_address(user)
        ).call()
        return {
            "total_collateral_base": result[0],
            "total_debt_base": result[1],
            "available_borrows_base": result[2],
            "current_liquidation_threshold": result[3],
            "ltv": result[4],
            "health_factor": result[5],
        }

    def get_reserve_data(self, asset: str) -> Dict[str, Any]:
        """Get reserve data for an asset."""
        result = self.pool.functions.getReserveData(
            Web3.to_checksum_address(asset)
        ).call()
        return {
            "liquidity_index": result[1],
            "current_liquidity_rate": result[2],
            "variable_borrow_index": result[3],
            "current_variable_borrow_rate": result[4],
            "current_stable_borrow_rate": result[5],
            "a_token_address": result[8],
            "variable_debt_token_address": result[10],
        }
