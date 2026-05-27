"""
Curve Finance Protocol Client

Curve is the leading stablecoin and like-asset DEX.
Supports swap, add_liquidity, remove_liquidity across multiple pools.

Curve uses per-pool contracts (each pool has its own swap/LP functions).
This client supports the most common pool types:
  - StableSwap (legacy): exchange(i, j, dx, min_dy)
  - StableNG: exchange(i, j, dx, min_dy)
  - CryptoSwap: exchange(i, j, dx, min_dy)

For swap routing across pools, use the Curve Router.
"""

from typing import Optional, Dict, Any, List

from web3 import Web3

from defi_autopilot.core.rpc import get_w3, get_chain_config
from defi_autopilot.core.signer import get_address
from defi_autopilot.core.tx import build_and_send_tx, check_allowance, approve_token


# Common Curve pool ABI (exchange + LP functions)
CURVE_POOL_ABI = [
    # exchange(i, j, dx, min_dy) — StableSwap
    {
        "inputs": [
            {"name": "i", "type": "int128"},
            {"name": "j", "type": "int128"},
            {"name": "_dx", "type": "uint256"},
            {"name": "_min_dy", "type": "uint256"},
        ],
        "name": "exchange",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # get_dy(i, j, dx) — quote
    {
        "inputs": [
            {"name": "i", "type": "int128"},
            {"name": "j", "type": "int128"},
            {"name": "_dx", "type": "uint256"},
        ],
        "name": "get_dy",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # add_liquidity(amounts, min_mint_amount)
    {
        "inputs": [
            {"name": "amounts", "type": "uint256[8]"},
            {"name": "min_mint_amount", "type": "uint256"},
        ],
        "name": "add_liquidity",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # remove_liquidity(amount, min_amounts)
    {
        "inputs": [
            {"name": "_amount", "type": "uint256"},
            {"name": "min_amounts", "type": "uint256[8]"},
        ],
        "name": "remove_liquidity",
        "outputs": [{"name": "", "type": "uint256[8]"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # remove_liquidity_one_coin(token_amount, i, min_amount)
    {
        "inputs": [
            {"name": "_token_amount", "type": "uint256"},
            {"name": "i", "type": "int128"},
            {"name": "_min_amount", "type": "uint256"},
        ],
        "name": "remove_liquidity_one_coin",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # coins(i) — get token address by index
    {
        "inputs": [{"name": "arg0", "type": "int128"}],
        "name": "coins",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    # balances(i) — get pool balance by index
    {
        "inputs": [{"name": "arg0", "type": "int128"}],
        "name": "balances",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # lp_token
    {
        "inputs": [],
        "name": "lp_token",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# ============================================================
# Well-known Curve Pools
# ============================================================

CURVE_POOLS = {
    1: {
        # 3pool: DAI/USDC/USDT
        "3pool": {
            "address": "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7",
            "coins": [
                "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI
                "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
                "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
            ],
            "lp_token": "0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490",
        },
        # stETH pool: stETH/ETH
        "steth": {
            "address": "0xDC24316b9AE028F1497c275EB9192a3Ea0f67022",
            "coins": [
                "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # ETH
                "0x06325440D014e39736583c165C2963BA99fAf14E",  # stETH
            ],
            "lp_token": "0x06325440D014e39736583c165C2963BA99fAf14E",
        },
    },
    8453: {
        # Base USDC/USDbC pool
        "usdc-usdbc": {
            "address": "0x76578Ecf3a6cCc9dB3598B35e5c34c93055ABD25",
            "coins": [
                "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC
                "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",  # USDbC
            ],
            "lp_token": "0x8eeD3e158cDA686156fE34a6bEc1D06A08C9d84E",
        },
    },
    42161: {
        # Arbitrum 2pool: USDC/USDT
        "2pool": {
            "address": "0x7f90122BF0700F9E7e1F688fe926940E8839F353",
            "coins": [
                "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",  # USDC
                "0xFd086bD7e825dcE0D0f7a02b84D9EFA4BB76c2A9",  # USDT
            ],
            "lp_token": "0x7f90122BF0700F9E7e1F688fe926940E8839F353",
        },
    },
    10: {
        # Optimism USDC/USDT pool
        "usdc-usdt": {
            "address": "0x1337BedC9D22ecbe766dF105c9623922A27963EC",
            "coins": [
                "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",  # USDC
                "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",  # USDT
            ],
            "lp_token": "0x1337BedC9D22ecbe766dF105c9623922A27963EC",
        },
    },
}


class CurveClient:
    """Curve Finance Pool Client"""

    def __init__(self, chain_id: int = 8453, pool_name: str = "usdc-usdbc"):
        self.chain_id = chain_id
        self.config = get_chain_config(chain_id)
        self.w3 = get_w3(chain_id)

        chain_pools = CURVE_POOLS.get(chain_id)
        if chain_pools is None:
            raise ValueError(f"Curve pools not configured for chain {chain_id}")

        pool_info = chain_pools.get(pool_name.lower())
        if pool_info is None:
            raise ValueError(
                f"Pool {pool_name} not found on chain {chain_id}. "
                f"Available: {list(chain_pools.keys())}"
            )

        self._pool_info = pool_info
        self._pool_addr = Web3.to_checksum_address(pool_info["address"])
        self._pool = self.w3.eth.contract(address=self._pool_addr, abi=CURVE_POOL_ABI)

    def _get_coin_index(self, token_address: str) -> int:
        """Find coin index by address."""
        addr = Web3.to_checksum_address(token_address)
        for i, coin in enumerate(self._pool_info["coins"]):
            if Web3.to_checksum_address(coin) == addr:
                return i
        raise ValueError(f"Token {token_address} not in pool")

    # ---- Swap ----

    def swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        min_amount_out: int = 0,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Swap tokens in a Curve pool."""
        signer_addr = get_address(private_key)
        i = self._get_coin_index(token_in)
        j = self._get_coin_index(token_out)

        # Approve pool to spend input token
        in_addr = self._pool_info["coins"][i]
        if in_addr != "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
            allowance = check_allowance(self.chain_id, in_addr, signer_addr, self._pool_addr)
            if allowance < amount_in:
                approve_token(self.chain_id, in_addr, self._pool_addr, 2**256 - 1, private_key)

        data = self._pool.encode_abi("exchange", [i, j, amount_in, min_amount_out])
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._pool_addr,
            data=data,
            private_key=private_key,
        )

    # ---- Quote ----

    def get_dy(self, token_in: str, token_out: str, amount_in: int) -> int:
        """Get expected output amount for a swap."""
        i = self._get_coin_index(token_in)
        j = self._get_coin_index(token_out)
        return self._pool.functions.get_dy(i, j, amount_in).call()

    # ---- Add Liquidity ----

    def add_liquidity(
        self,
        amounts: List[int],
        min_mint_amount: int = 0,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add liquidity to the pool.
        amounts: list of amounts per coin (0 for coins not being deposited).
        """
        signer_addr = get_address(private_key)

        # Pad to 8 elements (Curve ABI expects uint256[8])
        padded = amounts + [0] * (8 - len(amounts))

        # Approve all non-zero amounts
        for i, amt in enumerate(amounts):
            if amt > 0 and i < len(self._pool_info["coins"]):
                coin = self._pool_info["coins"][i]
                if coin != "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                    allowance = check_allowance(
                        self.chain_id, coin, signer_addr, self._pool_addr
                    )
                    if allowance < amt:
                        approve_token(self.chain_id, coin, self._pool_addr, 2**256 - 1, private_key)

        data = self._pool.encode_abi("add_liquidity", [padded, min_mint_amount])
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._pool_addr,
            data=data,
            private_key=private_key,
        )

    # ---- Remove Liquidity ----

    def remove_liquidity_one_coin(
        self,
        lp_amount: int,
        coin_index: int,
        min_amount: int = 0,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Remove liquidity into a single coin."""
        data = self._pool.encode_abi(
            "remove_liquidity_one_coin", [lp_amount, coin_index, min_amount]
        )
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=self._pool_addr,
            data=data,
            private_key=private_key,
        )

    # ---- Queries ----

    def get_pool_balances(self) -> List[int]:
        """Get current balances of all coins in the pool."""
        balances = []
        for i in range(len(self._pool_info["coins"])):
            balances.append(self._pool.functions.balances(i).call())
        return balances
