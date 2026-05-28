"""
Compound V3 (Comet) Protocol Client

Compound V3 uses a single-asset Comet contract per market.
Each Comet has a base asset (e.g. USDC) and multiple collateral assets.

Core operations: supply, withdraw, borrow, repay
Collateral: supplyCollateral, withdrawCollateral
Queries: balanceOf, borrowBalanceOf, getAssetInfo, getUserCollateral

Supported chains: Ethereum, Base, Arbitrum, Polygon
"""

from typing import Optional, Dict, Any, List

from web3 import Web3

from defi_autopilot.core.rpc import get_w3, get_chain_config
from defi_autopilot.core.signer import get_address
from defi_autopilot.core.tx import (
    build_and_send_tx,
    check_allowance,
    approve_token,
    enforce_token_policy,
)


# Comet ABI (core functions)
COMET_ABI = [
    # supply(asset, amount)
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "supply",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # withdraw(asset, amount)
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # supplyCollateral(asset, amount)
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "supplyCollateral",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # withdrawCollateral(asset, amount)
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "withdrawCollateral",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # balanceOf(account)
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # borrowBalanceOf(account)
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "borrowBalanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # getAssetInfo(uint8)
    {
        "inputs": [{"name": "i", "type": "uint8"}],
        "name": "getAssetInfo",
        "outputs": [
            {"name": "offset", "type": "uint8"},
            {"name": "asset", "type": "address"},
            {"name": "priceFeed", "type": "address"},
            {"name": "scale", "type": "uint256"},
            {"name": "borrowCollateralFactor", "type": "uint64"},
            {"name": "liquidateCollateralFactor", "type": "uint64"},
            {"name": "liquidationFactor", "type": "uint64"},
            {"name": "supplyCap", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # getUserCollateral(account, asset)
    {
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "asset", "type": "address"},
        ],
        "name": "getUserCollateral",
        "outputs": [{"name": "", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function",
    },
    # baseToken
    {
        "inputs": [],
        "name": "baseToken",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    # numAssets
    {
        "inputs": [],
        "name": "numAssets",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# ============================================================
# Compound V3 Comet Markets
# ============================================================

COMET_MARKETS = {
    # Ethereum
    1: {
        "USDC": {
            "comet": "0xc3d688B66703497DAA19211EEdff47f25384cdc3",
            "base_token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "collaterals": {
                "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                "stETH": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
                "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            },
        },
        "WETH": {
            "comet": "0xA17581A9E3356d9A898b421fAB2AA2d7aF597eE2",
            "base_token": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "collaterals": {
                "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
            },
        },
    },
    # Base
    8453: {
        "USDC": {
            "comet": "0x46e6B214B524310239732D51387075E0e70970Bf",
            "base_token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "collaterals": {
                "WETH": "0x4200000000000000000000000000000000000006",
                "cbBTC": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
            },
        },
    },
    # Arbitrum
    42161: {
        "USDC": {
            "comet": "0x9c4ec768c28520B50860ea7a15bd7213a9fF58bf",
            "base_token": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            "collaterals": {
                "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
                "WBTC": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
            },
        },
    },
    # Polygon
    137: {
        "USDC": {
            "comet": "0xF25212E676D1F7F89Cd72fFEe66158f541246445",
            "base_token": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "collaterals": {
                "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
                "WBTC": "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
            },
        },
    },
}


class CompoundV3Client:
    """Compound V3 (Comet) Protocol Client"""

    def __init__(self, chain_id: int = 8453, market: str = "USDC"):
        self.chain_id = chain_id
        self.config = get_chain_config(chain_id)
        self.w3 = get_w3(chain_id)

        chain_markets = COMET_MARKETS.get(chain_id)
        if chain_markets is None:
            raise ValueError(f"Compound V3 not deployed on chain {chain_id}")

        market_info = chain_markets.get(market.upper())
        if market_info is None:
            raise ValueError(
                f"Market {market} not found on chain {chain_id}. "
                f"Available: {list(chain_markets.keys())}"
            )

        self._market = market_info
        self._comet_addr = Web3.to_checksum_address(market_info["comet"])
        self._comet = self.w3.eth.contract(address=self._comet_addr, abi=COMET_ABI)

    # ---- Supply (base asset) ----

    def supply(
        self,
        amount: int,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Supply base asset (e.g. USDC) to earn interest."""
        signer_addr = get_address(private_key)
        base_token = self._market["base_token"]

        # ERC-20 notional gate (chokepoint only sees native value).
        enforce_token_policy(self.chain_id, base_token, amount)

        allowance = check_allowance(self.chain_id, base_token, signer_addr, self._comet_addr)
        if allowance < amount:
            approve_token(self.chain_id, base_token, self._comet_addr, 2**256 - 1, private_key)

        data = self._comet.encode_abi(
            "supply",
            [Web3.to_checksum_address(base_token), amount],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._comet_addr,
            data=data,
            private_key=private_key,
        )

    # ---- Withdraw (base asset) ----

    def withdraw(
        self,
        amount: int,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Withdraw supplied base asset."""
        base_token = self._market["base_token"]
        data = self._comet.encode_abi(
            "withdraw",
            [Web3.to_checksum_address(base_token), amount],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._comet_addr,
            data=data,
            private_key=private_key,
        )

    # ---- Supply Collateral ----

    def supply_collateral(
        self,
        asset_name: str,
        amount: int,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Supply a collateral asset."""
        signer_addr = get_address(private_key)
        asset_addr = self._market["collaterals"].get(asset_name.upper())
        if asset_addr is None:
            raise ValueError(
                f"Unknown collateral: {asset_name}. "
                f"Available: {list(self._market['collaterals'].keys())}"
            )

        # ERC-20 notional gate (chokepoint only sees native value).
        enforce_token_policy(self.chain_id, asset_addr, amount)

        allowance = check_allowance(self.chain_id, asset_addr, signer_addr, self._comet_addr)
        if allowance < amount:
            approve_token(self.chain_id, asset_addr, self._comet_addr, 2**256 - 1, private_key)

        data = self._comet.encode_abi(
            "supplyCollateral",
            [Web3.to_checksum_address(asset_addr), amount],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._comet_addr,
            data=data,
            private_key=private_key,
        )

    # ---- Withdraw Collateral ----

    def withdraw_collateral(
        self,
        asset_name: str,
        amount: int,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Withdraw a collateral asset."""
        asset_addr = self._market["collaterals"].get(asset_name.upper())
        if asset_addr is None:
            raise ValueError(f"Unknown collateral: {asset_name}")

        data = self._comet.encode_abi(
            "withdrawCollateral",
            [Web3.to_checksum_address(asset_addr), amount],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._comet_addr,
            data=data,
            private_key=private_key,
        )

    # ---- Borrow (base asset) ----

    def borrow(
        self,
        amount: int,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Borrow base asset. In Comet, borrowing = withdrawing more than supplied.
        Equivalent to withdraw(baseToken, amount) when you have no supply.
        """
        base_token = self._market["base_token"]

        # ERC-20 notional gate (chokepoint only sees native value).
        enforce_token_policy(self.chain_id, base_token, amount)

        data = self._comet.encode_abi(
            "withdraw",
            [Web3.to_checksum_address(base_token), amount],
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._comet_addr,
            data=data,
            private_key=private_key,
        )

    # ---- Repay (base asset) ----

    def repay(
        self,
        amount: int,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Repay borrowed base asset. In Comet, repaying = supplying.
        """
        return self.supply(amount, private_key)

    # ---- Queries ----

    def get_supply_balance(self, user: str) -> int:
        """Get base asset supply balance."""
        return self._comet.functions.balanceOf(Web3.to_checksum_address(user)).call()

    def get_borrow_balance(self, user: str) -> int:
        """Get base asset borrow balance."""
        return self._comet.functions.borrowBalanceOf(Web3.to_checksum_address(user)).call()

    def get_collateral_balance(self, user: str, asset_name: str) -> int:
        """Get collateral balance for an asset."""
        asset_addr = self._market["collaterals"].get(asset_name.upper())
        if asset_addr is None:
            raise ValueError(f"Unknown collateral: {asset_name}")
        return self._comet.functions.getUserCollateral(
            Web3.to_checksum_address(user),
            Web3.to_checksum_address(asset_addr),
        ).call()

    def get_market_assets(self) -> List[Dict[str, Any]]:
        """List all assets in the market."""
        num_assets = self._comet.functions.numAssets().call()
        assets = []
        for i in range(num_assets):
            info = self._comet.functions.getAssetInfo(i).call()
            assets.append({
                "asset": info[1],
                "price_feed": info[2],
                "borrow_collateral_factor": info[4],
                "liquidate_collateral_factor": info[5],
                "supply_cap": info[7],
            })
        return assets
