"""
predictor.py — Real-Time Gesture Inference Engine

Loads trained model artifact, processes continuous sensor streams,
applies confidence thresholding (with UNKNOWN fallback) and temporal debounce smoothing.
Can trigger glove LED feedback when a high-confidence gesture is detected.

Team 2 — Senior Design Project
"""

import sys
import os
import time
import argparse
from collections import deque, Counter
from pathlib import Path
from typing import Optional, Dict, Tuple, List, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Support running as a standalone script or imported module
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import numpy as np

from backend.utils import (
    packet_ready_for_inference,
    get_model_path,
    extract_features,
    FEATURE_NAMES,
    GESTURE_CLASSES,
    GESTURE_INFO,
)
from backend.serial_reader import SerialReader


class GesturePredictor:
    """
    Real-time gesture predictor with confidence thresholding and temporal debounce smoothing.
    """

    def __init__(
        self,
        model_path: Optional[Path] = None,
        confidence_threshold: float = 0.70,
        smoothing_window: int = 5,
        debounce_count: int = 3,
    ):
        self.model_path = Path(model_path) if model_path else get_model_path()
        self.confidence_threshold = confidence_threshold
        self.smoothing_window = smoothing_window
        self.debounce_count = debounce_count

        self.model = None
        self.feature_names = []
        self.classes = []
        self.metrics = {}
        self.active_flex_sensors = None

        # Rolling state
        self._window = deque(maxlen=self.smoothing_window)
        self._current_gesture = "RESTING"
        self._last_trigger_time = 0.0

        self.load_model()

    def load_model(self):
        """Load model bundle from disk."""
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model file not found at: {self.model_path}\n"
                "Please run 'python backend/train_model.py' to train and save the model first."
            )

        bundle = joblib.load(self.model_path)
        if isinstance(bundle, dict) and "model" in bundle:
            self.model = bundle["model"]
            self.feature_names = bundle.get("feature_names", FEATURE_NAMES)
            self.classes = list(bundle.get("classes", self.model.classes_))
            self.metrics = bundle.get("metrics", {})
            self.active_flex_sensors = bundle.get("active_flex_sensors")
        else:
            # Direct estimator
            self.model = bundle
            self.feature_names = FEATURE_NAMES
            self.classes = list(self.model.classes_)

    def set_smoothing_window(self, window: int):
        """
        Apply a new majority-vote window size to a live predictor.

        Rebuilds the rolling deque so the new size takes effect immediately;
        assigning self.smoothing_window alone would leave the old maxlen in place.
        """
        window = max(1, int(window))
        if window == self.smoothing_window and self._window.maxlen == window:
            return
        kept = list(self._window)[-window:]
        self.smoothing_window = window
        self._window = deque(kept, maxlen=window)

    def reset(self):
        """Clear smoothing history."""
        self._window.clear()
        self._current_gesture = "RESTING"

    def predict_raw(self, packet_or_row: Dict[str, Any]) -> Tuple[str, float, Dict[str, float]]:
        """
        Extract features and get raw class probabilities without smoothing.
        
        Returns:
            (raw_predicted_class, max_confidence, probability_dict)
        """
        feat_dict = extract_features(packet_or_row)
        feature_vector = np.array([[feat_dict[k] for k in self.feature_names]], dtype=np.float32)

        proba = self.model.predict_proba(feature_vector)[0]
        prob_dict = {cls: float(p) for cls, p in zip(self.model.classes_, proba)}

        # Find best candidate
        best_cls = max(prob_dict, key=prob_dict.get)
        best_prob = prob_dict[best_cls]

        # Apply confidence threshold
        if best_prob < self.confidence_threshold:
            candidate = "UNKNOWN"
        else:
            candidate = best_cls

        return candidate, best_prob, prob_dict

    def predict(self, packet_or_row: Dict[str, Any]) -> Tuple[str, float, Dict[str, float]]:
        """
        Perform real-time prediction with temporal smoothing & debouncing.
        
        Returns:
            (smoothed_gesture, confidence, probability_dict)
        """
        enabled = packet_or_row.get("enabled")
        if enabled is not None and self.active_flex_sensors != sum(enabled):
            self.reset()
            return "UNKNOWN", 0.0, {}
        if "flex" in packet_or_row and not packet_ready_for_inference(packet_or_row):
            self.reset()
            return "UNKNOWN", 0.0, {}
        candidate, prob, prob_dict = self.predict_raw(packet_or_row)

        # Append candidate to sliding window
        self._window.append(candidate)

        # Count frequencies in smoothing window
        counts = Counter(self._window)
        most_common_gesture, count = counts.most_common(1)[0]

        # Debounce: only switch current gesture if the most common candidate
        # meets or exceeds debounce_count
        if count >= self.debounce_count and most_common_gesture != self._current_gesture:
            self._current_gesture = most_common_gesture

        # Confidence of the resulting smoothed gesture
        if self._current_gesture == "UNKNOWN":
            smoothed_conf = prob if candidate == "UNKNOWN" else 0.0
        else:
            current_raw_prob = prob_dict.get(self._current_gesture, 0.0)
            if current_raw_prob >= 0.5:
                smoothed_conf = current_raw_prob
            else:
                # Glitch frame: current gesture is sustained by debouncing
                agreement_ratio = counts.get(self._current_gesture, 1) / float(len(self._window))
                smoothed_conf = max(current_raw_prob, agreement_ratio * self.confidence_threshold)

        return self._current_gesture, smoothed_conf, prob_dict


