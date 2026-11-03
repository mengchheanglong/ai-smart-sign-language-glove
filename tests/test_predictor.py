"""
test_predictor.py — Unit Tests for Real-Time Gesture Inference & Debouncing

Run with: python -m pytest tests/test_predictor.py -v
"""

import sys
import os
import pytest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils import get_model_path, GESTURE_CLASSES
from backend.predictor import GesturePredictor


class TestGesturePredictor:
    """Tests for real-time predictor class."""

    @pytest.fixture
    def predictor(self):
        """Fixture providing initialized GesturePredictor."""
        return GesturePredictor(confidence_threshold=0.70, smoothing_window=5, debounce_count=3)

    @pytest.fixture
    def open_palm_packet(self):
        return {
            "timestamp_ms": 100,
            "flex": [3200, 3200, 3200, 3200, 3200],
            "accel": [0.1, 0.1, 9.8],
            "gyro": [0.0, 0.0, 0.0],
        }

    @pytest.fixture
    def fist_packet(self):
        return {
            "timestamp_ms": 100,
            "flex": [1100, 1100, 1100, 1100, 1100],
            "accel": [0.1, 0.1, 9.8],
            "gyro": [0.0, 0.0, 0.0],
        }

    def test_model_loaded(self, predictor):
        """Predictor must load classes and model from bundle."""
        assert predictor.model is not None
        assert len(predictor.classes) == 6
        assert set(predictor.classes) == set(GESTURE_CLASSES)

    def test_predict_raw_open_palm(self, predictor, open_palm_packet):
        """Straight fingers should raw-predict OPEN_PALM with high confidence."""
        gesture, conf, prob_dict = predictor.predict_raw(open_palm_packet)
        assert gesture == "OPEN_PALM"
        assert conf >= 0.70
        assert sum(prob_dict.values()) == pytest.approx(1.0, rel=1e-2)

    def test_predict_raw_closed_fist(self, predictor, fist_packet):
        """Bent fingers should raw-predict CLOSED_FIST with high confidence."""
        gesture, conf, prob_dict = predictor.predict_raw(fist_packet)
        assert gesture == "CLOSED_FIST"
        assert conf >= 0.70

    def test_confidence_threshold_unknown_fallback(self, predictor, open_palm_packet):
        """Setting confidence threshold above 1.0 forces UNKNOWN fallback."""
        predictor.confidence_threshold = 1.01
        gesture, conf, prob_dict = predictor.predict_raw(open_palm_packet)
        assert gesture == "UNKNOWN"

    def test_debounce_filters_single_frame_noise(self, predictor, open_palm_packet, fist_packet):
        """A single anomalous frame should NOT cause the debounced prediction to jump."""
        predictor.reset()

        # Stabilize on OPEN_PALM
        for _ in range(5):
            predictor.predict(open_palm_packet)
        assert predictor._current_gesture == "OPEN_PALM"

        # One anomalous frame of CLOSED_FIST
        gesture, conf, _ = predictor.predict(fist_packet)
        # Should still report OPEN_PALM due to debouncing!
        assert gesture == "OPEN_PALM"

    def test_debounce_switches_after_sustained_gesture(self, predictor, open_palm_packet, fist_packet):
        """Sustained new gesture for debounce_count frames switches the active gesture."""
        predictor.reset()

        # Stabilize on OPEN_PALM
        for _ in range(5):
            predictor.predict(open_palm_packet)
        assert predictor._current_gesture == "OPEN_PALM"

        # Sustain CLOSED_FIST for debounce_count (3) frames
        for _ in range(predictor.debounce_count):
            gesture, conf, _ = predictor.predict(fist_packet)

        # Now it must have transitioned to CLOSED_FIST
        assert gesture == "CLOSED_FIST"

    def test_reset(self, predictor, open_palm_packet):
        """Reset clears window buffer."""
        predictor.predict(open_palm_packet)
        assert len(predictor._window) > 0
        predictor.reset()
        assert len(predictor._window) == 0
        assert predictor._current_gesture == "RESTING"
