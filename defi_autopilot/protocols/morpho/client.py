"""
Morpho Blue protocol interaction module

Morpho Blue is an immutable lending protocol; the core contract address is the same across all chains:
0xBBBBBBBBB9cC5e90e3b3af64bdAF62C37EEFFcBb

Core operations:
- supply(loanToken)        Supply assets to earn interest
- supplyCollateral(...)    Deposit collateral
- borrow(...)              Borrow assets
- repay(...)               Repay borrowed assets
- withdraw(loanToken)      Withdraw supplied assets
- withdrawCollateral(...)  Withdraw collateral

Each market is uniquely identified by MarketParams:
  { loanToken, collateralToken, oracle, irm, lltv }
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

from web3 import Web3

from defi_autopilot.core.rpc import get_w3, get_chain_config
from defi_autopilot.core.signer import get_address
from defi_autopilot.core.tx import build_and_send_tx, check_allowance, approve_token

# Morpho Blue core contract ABI (abbreviated, covers all operations)
MORPHO_BLUE_ABI = [
    # supply(loanToken amount shares onBehalf hooksData)
    {
        "inputs": [
            {"name": "marketParams", "type": "tuple", "components": [
                {"name": "loanToken", "type": "address"},
                {"name": "collateralToken", "type": "address"},
                {"name": "oracle", "type": "address"},
                {"name": "irm", "type": "address"},
                {"name": "lltv", "type": "uint256"},
            ]},
            {"name": "assets", "type": "uint256"},
            {"name": "shares", "type": "uint256"},
            {"name": "onBehalf", "type": "address"},
            {"name": "hooksData", "type": "bytes"},
        ],
        "name": "supply",
        "outputs": [{"name": "", "type": "uint256"}, {"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # withdraw(loanToken amount shares onBehalf receiver hooksData)
    {
        "inputs": [
            {"name": "marketParams", "type": "tuple", "components": [
                {"name": "loanToken", "type": "address"},
                {"name": "collateralToken", "type": "address"},
                {"name": "oracle", "type": "address"},
                {"name": "irm", "type": "address"},
                {"name": "lltv", "type": "uint256"},
            ]},
            {"name": "assets", "type": "uint256"},
            {"name": "shares", "type": "uint256"},
            {"name": "onBehalf", "type": "address"},
            {"name": "receiver", "type": "address"},
            {"name": "hooksData", "type": "bytes"},
        ],
        "name": "withdraw",
        "outputs": [{"name": "", "type": "uint256"}, {"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # supplyCollateral(marketParams amount onBehalf hooksData)
    {
        "inputs": [
            {"name": "marketParams", "type": "tuple", "components": [
                {"name": "loanToken", "type": "address"},
                {"name": "collateralToken", "type": "address"},
                {"name": "oracle", "type": "address"},
                {"name": "irm", "type": "address"},
                {"name": "lltv", "type": "uint256"},
            ]},
            {"name": "assets", "type": "uint256"},
            {"name": "onBehalf", "type": "address"},
            {"name": "hooksData", "type": "bytes"},
        ],
        "name": "supplyCollateral",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # withdrawCollateral(marketParams amount onBehalf receiver hooksData)
    {
        "inputs": [
            {"name": "marketParams", "type": "tuple", "components": [
                {"name": "loanToken", "type": "address"},
                {"name": "collateralToken", "type": "address"},
                {"name": "oracle", "type": "address"},
                {"name": "irm", "type": "address"},
                {"name": "lltv", "type": "uint256"},
            ]},
            {"name": "assets", "type": "uint256"},
            {"name": "onBehalf", "type": "address"},
            {"name": "receiver", "type": "address"},
            {"name": "hooksData", "type": "bytes"},
        ],
        "name": "withdrawCollateral",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # borrow(marketParams assets shares onBehalf receiver hooksData)
    {
        "inputs": [
            {"name": "marketParams", "type": "tuple", "components": [
                {"name": "loanToken", "type": "address"},
                {"name": "collateralToken", "type": "address"},
                {"name": "oracle", "type": "address"},
                {"name": "irm", "type": "address"},
                {"name": "lltv", "type": "uint256"},
            ]},
            {"name": "assets", "type": "uint256"},
            {"name": "shares", "type": "uint256"},
            {"name": "onBehalf", "type": "address"},
            {"name": "receiver", "type": "address"},
            {"name": "hooksData", "type": "bytes"},
        ],
        "name": "borrow",
        "outputs": [{"name": "", "type": "uint256"}, {"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # repay(marketParams assets shares onBehalf hooksData)
    {
        "inputs": [
            {"name": "marketParams", "type": "tuple", "components": [
                {"name": "loanToken", "type": "address"},
                {"name": "collateralToken", "type": "address"},
                {"name": "oracle", "type": "address"},
                {"name": "irm", "type": "address"},
                {"name": "lltv", "type": "uint256"},
            ]},
            {"name": "assets", "type": "uint256"},
            {"name": "shares", "type": "uint256"},
            {"name": "onBehalf", "type": "address"},
            {"name": "hooksData", "type": "bytes"},
        ],
        "name": "repay",
        "outputs": [{"name": "", "type": "uint256"}, {"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # position(id user) -> (supplyShares, borrowShares, collateral)
    {
        "inputs": [
            {"name": "id", "type": "bytes32"},
            {"name": "user", "type": "address"},
        ],
        "name": "position",
        "outputs": [
            {"name": "supplyShares", "type": "uint128"},
            {"name": "borrowShares", "type": "uint128"},
            {"name": "collateral", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # market(id) -> (totalSupplyAssets, totalSupplyShares, totalBorrowAssets, totalBorrowShares, lastUpdate, fee)
    {
        "inputs": [{"name": "id", "type": "bytes32"}],
        "name": "market",
        "outputs": [
            {"name": "totalSupplyAssets", "type": "uint128"},
            {"name": "totalSupplyShares", "type": "uint128"},
            {"name": "totalBorrowAssets", "type": "uint128"},
            {"name": "totalBorrowShares", "type": "uint128"},
            {"name": "lastUpdate", "type": "uint128"},
            {"name": "fee", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

# Zero address (Morpho uses bytes32(0) to indicate no hooks)
EMPTY_HOOKS = b"\x00" * 32


@dataclass
class MarketParams:
    """Morpho market parameters"""
    loan_token: str
    collateral_token: str
    oracle: str
    irm: str
    lltv: int  # Base 1e18 (e.g. 77% = 770000000000000000)

    @property
    def market_id(self) -> bytes:
        """Compute market ID (keccak256 of encoded params)"""
        from eth_abi import encode
        encoded = encode(
            ["address", "address", "address", "address", "uint256"],
            [
                Web3.to_checksum_address(self.loan_token),
                Web3.to_checksum_address(self.collateral_token),
                Web3.to_checksum_address(self.oracle),
                Web3.to_checksum_address(self.irm),
                self.lltv,
            ],
        )
        return Web3.keccak(encoded)

    def to_tuple(self):
        return (
            Web3.to_checksum_address(self.loan_token),
            Web3.to_checksum_address(self.collateral_token),
            Web3.to_checksum_address(self.oracle),
            Web3.to_checksum_address(self.irm),
            self.lltv,
        )


# ============================================================
# Preset Base chain market parameters
# ============================================================

# Morpho official IRM addresses
MORPHO_IRM = {
    8453: {
        "adaptive_curve": "0x870aAcb0EB19c95DaE3Fb3e4047a8D7F28461141",
    },
    1: {
        "adaptive_curve": "0x870aAcb0EB19c95DaE3Fb3e4047a8D7F28461141",
    },
}

# Base chain commonly used Oracle addresses
BASE_ORACLES = {
    "weth_usdc": "0x5c9e10a30610EfE425697e3b9145569cAcdA7A3f",
}

# Base chain commonly used Token addresses
BASE_TOKENS = {
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "WETH": "0x4200000000000000000000000000000000000006",
    "cbBTC": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
    "USDbC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",
    "wstETH": "0xc1CBa3fCea347f7fDCaB627dA9aF9e97D0e01e7D",
}

# Preset Base chain Morpho markets
BASE_MARKETS = {
    "USDC-WETH-77": MarketParams(
        loan_token=BASE_TOKENS["USDC"],
        collateral_token=BASE_TOKENS["WETH"],
        oracle=BASE_ORACLES["weth_usdc"],
        irm=MORPHO_IRM[8453]["adaptive_curve"],
        lltv=770000000000000000,  # 77%
    ),
    "USDC-wstETH-80": MarketParams(
        loan_token=BASE_TOKENS["USDC"],
        collateral_token=BASE_TOKENS["wstETH"],
        oracle=BASE_ORACLES["weth_usdc"],
        irm=MORPHO_IRM[8453]["adaptive_curve"],
        lltv=800000000000000000,  # 80%
    ),
    "USDC-cbBTC-74": MarketParams(
        loan_token=BASE_TOKENS["USDC"],
        collateral_token=BASE_TOKENS["cbBTC"],
        oracle=BASE_ORACLES["weth_usdc"],
        irm=MORPHO_IRM[8453]["adaptive_curve"],
        lltv=740000000000000000,  # 74%
    ),
}


class MorphoClient:
    """Morpho Blue protocol client"""

    def __init__(self, chain_id: int = 8453):
        self.chain_id = chain_id
        self.config = get_chain_config(chain_id)
        self.w3 = get_w3(chain_id)
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.config.morpho_blue),
            abi=MORPHO_BLUE_ABI,
        )
        self._morpho_address = self.config.morpho_blue

    # ---- Supply ----

    def supply(
        self,
        market: MarketParams,
        amount: int,
        on_behalf: Optional[str] = None,
        private_key: Optional[str] = None,
        skip_approval: bool = False,
    ) -> Dict[str, Any]:
        """Supply assets to the market (earn interest)"""
        signer_addr = get_address(private_key)
        on_behalf = on_behalf or signer_addr

        # Check and handle approval (use max approve to save gas on future txs)
        if not skip_approval:
            allowance = check_allowance(
                self.chain_id, market.loan_token, signer_addr, self._morpho_address
            )
            if allowance < amount:
                approve_token(
                    self.chain_id, market.loan_token,
                    self._morpho_address, 2**256 - 1, private_key
                )

        data = self.contract.encode_abi(
            "supply",
            [market.to_tuple(), amount, 0, Web3.to_checksum_address(on_behalf), EMPTY_HOOKS],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._morpho_address,
            data=data,
            private_key=private_key,
        )

    # ---- Deposit Collateral ----

    def supply_collateral(
        self,
        market: MarketParams,
        amount: int,
        on_behalf: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Deposit collateral"""
        signer_addr = get_address(private_key)
        on_behalf = on_behalf or signer_addr

        # Check approval
        allowance = check_allowance(
            self.chain_id, market.collateral_token, signer_addr, self._morpho_address
        )
        if allowance < amount:
            approve_token(
                self.chain_id, market.collateral_token,
                self._morpho_address, amount, private_key
            )

        data = self.contract.encode_abi(
            "supplyCollateral",
            [market.to_tuple(), amount, Web3.to_checksum_address(on_behalf), EMPTY_HOOKS],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._morpho_address,
            data=data,
            private_key=private_key,
        )

    # ---- Borrow ----

    def borrow(
        self,
        market: MarketParams,
        amount: int,
        on_behalf: Optional[str] = None,
        receiver: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Borrow assets from the market"""
        signer_addr = get_address(private_key)
        on_behalf = on_behalf or signer_addr
        receiver = receiver or signer_addr

        data = self.contract.encode_abi(
            "borrow",
            [
                market.to_tuple(),
                amount,  # assets
                0,       # shares (use amount as reference)
                Web3.to_checksum_address(on_behalf),
                Web3.to_checksum_address(receiver),
                EMPTY_HOOKS,
            ],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._morpho_address,
            data=data,
            private_key=private_key,
        )

    # ---- Repay ----

    def repay(
        self,
        market: MarketParams,
        amount: int = 0,
        shares: int = 0,
        on_behalf: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Repay borrowed assets.
        amount=0 and shares>0 → repay by shares (full amount)
        amount>0 and shares=0 → repay specified amount
        """
        assert amount > 0 or shares > 0, "At least one of amount or shares must be specified"
        signer_addr = get_address(private_key)
        on_behalf = on_behalf or signer_addr

        # Check approval (need to authorize loanToken)
        allowance = check_allowance(
            self.chain_id, market.loan_token, signer_addr, self._morpho_address
        )
        if allowance < amount:
            approve_token(
                self.chain_id, market.loan_token,
                self._morpho_address, 2**256 - 1,  # max approve
                private_key,
            )

        data = self.contract.encode_abi(
            "repay",
            [
                market.to_tuple(),
                amount,
                shares,
                Web3.to_checksum_address(on_behalf),
                EMPTY_HOOKS,
            ],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._morpho_address,
            data=data,
            private_key=private_key,
        )

    # ---- Withdraw Supply ----

    def withdraw(
        self,
        market: MarketParams,
        amount: int = 0,
        shares: int = 0,
        on_behalf: Optional[str] = None,
        receiver: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Withdraw supplied assets"""
        assert amount > 0 or shares > 0, "At least one of amount or shares must be specified"
        signer_addr = get_address(private_key)
        on_behalf = on_behalf or signer_addr
        receiver = receiver or signer_addr

        data = self.contract.encode_abi(
            "withdraw",
            [
                market.to_tuple(),
                amount,
                shares,
                Web3.to_checksum_address(on_behalf),
                Web3.to_checksum_address(receiver),
                EMPTY_HOOKS,
            ],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._morpho_address,
            data=data,
            private_key=private_key,
        )

    # ---- Withdraw Collateral ----

    def withdraw_collateral(
        self,
        market: MarketParams,
        amount: int,
        on_behalf: Optional[str] = None,
        receiver: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Withdraw collateral"""
        signer_addr = get_address(private_key)
        on_behalf = on_behalf or signer_addr
        receiver = receiver or signer_addr

        data = self.contract.encode_abi(
            "withdrawCollateral",
            [
                market.to_tuple(),
                amount,
                Web3.to_checksum_address(on_behalf),
                Web3.to_checksum_address(receiver),
                EMPTY_HOOKS,
            ],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._morpho_address,
            data=data,
            private_key=private_key,
        )

    # ---- Queries ----

    def get_position(
        self, market: MarketParams, user: str
    ) -> Tuple[int, int, int]:
        """Query user position → (supplyShares, borrowShares, collateral)"""
        return self.contract.functions.position(
            market.market_id, Web3.to_checksum_address(user)
        ).call()

    def get_market_info(self, market: MarketParams) -> Dict[str, Any]:
        """Query market state"""
        result = self.contract.functions.market(market.market_id).call()
        return {
            "total_supply_assets": result[0],
            "total_supply_shares": result[1],
            "total_borrow_assets": result[2],
            "total_borrow_shares": result[3],
            "last_update": result[4],
            "fee": result[5],
            "utilization": result[2] / result[0] if result[0] > 0 else 0,
        }