def main():
    parser = argparse.ArgumentParser(description="Real-Time Sign Language Gesture Predictor")
    parser.add_argument("--port", type=str, default=None, help="Serial port (e.g. COM3)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--model", type=str, default=None, help="Path to trained model artifact")
    parser.add_argument("--mock", action="store_true", help="Run simulated glove stream")
    parser.add_argument("--threshold", type=float, default=0.70, help="Confidence threshold (0.0-1.0)")
    parser.add_argument("--feedback", action="store_true", help="Send buzzer feedback on a gesture change")
    parser.add_argument("--max-packets", type=int, default=None, help="Stop after N predictions")
    args = parser.parse_args()

    print("==================================================")
    print("  AI Smart Sign Language Glove — Live Predictor")
    print("  Team 2 — Senior Design Project")
    print("==================================================")

    predictor = GesturePredictor(
        model_path=Path(args.model) if args.model else None,
        confidence_threshold=args.threshold,
    )
    print(f"Loaded Model: {predictor.model_path.name}")
    print(f"Classes ({len(predictor.classes)}): {', '.join(predictor.classes)}")
    print(f"Confidence Threshold: {args.threshold * 100:.0f}%")

    reader = SerialReader(port=args.port, baud_rate=args.baud, mock=args.mock)
    if not reader.connect():
        sys.exit(1)

    print(f"Connected to: {'MOCK ESP32' if args.mock else reader.port}")
    print("\nRunning real-time inference (Press Ctrl+C to stop)...")
    print("Time(ms) | Prediction    | Conf  | Emoji | Meaning")
    print("---------+---------------+-------+-------+-------------------------")

    last_gesture = None
    count = 0

    try:
        for packet in reader.stream(max_packets=args.max_packets):
            count += 1
            if not reader.mock and "calibrated" not in packet:
                print("Firmware calibration status missing; upload current firmware.")
                continue
            gesture, conf, probs = predictor.predict(packet)

            info = GESTURE_INFO.get(gesture, {})
            emoji = info.get("emoji", "❓")
            meaning = info.get("meaning", "Unrecognized or transitioning")

            print(f"{packet['timestamp_ms']:8d} | {gesture:<13} | {conf * 100:4.1f}% | {emoji:^5} | {meaning}")

            # Trigger LED on gesture change
            if args.feedback and gesture != "UNKNOWN" and gesture != "RESTING" and gesture != last_gesture:
                reader.send_command("buzzer")

            last_gesture = gesture

    except KeyboardInterrupt:
        print("\nStopping predictor...")
    finally:
        reader.disconnect()
        print(f"Done. Processed {count} frames.")


if __name__ == "__main__":
    main()

