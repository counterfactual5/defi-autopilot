"""defi-autopilot Signer 管理"""

import os
from typing import Optional
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3


def get_signer(private_key: Optional[str] = None) -> LocalAccount:
    """
    获取签名账户。
    优先使用传入的 private_key，否则从环境变量 SIGNER_PRIVATE_KEY 读取。
    """
    key = private_key or os.environ.get("SIGNER_PRIVATE_KEY")
    if not key:
        raise ValueError("未提供私钥（通过参数或 SIGNER_PRIVATE_KEY 环境变量）")

    if not key.startswith("0x"):
        key = "0x" + key

    return Account.from_key(key)


def get_address(private_key: Optional[str] = None) -> str:
    """获取签名地址（checksummed）"""
    signer = get_signer(private_key)
    return Web3.to_checksum_address(signer.address)
