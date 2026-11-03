"""
test_serial_reader.py — Unit Tests for Serial Interface & Mock Reader

Run with: python -m pytest tests/test_serial_reader.py -v
"""

import sys
import os
import json
import pytest
from pathlib import Path
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.serial_reader import SerialReader, MockSerialConnection
from backend.utils import DATASET_COLUMNS


class TestMockSerialConnection:
    """Tests for MockSerialConnection generator."""

    def test_mock_connection_lifecycle(self):
        conn = MockSerialConnection(sample_rate_hz=100.0)
        assert conn.is_open is True
        raw_bytes = conn.readline()
        assert raw_bytes.endswith(b"\n")
        parsed = json.loads(raw_bytes.decode("utf-8"))
        assert "flex" in parsed
        assert len(parsed["flex"]) == 5
        conn.close()
        assert conn.is_open is False


class TestSerialReader:
    """Tests for SerialReader class in mock and headless mode."""

    def test_mock_reader_streaming(self):
        reader = SerialReader(mock=True)
        assert reader.connect() is True
        assert reader.is_connected is True

        is_valid, packet, raw = reader.read_packet()
        assert is_valid is True
        assert isinstance(packet, dict)
        assert "timestamp_ms" in packet
        assert len(packet["flex"]) == 5
        assert len(packet["accel"]) == 3
        assert len(packet["gyro"]) == 3

        reader.disconnect()
        assert reader.is_connected is False

    def test_send_command(self):
        reader = SerialReader(mock=True)
        reader.connect()
        # Should not crash and return True
        res = reader.send_command({"led": 1})
        assert res is True
        reader.disconnect()

    def test_csv_logging(self, tmp_path):
        csv_file = tmp_path / "test_log.csv"
        reader = SerialReader(mock=True, csv_path=str(csv_file))
        reader.connect()

        is_valid, packet, _ = reader.read_packet()
        reader.log_packet(packet, gesture="POINTING", participant_id="P99", session_id="S99")
        reader.disconnect()

        assert csv_file.exists()
        df = pd.read_csv(csv_file)
        assert len(df) == 1
        assert df.iloc[0]["gesture"] == "POINTING"
        assert df.iloc[0]["participant_id"] == "P99"
        assert list(df.columns) == DATASET_COLUMNS

    def test_stream_generator_limit(self):
        reader = SerialReader(mock=True)
        reader.connect()
        packets = list(reader.stream(max_packets=5))
        assert len(packets) == 5
        reader.disconnect()

