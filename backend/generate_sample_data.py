"""
generate_sample_data.py — Synthetic Dataset Generator

Generates realistic gesture dataset CSV files for the ESP32 Gesture Recognition Glove.
Simulates multiple participants, sessions, and physical sensor responses.
Allows immediate training and testing of the ML pipeline without physical hardware.

Team 2 — Senior Design Project
"""

import sys
import os
import argparse
import random
from pathlib import Path
from typing import List, Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Support running as a standalone script or imported module
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.utils import DATASET_DIR, GESTURE_CLASSES, DATASET_COLUMNS
import pandas as pd
import numpy as np


# Base profiles for the 6 gesture classes
# Format: { "flex": [thumb, index, mid, ring, little], "accel": [ax, ay, az], "gyro": [gx, gy, gz] }
# Straight finger: ~3200 ADC
# Bent finger:     ~1100 ADC
# Relaxed finger:  ~2350 ADC
GESTURE_PROFILES = {
    "OPEN_PALM": {
        "flex": [3250, 3200, 3220, 3180, 3150],
        "accel": [0.1, 0.2, 9.80],
        "gyro": [0.0, 0.0, 0.0],
    },
    "CLOSED_FIST": {
        "flex": [1150, 1100, 1080, 1090, 1120],
        "accel": [0.3, 0.1, 9.75],
        "gyro": [0.0, 0.0, 0.0],
    },
    "POINTING": {
        # Index straight, other 4 curled
        "flex": [1150, 3250, 1100, 1080, 1100],
        "accel": [1.5, 0.2, 9.60],  # slight forward angle
        "gyro": [0.0, 0.0, 0.0],
    },
    "PEACE": {
        # Index and Middle straight, others curled
        "flex": [1150, 3220, 3250, 1100, 1080],
        "accel": [0.2, 0.1, 9.80],
        "gyro": [0.0, 0.0, 0.0],
    },
    "THUMBS_UP": {
        # Thumb straight, 4 curled, hand rotated 90 degrees (X-axis pointing up)
        "flex": [3200, 1120, 1090, 1080, 1110],
        "accel": [9.6, 0.2, 1.80],  # Tilted hand
        "gyro": [0.0, 0.0, 0.0],
    },
    "RESTING": {
        # Relaxed natural hand resting on desk
        "flex": [2400, 2350, 2380, 2320, 2300],
        "accel": [0.0, 0.1, 9.81],
        "gyro": [0.0, 0.0, 0.0],
    },
}


def generate_session_data(
    gesture: str,
    participant_id: str,
    session_id: str,
    num_samples: int = 100,
    sampling_interval_ms: int = 40,
    random_seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic samples for one session with realistic participant variations.
    """
    profile = GESTURE_PROFILES[gesture]
    base_flex = np.array(profile["flex"], dtype=float)
    base_accel = np.array(profile["accel"], dtype=float)
    base_gyro = np.array(profile["gyro"], dtype=float)

    # Participant-specific variations (simulates individual hand anatomy / sensor fit)
    p_hash = hash(participant_id) % 1000
    np.random.seed(random_seed + p_hash)
    participant_flex_offset = np.random.uniform(-100, 100, size=5)
    participant_accel_offset = np.random.uniform(-0.3, 0.3, size=3)

    # Session-specific slight shifts (sensor realignment on glove put-on)
    s_hash = hash(session_id) % 500
    np.random.seed(random_seed + s_hash)
    session_flex_offset = np.random.uniform(-50, 50, size=5)

    rows = []
    current_time_ms = 0

    for i in range(num_samples):
        # Time progression
        current_time_ms += sampling_interval_ms + random.randint(-2, 2)

        # Dynamic sample noise
        flex_noise = np.random.normal(0, 30.0, size=5)
        accel_noise = np.random.normal(0, 0.12, size=3)
        gyro_noise = np.random.normal(0, 0.15, size=3)

        sample_flex = base_flex + participant_flex_offset + session_flex_offset + flex_noise
        sample_flex = np.clip(sample_flex, 100, 4000).astype(int)

        sample_accel = base_accel + participant_accel_offset + accel_noise
        sample_gyro = base_gyro + gyro_noise

        rows.append({
            "timestamp_ms": current_time_ms,
            "flex_thumb": int(sample_flex[0]),
            "flex_index": int(sample_flex[1]),
            "flex_middle": int(sample_flex[2]),
            "flex_ring": int(sample_flex[3]),
            "flex_little": int(sample_flex[4]),
            "accel_x": round(float(sample_accel[0]), 3),
            "accel_y": round(float(sample_accel[1]), 3),
            "accel_z": round(float(sample_accel[2]), 3),
            "gyro_x": round(float(sample_gyro[0]), 3),
            "gyro_y": round(float(sample_gyro[1]), 3),
            "gyro_z": round(float(sample_gyro[2]), 3),
            "gesture": gesture,
            "participant_id": participant_id,
            "session_id": session_id,
        })

    return pd.DataFrame(rows, columns=DATASET_COLUMNS)


def generate_full_dataset(
    output_dir: Path = DATASET_DIR,
    participants: List[str] = ["P01", "P02", "P03"],
    sessions: List[str] = ["S01", "S02", "S03"],
    samples_per_session: int = 120,
) -> List[Path]:
    """
    Generate complete dataset across all gestures, participants, and sessions.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_files = []

    print(f"Generating synthetic dataset in: {output_dir}")
    print(f"Gestures ({len(GESTURE_CLASSES)}): {GESTURE_CLASSES}")
    print(f"Participants: {participants} | Sessions: {sessions}")
    print(f"Samples per session: {samples_per_session}")

    seed = 100
    for p in participants:
        for s in sessions:
            for g in GESTURE_CLASSES:
                seed += 7
                df = generate_session_data(
                    gesture=g,
                    participant_id=p,
                    session_id=s,
                    num_samples=samples_per_session,
                    random_seed=seed,
                )
                filename = f"{g}_{p}_{s}.csv"
                filepath = output_dir / filename
                df.to_csv(filepath, index=False)
                generated_files.append(filepath)

    total_samples = len(generated_files) * samples_per_session
    print(f"\n✅ Created {len(generated_files)} CSV files ({total_samples:,} total samples).")
    return generated_files


def main():
    parser = argparse.ArgumentParser(description="Synthetic Gesture Dataset Generator")
    parser.add_argument("--output-dir", type=str, default=str(DATASET_DIR), help="Output directory")
    parser.add_argument("--participants", nargs="+", default=["P01", "P02", "P03"], help="List of participant IDs")
    parser.add_argument("--sessions", nargs="+", default=["S01", "S02", "S03"], help="List of session IDs")
    parser.add_argument("--samples", type=int, default=120, help="Samples per gesture session (default: 120)")
    args = parser.parse_args()

    generate_full_dataset(
        output_dir=Path(args.output_dir),
        participants=args.participants,
        sessions=args.sessions,
        samples_per_session=args.samples,
    )


if __name__ == "__main__":
    main()

