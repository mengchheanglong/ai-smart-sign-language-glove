"""
serial_reader.py — Serial Interface for AI Smart Sign Language Glove

Reads JSON packets from ESP32 over USB Serial, validates data,
supports CSV logging, and allows bidirectional LED feedback commands.
Includes a simulation/mock mode for testing without hardware.

Team 2 — Senior Design Project
"""

import sys
import os
import time
import json
import csv
import math
import random
import argparse
from pathlib import Path
import threading
from typing import Optional, Dict, Any, Generator, Tuple

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
    get_serial_port,
    validate_sensor_packet,
    DEFAULT_BAUD_RATE,
    DATASET_COLUMNS,
    packet_to_csv_row,
)


class MockSerialConnection:
    """Simulates an ESP32 sending realistic sign language glove data."""

    def __init__(self, sample_rate_hz: float = 25.0):
        self.interval = 1.0 / sample_rate_hz
        self.is_open = True
        self.start_time = time.time()
        self.last_emit = 0.0
        self.mode = "OPEN_PALM"
        self._modes = ["OPEN_PALM", "CLOSED_FIST", "POINTING", "PEACE", "THUMBS_UP", "RESTING"]
        self._mode_cycle_time = time.time()
        self._fixed_mode = False

    def set_mode(self, mode: str):
        """Lock mock stream to output specific gesture profile."""
        if mode in self._modes:
            self.mode = mode
            self._fixed_mode = True

    def close(self):
        self.is_open = False

    def write(self, data: bytes):
        """Mock receiving commands from PC."""
        # e.g. b'{"led": 1}\n'
        pass

    def readline(self) -> bytes:
        now = time.time()
        elapsed = now - self.last_emit
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_emit = time.time()

        # Slowly cycle modes every 6 seconds to give dynamic demo data (if not locked)
        if not self._fixed_mode and time.time() - self._mode_cycle_time > 6.0:
            self._mode_cycle_time = time.time()
            idx = (self._modes.index(self.mode) + 1) % len(self._modes)
            self.mode = self._modes[idx]

        timestamp_ms = int((time.time() - self.start_time) * 1000)
        packet = self._generate_packet_for_mode(self.mode, timestamp_ms)
        return (json.dumps(packet) + "\n").encode("utf-8")

    def _generate_packet_for_mode(self, mode: str, timestamp_ms: int) -> Dict[str, Any]:
        noise = lambda: random.randint(-25, 25)
        f_noise = lambda: round(random.gauss(0, 0.05), 2)

        if mode == "OPEN_PALM":
            # All straight (~3200)
            flex = [3200 + noise() for _ in range(5)]
            accel = [0.1 + f_noise(), 0.1 + f_noise(), 9.8 + f_noise()]
            gyro = [0.0 + f_noise(), 0.0 + f_noise(), 0.0 + f_noise()]
        elif mode == "CLOSED_FIST":
            # All bent (~1100)
            flex = [1100 + noise() for _ in range(5)]
            accel = [0.2 + f_noise(), 0.0 + f_noise(), 9.7 + f_noise()]
            gyro = [0.0 + f_noise(), 0.0 + f_noise(), 0.0 + f_noise()]
        elif mode == "POINTING":
            # Index straight (~3200), others bent (~1100)
            flex = [1100 + noise(), 3200 + noise(), 1100 + noise(), 1100 + noise(), 1100 + noise()]
            accel = [0.5 + f_noise(), 0.2 + f_noise(), 9.6 + f_noise()]
            gyro = [0.0 + f_noise(), 0.0 + f_noise(), 0.0 + f_noise()]
        elif mode == "PEACE":
            # Index & middle straight, others bent
            flex = [1100 + noise(), 3200 + noise(), 3200 + noise(), 1100 + noise(), 1100 + noise()]
            accel = [0.2 + f_noise(), 0.1 + f_noise(), 9.8 + f_noise()]
            gyro = [0.0 + f_noise(), 0.0 + f_noise(), 0.0 + f_noise()]
        elif mode == "THUMBS_UP":
            # Thumb straight, hand tilted, fingers curled
            flex = [3200 + noise(), 1100 + noise(), 1100 + noise(), 1100 + noise(), 1100 + noise()]
            accel = [9.5 + f_noise(), 0.2 + f_noise(), 2.0 + f_noise()]
            gyro = [0.0 + f_noise(), 0.0 + f_noise(), 0.0 + f_noise()]
        else:  # RESTING
            # Neutral curl (~2400)
            flex = [2400 + noise() for _ in range(5)]
            accel = [0.0 + f_noise(), 0.0 + f_noise(), 9.8 + f_noise()]
            gyro = [0.0 + f_noise(), 0.0 + f_noise(), 0.0 + f_noise()]

        # Constrain to 0-4095
        flex = [max(0, min(4095, f)) for f in flex]

        return {
            "timestamp_ms": timestamp_ms,
            "flex": flex,
            "accel": accel,
            "gyro": gyro,
        }


