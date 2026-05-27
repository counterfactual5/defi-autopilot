"""defi-autopilot transaction broadcast module"""

import time
from typing import Optional, Dict, Any
from web3 import Web3
from web3.types import TxReceipt, TxParams

from .rpc import get_w3
from .signer import get_signer


GAS_MULTIPLIER = 1.1  # Gas estimation markup: 10%


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
    Build, sign, send a transaction, and wait for receipt.
    """
    w3 = get_w3(chain_id)
    signer = get_signer(private_key)
    address = Web3.to_checksum_address(signer.address)

    # Get nonce
    nonce = w3.eth.get_transaction_count(address)

    # Estimate gas
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
            raise RuntimeError(f"Gas estimation failed: {e}")

    # Get EIP-1559 fees
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

    # Sign
    signed = w3.eth.account.sign_transaction(tx, signer.key)

    # Send
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
    """Wait for transaction receipt"""
    start = time.time()
    while time.time() - start < timeout:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt is not None:
            return receipt
        time.sleep(poll_interval)
    raise TimeoutError(f"Transaction {tx_hash.hex()} not confirmed within {timeout}s")


def check_allowance(
    chain_id: int,
    token_address: str,
    owner: str,
    spender: str,
) -> int:
    """Query ERC20 allowance"""
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
    """Approve ERC20 token spending"""
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
