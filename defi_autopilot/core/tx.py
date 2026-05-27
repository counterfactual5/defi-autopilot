"""defi-autopilot 交易广播模块"""

import time
from typing import Optional, Dict, Any
from web3 import Web3
from web3.types import TxReceipt, TxParams

from .rpc import get_w3
from .signer import get_signer


GAS_MULTIPLIER = 1.1  # Gas 估算加成 10%


def build_and_send_tx(
    chain_id: int,
    to: str,
    data: bytes,
    value: int = 0,
    gas_limit: Optional[int] = None,
    max_fee_per_gas: Optional[int] = None,
    max_priority_fee: Optional[int] = None,
    private_key: Optional[str] = None,
    wait_for_receipt: bool = True,
    timeout: int = 120,
) -> Dict[str, Any]:
    """
    构建、签名、发送交易，并等待回执。
    """
    w3 = get_w3(chain_id)
    signer = get_signer(private_key)
    address = Web3.to_checksum_address(signer.address)

    # 获取 nonce
    nonce = w3.eth.get_transaction_count(address)

    # 估算 gas
    if gas_limit is None:
        try:
            estimated = w3.eth.estimate_gas({
                "from": address,
                "to": Web3.to_checksum_address(to),
                "data": data,
                "value": value,
            })
            gas_limit = int(estimated * GAS_MULTIPLIER)
        except Exception as e:
            raise RuntimeError(f"Gas 估算失败: {e}")

    # 获取 EIP-1559 费用
    if max_fee_per_gas is None:
        block = w3.eth.get_block("latest")
        base_fee = block.get("baseFeePerGas", w3.eth.gas_price)
        if max_priority_fee is None:
            max_priority_fee = w3.eth.max_priority_fee
        max_fee_per_gas = base_fee * 2 + max_priority_fee

    tx: TxParams = {
        "from": address,
        "to": Web3.to_checksum_address(to),
        "data": data,
        "value": value,
        "nonce": nonce,
        "gas": gas_limit,
        "maxFeePerGas": max_fee_per_gas,
        "maxPriorityFeePerGas": max_priority_fee,
        "chainId": chain_id,
    }

    # 签名
    signed = w3.eth.account.sign_transaction(tx, signer.key)

    # 发送
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

    result = {
        "tx_hash": tx_hash.hex(),
        "chain_id": chain_id,
        "from": address,
        "to": to,
    }

    if wait_for_receipt:
        receipt = wait_receipt(w3, tx_hash, timeout=timeout)
        result["status"] = receipt.get("status")
        result["block_number"] = receipt.get("blockNumber")
        result["gas_used"] = receipt.get("gasUsed")

    return result


def wait_receipt(
    w3: Web3, tx_hash: bytes, timeout: int = 120, poll_interval: float = 1.0
) -> TxReceipt:
    """等待交易回执"""
    start = time.time()
    while time.time() - start < timeout:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt is not None:
            return receipt
        time.sleep(poll_interval)
    raise TimeoutError(f"交易 {tx_hash.hex()} 在 {timeout}s 内未确认")


def check_allowance(
    chain_id: int,
    token_address: str,
    owner: str,
    spender: str,
) -> int:
    """查询 ERC20 allowance"""
    w3 = get_w3(chain_id)
    erc20_abi = [
        {
            "constant": True,
            "inputs": [
                {"name": "_owner", "type": "address"},
                {"name": "_spender", "type": "address"},
            ],
            "name": "allowance",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function",
        }
    ]
    token = w3.eth.contract(
        address=Web3.to_checksum_address(token_address), abi=erc20_abi
    )
    return token.functions.allowance(
        Web3.to_checksum_address(owner), Web3.to_checksum_address(spender)
    ).call()


def approve_token(
    chain_id: int,
    token_address: str,
    spender: str,
    amount: int,
    private_key: Optional[str] = None,
) -> Dict[str, Any]:
    """授权 ERC20 token"""
    erc20_approve_abi = [
        {
            "constant": False,
            "inputs": [
                {"name": "_spender", "type": "address"},
                {"name": "_value", "type": "uint256"},
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function",
        }
    ]
    w3 = get_w3(chain_id)
    token = w3.eth.contract(
        address=Web3.to_checksum_address(token_address), abi=erc20_approve_abi
    )
    data = token.encode_abi("approve", [Web3.to_checksum_address(spender), amount])
    return build_and_send_tx(
        chain_id=chain_id,
        to=token_address,
        data=data,
        private_key=private_key,
    )