class SerialReader:
    """
    Manages USB Serial connection to ESP32 glove.
    Provides streaming, validation, logging, and LED trigger commands.
    """

    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = DEFAULT_BAUD_RATE,
        csv_path: Optional[str] = None,
        mock: bool = False,
        timeout: float = 2.0,
    ):
        self.port = port
        self.baud_rate = baud_rate
        self.csv_path = csv_path
        self.mock = mock
        self.timeout = timeout

        self.ser = None
        self.is_connected = False
        self._csv_file = None
        self._csv_writer = None

        # Statistics
        self.total_packets = 0
        self.valid_packets = 0
        self.invalid_packets = 0
        self.start_time = None
        self.last_packet_time = None

        if self.csv_path:
            self._init_csv(self.csv_path)

    def _init_csv(self, path: str):
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        file_exists = filepath.is_file() and filepath.stat().st_size > 0
        self._csv_file = open(filepath, mode="a", newline="", encoding="utf-8")
        self._csv_writer = csv.DictWriter(self._csv_file, fieldnames=DATASET_COLUMNS)
        if not file_exists:
            self._csv_writer.writeheader()
            self._csv_file.flush()

    def connect(self) -> bool:
        """Connect to the serial port or start mock mode."""
        if self.mock:
            self.ser = MockSerialConnection()
            self.is_connected = True
            self.start_time = time.time()
            return True

        if not self.port:
            try:
                self.port = get_serial_port()
            except RuntimeError as e:
                print(f"❌ {e}")
                self.is_connected = False
                return False

        import serial

        for attempt in range(3):
            try:
                self.ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baud_rate,
                    timeout=self.timeout,
                )
                # Flush existing buffer garbage on boot
                time.sleep(0.1)
                self.ser.reset_input_buffer()
                self.is_connected = True
                self.start_time = time.time()
                return True
            except Exception as e:
                # If another process or driver just released the handle, wait and retry
                if attempt < 2 and ("PermissionError" in str(e) or "Access is denied" in str(e)):
                    time.sleep(0.2)
                    continue
                self.is_connected = False
                self.ser = None
                print(f"❌ Failed to connect to {self.port}: {e}")
                return False
        return False

    def disconnect(self):
        """Disconnect and release resources."""
        self.is_connected = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
            # Allow Windows kernel driver brief moment to release COM handle
            time.sleep(0.12)
        if self._csv_file:
            try:
                self._csv_file.flush()
                self._csv_file.close()
            except Exception:
                pass
            self._csv_file = None
            self._csv_writer = None

    def read_packet(self) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Read a single line from the connection and parse/validate.
        Automatically skips non-JSON boot/debug messages to find valid packets.
        
        Returns:
            (is_valid, packet_dict_or_none, raw_line_str)
        """
        if not self.is_connected or not self.ser:
            return False, None, ""

        try:
            # Drain backlog if serial buffer accumulated older frames to eliminate UI lag
            if hasattr(self.ser, "in_waiting"):
                try:
                    while self.ser.in_waiting > 120:
                        self.ser.readline()
                except Exception:
                    pass

            # Try up to 5 lines to skip boot banners or debug text
            for _ in range(5):
                line_bytes = self.ser.readline()
                if not line_bytes:
                    break

                raw_line = line_bytes.decode("utf-8", errors="replace").strip()
                if not raw_line:
                    continue

                # Check if line looks like JSON
                if raw_line.startswith("{") and raw_line.endswith("}"):
                    try:
                        packet = json.loads(raw_line)
                    except json.JSONDecodeError:
                        self.invalid_packets += 1
                        continue

                    is_valid, error = validate_sensor_packet(packet)
                    self.total_packets += 1
                    if is_valid:
                        self.valid_packets += 1
                        self.last_packet_time = time.time()
                        return True, packet, raw_line
                    else:
                        self.invalid_packets += 1
                        return False, None, raw_line


            return False, None, ""

        except Exception as e:
            # Handle possible unplugging
            self.is_connected = False
            return False, None, f"ERROR: {str(e)}"

    def send_command(self, cmd: Any) -> bool:
        """Send command over serial (e.g. {'led': 1} or 'b')."""
        if not self.is_connected or not self.ser:
            return False
        try:
            if isinstance(cmd, dict):
                payload = (json.dumps(cmd) + "\n").encode("utf-8")
            else:
                payload = (str(cmd) + "\n").encode("utf-8")
            self.ser.write(payload)
            return True
        except Exception:
            return False

    def set_mock_mode(self, mode: str):
        """Set mock stream gesture mode if running in mock simulation."""
        if self.mock and isinstance(self.ser, MockSerialConnection):
            self.ser.set_mode(mode)

    def log_packet(self, packet: Dict[str, Any], gesture: str = "UNKNOWN", participant_id: str = "P01", session_id: str = "S01"):
        """Save a validated packet into the configured CSV file."""
        if self._csv_writer and self._csv_file:
            row = packet_to_csv_row(packet, gesture=gesture, participant_id=participant_id, session_id=session_id)
            self._csv_writer.writerow(row)
            self._csv_file.flush()

    def get_packet_rate(self) -> float:
        """Calculate recent packet throughput in Hz."""
        if not self.start_time or self.total_packets == 0:
            return 0.0
        elapsed = time.time() - self.start_time
        return self.total_packets / elapsed if elapsed > 0 else 0.0

    def stream(self, max_packets: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """Generator yielding validated packets until stopped or max_packets reached."""
        count = 0
        while self.is_connected:
            is_valid, packet, _ = self.read_packet()
            if is_valid and packet:
                yield packet
                count += 1
                if max_packets and count >= max_packets:
                    break


# Global shared singleton connection for multi-threaded / multi-session runtimes (e.g. Streamlit)
_SHARED_READER: Optional[SerialReader] = None
_SHARED_LOCK = threading.Lock()


def get_shared_reader(port: str, baud_rate: int = DEFAULT_BAUD_RATE, timeout: float = 0.5) -> Optional[SerialReader]:
    """
    Get or create a process-wide shared SerialReader singleton.
    Prevents Win32 exclusive handle collision (PermissionError 13)
    when Streamlit reruns or multiple browser tabs are open.
    """
    global _SHARED_READER
    with _SHARED_LOCK:
        if (
            _SHARED_READER is not None
            and _SHARED_READER.is_connected
            and _SHARED_READER.port == port
        ):
            return _SHARED_READER

        if _SHARED_READER is not None:
            try:
                _SHARED_READER.disconnect()
            except Exception:
                pass
            _SHARED_READER = None

        reader = SerialReader(port=port, baud_rate=baud_rate, timeout=timeout)
        if reader.connect():
            _SHARED_READER = reader
            return _SHARED_READER
        return None


def close_shared_reader():
    """Disconnect and release the process-wide shared SerialReader singleton."""
    global _SHARED_READER
    with _SHARED_LOCK:
        if _SHARED_READER is not None:
            try:
                _SHARED_READER.disconnect()
            except Exception:
                pass
            _SHARED_READER = None


def main():
    parser = argparse.ArgumentParser(description="AI Smart Sign Language Glove — Serial Reader CLI")
    parser.add_argument("--port", type=str, default=None, help="Serial port (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE, help="Baud rate (default: 115200)")
    parser.add_argument("--csv", type=str, default=None, help="Optional CSV file to log readings to")
    parser.add_argument("--mock", action="store_true", help="Run simulated glove stream without physical hardware")
    parser.add_argument("--max-packets", type=int, default=None, help="Stop after reading N packets")
    parser.add_argument("--send-blink", action="store_true", help="Send test LED blink command to glove")
    args = parser.parse_args()

    print("==================================================")
    print("  AI Smart Sign Language Glove — Serial Reader")
    print("  Team 2 — Senior Design Project")
    print("==================================================")

    reader = SerialReader(
        port=args.port,
        baud_rate=args.baud,
        csv_path=args.csv,
        mock=args.mock,
    )

    if not reader.connect():
        sys.exit(1)

    print(f"Connected to: {'MOCK ESP32' if args.mock else reader.port}")
    if args.csv:
        print(f"Logging to: {args.csv}")

    if args.send_blink:
        print("Sending test blink command to glove...")
        reader.send_command("buzzer")

    print("\nStreaming sensor packets (Press Ctrl+C to stop)...")
    print("Time(ms) | Thumb | Index | Mid   | Ring  | Pinky | Accel (X, Y, Z)   | Rate (Hz)")
    print("---------+-------+-------+-------+-------+-------+--------------------+----------")

    try:
        packet_count = 0
        for packet in reader.stream(max_packets=args.max_packets):
            packet_count += 1
            f = packet["flex"]
            ax, ay, az = packet["accel"]
            rate = reader.get_packet_rate()

            print(
                f"{packet['timestamp_ms']:8d} | {f[0]:5d} | {f[1]:5d} | {f[2]:5d} | {f[3]:5d} | {f[4]:5d} | "
                f"{ax:5.2f}, {ay:5.2f}, {az:5.2f} | {rate:5.1f} Hz"
            )

            if args.csv:
                reader.log_packet(packet, gesture="MONITOR")

    except KeyboardInterrupt:
        print("\n\nStopping serial reader...")
    finally:
        reader.disconnect()
        print(f"Done. Total valid packets received: {reader.valid_packets}/{reader.total_packets}")


if __name__ == "__main__":
    main()
