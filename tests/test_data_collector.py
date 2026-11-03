"""
test_data_collector.py — Unit Tests for Dataset Collection Tool

Run with: python -m pytest tests/test_data_collector.py -v
"""

import sys
import os
import pytest
from pathlib import Path
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.serial_reader import SerialReader
from backend.data_collector import DataCollector
from backend.utils import DATASET_COLUMNS


class TestDataCollector:
    """Tests for DataCollector class."""

    def test_record_gesture_mock(self, tmp_path):
        reader = SerialReader(mock=True)
        reader.connect()

        collector = DataCollector(serial_reader=reader, output_dir=tmp_path, samples_per_session=10)
        saved_file = collector.record_gesture(
            gesture="PEACE",
            participant_id="P_TEST",
            session_id="S_TEST",
            countdown_sec=0,  # skip countdown for fast testing
            num_samples=10,
        )

        reader.disconnect()

        assert saved_file is not None
        assert saved_file.exists()
        assert "PEACE_P_TEST_S_TEST" in saved_file.name

        df = pd.read_csv(saved_file)
        assert len(df) == 10
        assert list(df.columns) == DATASET_COLUMNS
        assert (df["gesture"] == "PEACE").all()
        assert (df["participant_id"] == "P_TEST").all()
        assert (df["session_id"] == "S_TEST").all()

    def test_invalid_gesture_raises(self, tmp_path):
        reader = SerialReader(mock=True)
        reader.connect()
        collector = DataCollector(serial_reader=reader, output_dir=tmp_path)

        with pytest.raises(ValueError):
            collector.record_gesture(
                gesture="NON_EXISTENT_GESTURE",
                countdown_sec=0,
            )
        reader.disconnect()

