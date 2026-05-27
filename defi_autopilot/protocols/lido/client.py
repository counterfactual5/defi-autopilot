"""
Lido Liquid Staking Protocol Client

Lido is the largest liquid staking protocol on Ethereum.
Core operation: deposit ETH → receive stETH (rebasing) or wstETH (non-rebasing).

Contract addresses:
  - Lido (stETH): 0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84 (Ethereum only)
  - wstETH: wrapped stETH, deployed on L2s via bridge

stETH rebases daily (balance increases). wstETH is static balance, price appreciates.
"""

from typing import Optional, Dict, Any

from web3 import Web3

from defi_autopilot.core.rpc import get_w3, get_chain_config
from defi_autopilot.core.tx import build_and_send_tx


# Lido core contract ABI (minimal)
LIDO_ABI = [
    # submit(referral) — payable, mints stETH
    {
        "inputs": [
            {"name": "_referral", "type": "address"},
        ],
        "name": "submit",
        "outputs": [],
        "stateMutability": "payable",
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
    # getTotalPooledEther
    {
        "inputs": [],
        "name": "getTotalPooledEther",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # getTotalShares
    {
        "inputs": [],
        "name": "getTotalShares",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # sharesOf(account)
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "sharesOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# wstETH (wrapped stETH) ABI
WSTETH_ABI = [
    # wrap(uint256) — convert stETH to wstETH
    {
        "inputs": [{"name": "_stETHAmount", "type": "uint256"}],
        "name": "wrap",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # unwrap(uint256) — convert wstETH to stETH
    {
        "inputs": [{"name": "_wstETHAmount", "type": "uint256"}],
        "name": "unwrap",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # getWstETHByStETH(uint256)
    {
        "inputs": [{"name": "_stETHAmount", "type": "uint256"}],
        "name": "getWstETHByStETH",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # getStETHByWstETH(uint256)
    {
        "inputs": [{"name": "_wstETHAmount", "type": "uint256"}],
        "name": "getStETHByWstETH",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # stEthPerToken()
    {
        "inputs": [],
        "name": "stEthPerToken",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
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
]

# ============================================================
# Contract Addresses
# ============================================================

LIDO_ADDRESSES = {
    # Lido stETH — Ethereum only (native staking)
    1: {
        "lido": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
        "wstETH": "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0",
    },
    # L2s: wstETH bridged (no native staking, but can wrap/unwrap)
    8453: {
        "wstETH": "0xc1CBa3fCea347f7fDCaB627dA9aF9e97D0e01e7D",
    },
    42161: {
        "wstETH": "0x5979D7b546E38E414F7E9822514be443A4800529",
    },
    10: {
        "wstETH": "0x1F32b1c2345538c0c6f582fCB022739c4A194Ebb",
    },
    137: {
        "wstETH": "0x03b54A6e9a984069379fae1a4fC4dBAE93B9BD0B",
    },
}


class LidoClient:
    """Lido Liquid Staking Protocol Client"""

    def __init__(self, chain_id: int = 1):
        self.chain_id = chain_id
        self.config = get_chain_config(chain_id)
        self.w3 = get_w3(chain_id)

        if chain_id not in LIDO_ADDRESSES:
            raise ValueError(f"Lido not deployed on chain {chain_id}")

        self._addresses = LIDO_ADDRESSES[chain_id]
        self._has_native_staking = "lido" in self._addresses

    @property
    def supports_native_staking(self) -> bool:
        """Whether this chain supports native ETH → stETH staking."""
        return self._has_native_staking

    # ---- Stake (Ethereum only) ----

    def stake(
        self,
        amount_wei: int,
        referral: str = "0x0000000000000000000000000000000000000000",
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Stake ETH to receive stETH (Ethereum mainnet only).
        Sends ETH to Lido contract, mints stETH 1:1.
        """
        if not self._has_native_staking:
            raise ValueError("Native staking only available on Ethereum mainnet")

        lido_addr = Web3.to_checksum_address(self._addresses["lido"])
        lido = self.w3.eth.contract(address=lido_addr, abi=LIDO_ABI)

        data = lido.encode_abi("submit", [Web3.to_checksum_address(referral)])

        return build_and_send_tx(
            chain_id=self.chain_id,
            to=lido_addr,
            data=data,
            value=amount_wei,
            private_key=private_key,
        )

    # ---- Wrap stETH → wstETH ----

    def wrap(
        self,
        steth_amount: int,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Wrap stETH to wstETH (non-rebasing, static balance)."""
        wsteth_addr = Web3.to_checksum_address(self._addresses["wstETH"])
        wsteth = self.w3.eth.contract(address=wsteth_addr, abi=WSTETH_ABI)

        data = wsteth.encode_abi("wrap", [steth_amount])
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=wsteth_addr,
            data=data,
            private_key=private_key,
        )

    # ---- Unwrap wstETH → stETH ----

    def unwrap(
        self,
        wsteth_amount: int,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Unwrap wstETH back to stETH."""
        wsteth_addr = Web3.to_checksum_address(self._addresses["wstETH"])
        wsteth = self.w3.eth.contract(address=wsteth_addr, abi=WSTETH_ABI)

        data = wsteth.encode_abi("unwrap", [wsteth_amount])
        return build_and_send_tx(
            chain_id=self.chain_id,
            to=wsteth_addr,
            data=data,
            private_key=private_key,
        )

    # ---- Queries ----

    def get_steth_balance(self, user: str) -> int:
        """Get stETH balance (Ethereum only, includes rebasing)."""
        if not self._has_native_staking:
            raise ValueError("stETH balance only available on Ethereum mainnet")

        lido_addr = Web3.to_checksum_address(self._addresses["lido"])
        lido = self.w3.eth.contract(address=lido_addr, abi=LIDO_ABI)
        return lido.functions.balanceOf(Web3.to_checksum_address(user)).call()

    def get_wsteth_balance(self, user: str) -> int:
        """Get wstETH balance."""
        wsteth_addr = Web3.to_checksum_address(self._addresses["wstETH"])
        wsteth = self.w3.eth.contract(address=wsteth_addr, abi=WSTETH_ABI)
        return wsteth.functions.balanceOf(Web3.to_checksum_address(user)).call()

    def get_steth_per_wsteth(self) -> int:
        """Get current stETH per 1 wstETH (increases over time)."""
        wsteth_addr = Web3.to_checksum_address(self._addresses["wstETH"])
        wsteth = self.w3.eth.contract(address=wsteth_addr, abi=WSTETH_ABI)
        return wsteth.functions.stEthPerToken().call()

    def get_total_pooled_ether(self) -> int:
        """Get total ETH pooled in Lido (Ethereum only)."""
        if not self._has_native_staking:
            raise ValueError("Only available on Ethereum mainnet")

        lido_addr = Web3.to_checksum_address(self._addresses["lido"])
        lido = self.w3.eth.contract(address=lido_addr, abi=LIDO_ABI)
        return lido.functions.getTotalPooledEther().call()
