"""
data_collector.py — Gesture Dataset Collection Tool

Interactive tool for recording labeled sign language gestures from the glove.
Saves CSV files to dataset/ directory with session and participant metadata.

Team 2 — Senior Design Project
"""

import sys
import os
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Support running as a standalone script or imported module
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.utils import (
    DATASET_DIR,
    GESTURE_CLASSES,
    GESTURE_INFO,
    DATASET_COLUMNS,
    packet_to_csv_row,
)
from backend.serial_reader import SerialReader


class DataCollector:
    """
    Manages structured recording sessions for gesture training data.
    """

    def __init__(
        self,
        serial_reader: SerialReader,
        output_dir: Path = DATASET_DIR,
        samples_per_session: int = 100,
    ):
        self.reader = serial_reader
        self.output_dir = Path(output_dir)
        self.samples_per_session = samples_per_session
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def record_gesture(
        self,
        gesture: str,
        participant_id: str = "P01",
        session_id: str = "S01",
        countdown_sec: int = 3,
        num_samples: Optional[int] = None,
    ) -> Optional[Path]:
        """
        Record a single gesture session.
        
        Args:
            gesture: One of GESTURE_CLASSES
            participant_id: Identifier for person wearing glove (e.g. 'P01')
            session_id: Identifier for recording session (e.g. 'S01')
            countdown_sec: Countdown delay before recording starts
            num_samples: Number of samples to collect
        
        Returns:
            Path to saved CSV file, or None if cancelled/failed
        """
        if gesture not in GESTURE_CLASSES:
            raise ValueError(f"Unknown gesture '{gesture}'. Must be one of: {GESTURE_CLASSES}")

        target_samples = num_samples or self.samples_per_session
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{gesture}_{participant_id}_{session_id}_{timestamp_str}.csv"
        filepath = self.output_dir / filename

        info = GESTURE_INFO.get(gesture, {})
        emoji = info.get("emoji", "✋")
        desc = info.get("description", "")

        print("\n" + "=" * 60)
        print(f"  RECORDING GESTURE: {gesture} {emoji}")
        print(f"  Description: {desc}")
        print(f"  Participant: {participant_id} | Session: {session_id} | Target Samples: {target_samples}")
        print("=" * 60)

        # Countdown phase
        if countdown_sec > 0:
            print("\nHold your hand in position. Recording starts in:")
            for c in range(countdown_sec, 0, -1):
                print(f"  ⏱️  {c}...")
                time.sleep(1.0)
            print("  🚀 RECORDING NOW! Hold position steady!\n")

        # Lock mock stream mode if in simulation
        if hasattr(self.reader, "set_mock_mode"):
            self.reader.set_mock_mode(gesture)

        # Visual feedback: flash glove LED if connected
        self.reader.send_command({"led": 1})

        rows: List[Dict[str, Any]] = []
        collected = 0

        try:
            for packet in self.reader.stream():
                row = packet_to_csv_row(packet, gesture=gesture, participant_id=participant_id, session_id=session_id)
                rows.append(row)
                collected += 1

                # Progress bar
                pct = int((collected / target_samples) * 30)
                bar = "█" * pct + "░" * (30 - pct)
                sys.stdout.write(f"\r  [{bar}] {collected}/{target_samples} samples collected")
                sys.stdout.flush()

                if collected >= target_samples:
                    break

            sys.stdout.write("\n")

        except KeyboardInterrupt:
            print("\n⚠️  Recording interrupted by user!")
            return None

        # Turn off LED / flash to signal completion
        self.reader.send_command({"led": 0})

        if len(rows) == 0:
            print("❌ No samples were collected! Serial connection may not be streaming.")
            return None

        # Save to CSV using pandas or csv module
        import pandas as pd
        df = pd.DataFrame(rows, columns=DATASET_COLUMNS)
        df.to_csv(filepath, index=False)

        print(f"✅ Successfully saved {len(df)} samples to:\n   {filepath}")
        return filepath


def interactive_collector(reader: SerialReader, output_dir: Path):
    """Interactive CLI menu for recording multiple gestures in sequence."""
    print("==================================================")
    print("  AI Smart Sign Language Glove — Dataset Collector")
    print("  Team 2 — Senior Design Project")
    print("==================================================")

    participant_id = input("\nEnter Participant ID [default: P01]: ").strip() or "P01"
    session_id = input("Enter Session ID [default: S01]: ").strip() or "S01"
    samples_str = input("Samples per gesture [default: 100]: ").strip()
    samples = int(samples_str) if samples_str.isdigit() else 100

    collector = DataCollector(reader, output_dir=output_dir, samples_per_session=samples)

    while True:
        print("\nSelect gesture to record:")
        for idx, g in enumerate(GESTURE_CLASSES, 1):
            emoji = GESTURE_INFO[g]["emoji"]
            desc = GESTURE_INFO[g]["description"]
            print(f"  [{idx}] {g:<12} {emoji}  — {desc}")
        print("  [A] Record ALL gestures in sequence")
        print("  [Q] Quit")

        choice = input("\nYour choice: ").strip().upper()

        if choice == "Q":
            print("Exiting data collector.")
            break
        elif choice == "A":
            print("\nStarting full sequence recording...")
            for g in GESTURE_CLASSES:
                collector.record_gesture(
                    gesture=g,
                    participant_id=participant_id,
                    session_id=session_id,
                    countdown_sec=3,
                    num_samples=samples,
                )
                time.sleep(1.5)
            print("\n🎉 Completed full recording sequence!")
        else:
            try:
                num = int(choice)
                if 1 <= num <= len(GESTURE_CLASSES):
                    selected_gesture = GESTURE_CLASSES[num - 1]
                    collector.record_gesture(
                        gesture=selected_gesture,
                        participant_id=participant_id,
                        session_id=session_id,
                        countdown_sec=3,
                        num_samples=samples,
                    )
                else:
                    print("Invalid option number.")
            except ValueError:
                print("Invalid choice.")


def main():
    parser = argparse.ArgumentParser(description="Sign Language Glove Gesture Data Collector")
    parser.add_argument("--port", type=str, default=None, help="Serial port (e.g. COM3)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--gesture", type=str, choices=GESTURE_CLASSES, default=None, help="Directly record one gesture")
    parser.add_argument("--participant", type=str, default="P01", help="Participant ID (default: P01)")
    parser.add_argument("--session", type=str, default="S01", help="Session ID (default: S01)")
    parser.add_argument("--samples", type=int, default=100, help="Samples to record (default: 100)")
    parser.add_argument("--output-dir", type=str, default=str(DATASET_DIR), help="Output directory")
    parser.add_argument("--mock", action="store_true", help="Simulate data without physical glove hardware")
    args = parser.parse_args()

    reader = SerialReader(port=args.port, baud_rate=args.baud, mock=args.mock)
    if not reader.connect():
        sys.exit(1)

    try:
        if args.gesture:
            collector = DataCollector(reader, output_dir=Path(args.output_dir), samples_per_session=args.samples)
            collector.record_gesture(
                gesture=args.gesture,
                participant_id=args.participant,
                session_id=args.session,
                num_samples=args.samples,
            )
        else:
            interactive_collector(reader, Path(args.output_dir))
    finally:
        reader.disconnect()


if __name__ == "__main__":
    main()
