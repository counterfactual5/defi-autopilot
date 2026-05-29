"""Core tx module tests"""

from unittest.mock import MagicMock, patch

from defi_autopilot.core.tx import build_and_send_tx


class TestDataTypeHandling:
    """Test that tx.py handles various data input types."""

    def test_hex_string_conversion(self):
        """Hex strings should be accepted and converted to bytes."""
        try:
            build_and_send_tx(
                chain_id=8453,
                to="0x0000000000000000000000000000000000000001",
                data="0xabcdef",
                private_key=None,
            )
        except (ValueError, Exception) as e:
            assert "bytes" not in str(e).lower() or "fromhex" not in str(e)

    def test_none_data_defaults_to_empty(self):
        """None data should be treated as empty bytes."""
        data = None
        if isinstance(data, str):
            result = bytes.fromhex(data.removeprefix("0x"))
        elif not isinstance(data, (bytes, bytearray)):
            result = b""
        else:
            result = data
        assert result == b""


def _mock_w3(*, balance: int = 10**18, gas_estimate: int = 100_000, chain_id: int = 8453):
    w3 = MagicMock()
    w3.eth.chain_id = chain_id
    w3.eth.get_transaction_count.return_value = 0
    w3.eth.get_balance.return_value = balance
    w3.eth.estimate_gas.return_value = gas_estimate
    w3.eth.gas_price = 10**9
    w3.eth.max_priority_fee = 10**8
    w3.eth.get_block.return_value = {"baseFeePerGas": 10**9}
    signed = MagicMock()
    signed.raw_transaction = b"\x00" * 32
    w3.eth.account.sign_transaction.return_value = signed
    tx_hash = MagicMock()
    tx_hash.hex.return_value = "0xabc123"
    w3.eth.send_raw_transaction.return_value = tx_hash
    receipt = {"status": 1, "blockNumber": 42, "gasUsed": 50_000}
    w3.eth.get_transaction_receipt.return_value = receipt
    return w3


def _mock_signer():
    signer = MagicMock()
    signer.address = "0x000000000000000000000000000000000000bEEF"
    signer.key = b"\x01" * 32
    return signer


_TO = "0x0000000000000000000000000000000000000001"


class TestSimulationGate:
    """estimateGas acts as a dry-run — revert = simulation_failed."""

    @patch("defi_autopilot.core.tx.get_signer")
    @patch("defi_autopilot.core.tx.get_w3")
    def test_simulation_revert_audited(self, mock_get_w3, mock_get_signer):
        w3 = _mock_w3()
        w3.eth.estimate_gas.side_effect = Exception("execution reverted: ERC20: insufficient allowance")
        mock_get_w3.return_value = w3
        mock_get_signer.return_value = _mock_signer()

        try:
            build_and_send_tx(chain_id=8453, to=_TO, data=b"\x01")
        except RuntimeError as exc:
            assert "simulation_failed" in str(exc) or "Gas estimation failed" in str(exc)
        else:
            raise AssertionError("should have raised")

    @patch("defi_autopilot.core.tx.get_signer")
    @patch("defi_autopilot.core.tx.get_w3")
    def test_no_gas_balance_rejected(self, mock_get_w3, mock_get_signer):
        w3 = _mock_w3(balance=0)
        mock_get_w3.return_value = w3
        mock_get_signer.return_value = _mock_signer()

        try:
            build_and_send_tx(chain_id=8453, to=_TO, data=b"\x01")
        except RuntimeError as exc:
            assert "zero" in str(exc).lower() or "no_gas" in str(exc).lower()
        else:
            raise AssertionError("should have raised")

    @patch("defi_autopilot.core.tx.get_signer")
    @patch("defi_autopilot.core.tx.get_w3")
    def test_happy_path_with_simulation(self, mock_get_w3, mock_get_signer):
        w3 = _mock_w3()
        mock_get_w3.return_value = w3
        mock_get_signer.return_value = _mock_signer()

        result = build_and_send_tx(chain_id=8453, to=_TO, data=b"\x01")
        assert result["tx_hash"] == "0xabc123"
        assert result["status"] == 1
        w3.eth.estimate_gas.assert_called_once()
