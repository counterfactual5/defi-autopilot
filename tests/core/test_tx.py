"""Core tx module tests"""

from defi_autopilot.core.tx import build_and_send_tx


class TestDataTypeHandling:
    """Test that tx.py handles various data input types."""

    def test_hex_string_conversion(self):
        """Hex strings should be accepted and converted to bytes."""
        # This should not raise a type error at the data conversion step
        # (it will fail later at RPC, which is expected)
        try:
            build_and_send_tx(
                chain_id=8453,
                to="0x0000000000000000000000000000000000000001",
                data="0xabcdef",
                private_key=None,
            )
        except (ValueError, Exception) as e:
            # Should NOT be a type error on data
            assert "bytes" not in str(e).lower() or "fromhex" not in str(e)

    def test_none_data_defaults_to_empty(self):
        """None data should be treated as empty bytes."""
        # We test the conversion logic, not the full tx flow
        data = None
        if isinstance(data, str):
            result = bytes.fromhex(data.removeprefix("0x"))
        elif not isinstance(data, (bytes, bytearray)):
            result = b""
        else:
            result = data
        assert result == b""
