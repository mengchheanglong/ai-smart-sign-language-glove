"""
test_utils.py — Unit Tests for Backend Utilities

Run with: python -m pytest tests/ -v
"""

import pytest
import sys
import os

# Add the project root to path so we can import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils import validate_sensor_packet, GESTURE_CLASSES


class TestValidateSensorPacket:
    """Tests for the sensor packet validation function."""

    def test_valid_packet(self):
        """A properly formatted packet should pass validation."""
        packet = {
            "timestamp_ms": 12345,
            "flex": [1200, 1800, 2100, 1500, 1900],
            "accel": [0.1, -0.2, 9.81],
            "gyro": [0.0, 0.1, -0.05],
        }
        is_valid, error = validate_sensor_packet(packet)
        assert is_valid is True
        assert error is None

    def test_missing_timestamp(self):
        """Packet without timestamp_ms should fail."""
        packet = {
            "flex": [1200, 1800, 2100, 1500, 1900],
            "accel": [0.0, 0.0, 9.81],
            "gyro": [0.0, 0.0, 0.0],
        }
        is_valid, error = validate_sensor_packet(packet)
        assert is_valid is False
        assert "timestamp_ms" in error

    def test_missing_flex(self):
        """Packet without flex data should fail."""
        packet = {
            "timestamp_ms": 100,
            "accel": [0.0, 0.0, 9.81],
            "gyro": [0.0, 0.0, 0.0],
        }
        is_valid, error = validate_sensor_packet(packet)
        assert is_valid is False
        assert "flex" in error

    def test_wrong_flex_count(self):
        """Flex array with wrong number of sensors should fail."""
        packet = {
            "timestamp_ms": 100,
            "flex": [1200, 1800, 2100],  # Only 3 instead of 5
            "accel": [0.0, 0.0, 9.81],
            "gyro": [0.0, 0.0, 0.0],
        }
        is_valid, error = validate_sensor_packet(packet)
        assert is_valid is False
        assert "5" in error

    def test_flex_out_of_range(self):
        """Flex sensor value above 4095 should fail."""
        packet = {
            "timestamp_ms": 100,
            "flex": [1200, 1800, 5000, 1500, 1900],
            "accel": [0.0, 0.0, 9.81],
            "gyro": [0.0, 0.0, 0.0],
        }
        is_valid, error = validate_sensor_packet(packet)
        assert is_valid is False
        assert "outside range" in error

    def test_negative_timestamp(self):
        """Negative timestamp should fail."""
        packet = {
            "timestamp_ms": -100,
            "flex": [1200, 1800, 2100, 1500, 1900],
            "accel": [0.0, 0.0, 9.81],
            "gyro": [0.0, 0.0, 0.0],
        }
        is_valid, error = validate_sensor_packet(packet)
        assert is_valid is False
        assert "non-negative" in error

    def test_wrong_accel_count(self):
        """Accel array with wrong number of axes should fail."""
        packet = {
            "timestamp_ms": 100,
            "flex": [1200, 1800, 2100, 1500, 1900],
            "accel": [0.0, 0.0],  # Only 2 instead of 3
            "gyro": [0.0, 0.0, 0.0],
        }
        is_valid, error = validate_sensor_packet(packet)
        assert is_valid is False

    def test_empty_packet(self):
        """Empty dictionary should fail."""
        is_valid, error = validate_sensor_packet({})
        assert is_valid is False

    def test_zero_values_valid(self):
        """All-zero readings should be valid (sensor might be disconnected but data format is correct)."""
        packet = {
            "timestamp_ms": 0,
            "flex": [0, 0, 0, 0, 0],
            "accel": [0.0, 0.0, 0.0],
            "gyro": [0.0, 0.0, 0.0],
        }
        is_valid, error = validate_sensor_packet(packet)
        assert is_valid is True


class TestGestureClasses:
    """Tests for gesture class definitions."""

    def test_gesture_count(self):
        """Should have exactly 6 gesture classes."""
        assert len(GESTURE_CLASSES) == 6

    def test_required_gestures(self):
        """All required gestures should be defined."""
        required = ["OPEN_PALM", "CLOSED_FIST", "POINTING", "PEACE", "THUMBS_UP", "RESTING"]
        for gesture in required:
            assert gesture in GESTURE_CLASSES, f"Missing gesture: {gesture}"

    def test_no_duplicates(self):
        """No duplicate gesture names."""
        assert len(GESTURE_CLASSES) == len(set(GESTURE_CLASSES))


class TestFeatureExtraction:
    """Tests for feature engineering logic."""

    def test_extract_features_from_packet(self):
        """Extract features from JSON packet dict."""
        from backend.utils import extract_features, FEATURE_NAMES

        packet = {
            "timestamp_ms": 1000,
            "flex": [3200, 3100, 3050, 2900, 2800],
            "accel": [0.0, 0.0, 9.81],
            "gyro": [0.1, -0.2, 0.0],
        }
        feats = extract_features(packet)
        assert isinstance(feats, dict)
        for name in FEATURE_NAMES:
            assert name in feats, f"Missing feature: {name}"

        # Check math sanity
        assert feats["flex_sum"] == sum(packet["flex"])
        assert feats["flex_mean"] == sum(packet["flex"]) / 5.0
        assert feats["accel_mag"] > 9.80

    def test_extract_features_from_row(self):
        """Extract features from flat dictionary (like a pandas series)."""
        from backend.utils import extract_features, FEATURE_NAMES

        row = {
            "flex_thumb": 1200,
            "flex_index": 1100,
            "flex_middle": 1050,
            "flex_ring": 1000,
            "flex_little": 950,
            "accel_x": 1.0,
            "accel_y": 2.0,
            "accel_z": 9.0,
            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0,
        }
        feats = extract_features(row)
        for name in FEATURE_NAMES:
            assert name in feats
        assert feats["flex_thumb"] == 1200


class TestPacketToCsvRow:
    """Tests for formatting packets into CSV rows."""

    def test_row_formatting(self):
        from backend.utils import packet_to_csv_row, DATASET_COLUMNS

        packet = {
            "timestamp_ms": 500,
            "flex": [1000, 2000, 3000, 4000, 1500],
            "accel": [0.5, -0.5, 9.8],
            "gyro": [1.0, 2.0, 3.0],
        }
        row = packet_to_csv_row(packet, gesture="PEACE", participant_id="P02", session_id="S02")
        for col in DATASET_COLUMNS:
            assert col in row, f"Missing CSV column {col}"
        assert row["gesture"] == "PEACE"
        assert row["participant_id"] == "P02"
        assert row["session_id"] == "S02"
