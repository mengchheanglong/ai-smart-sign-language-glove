"""
utils.py — Shared Utilities for AI Smart Sign Language Glove

This module contains helper functions used across the backend:
- Configuration loading
- Serial port detection
- Data validation
- File path management

Team 2 — Senior Design Project
"""

import os
import sys
import glob
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================
# PROJECT PATHS
# ============================================================

# Get the project root directory (parent of backend/)
PROJECT_ROOT = Path(__file__).parent.parent

# Standard project directories
DATASET_DIR = PROJECT_ROOT / os.getenv("DATASET_DIR", "dataset")
MODELS_DIR = PROJECT_ROOT / "models"
FIRMWARE_DIR = PROJECT_ROOT / "firmware"

# ============================================================
# SERIAL PORT CONFIGURATION
# ============================================================

DEFAULT_BAUD_RATE = int(os.getenv("SERIAL_BAUD_RATE", "115200"))


def find_serial_ports(prefer_usb=True):
    """
    Detect available serial ports on the current operating system.
    
    Args:
        prefer_usb (bool): If True, filters out virtual Bluetooth ports
                           and prioritizes real USB-to-UART bridges.
    
    Returns:
        list: A list of dicts with port, description, manufacturer.
    """
    import serial.tools.list_ports
    
    ports = serial.tools.list_ports.comports()
    available = []
    usb_ports = []
    
    for port in ports:
        info = {
            "port": port.device,
            "description": port.description,
            "manufacturer": port.manufacturer or "Unknown"
        }
        available.append(info)
        
        desc_lower = (port.description or "").lower()
        hwid_lower = (port.hwid or "").lower()
        # Filter out virtual Bluetooth links
        if "bluetooth" not in desc_lower and "bthenum" not in hwid_lower:
            if any(k in desc_lower or k in hwid_lower for k in ["ch34", "cp21", "ftdi", "usb", "uart"]):
                usb_ports.append(info)
            elif "com" in port.device.lower():
                usb_ports.append(info)

    if prefer_usb and usb_ports:
        return usb_ports
    return available


def get_serial_port():
    """
    Get the configured serial port, or help the user find one.
    
    Priority:
        1. SERIAL_PORT environment variable (from .env file)
        2. Auto-detect if only one real USB port is available
        3. Ask the user to choose
    
    Returns:
        str: The serial port name (e.g., 'COM3' or '/dev/ttyUSB0')
    """
    # Check environment variable first
    env_port = os.getenv("SERIAL_PORT")
    if env_port:
        return env_port
    
    # Try to auto-detect USB ports
    ports = find_serial_ports(prefer_usb=True)
    
    if len(ports) == 0:
        raise RuntimeError(
            "No serial ports found! Make sure your ESP32 is connected via USB and drivers are installed."
        )
    elif len(ports) == 1:
        port = ports[0]["port"]
        print(f"[OK] Auto-detected serial port: {port} ({ports[0]['description']})")
        return port
    else:
        print("[INFO] Multiple serial ports found:")
        for i, p in enumerate(ports):
            print(f"   [{i + 1}] {p['port']} - {p['description']}")
        
        while True:
            try:
                choice = int(input("\nSelect port number: ")) - 1
                if 0 <= choice < len(ports):
                    return ports[choice]["port"]
                print("Invalid selection. Try again.")
            except (ValueError, KeyboardInterrupt):
                print("\nCancelled.")
                sys.exit(0)


def _is_valid_number(val, min_val=None, max_val=None):
    """Check that value is a finite number, strictly excluding booleans."""
    import math
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    if not math.isfinite(val):
        return False
    if min_val is not None and val < min_val:
        return False
    if max_val is not None and val > max_val:
        return False
    return True


def validate_sensor_packet(packet):
    """
    Validate a sensor data packet (parsed from JSON).
    
    A valid packet must contain:
        - timestamp_ms: integer >= 0 (finite, non-boolean)
        - flex: list of 5 integers (0-4095, finite, non-boolean)
        - accel: list of 3 floats (finite, non-boolean)
        - gyro: list of 3 floats (finite, non-boolean)
    
    Args:
        packet (dict): Parsed JSON packet from ESP32
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    try:
        if not isinstance(packet, dict):
            return False, "packet must be a dictionary"

        # Check required keys
        required_keys = ["timestamp_ms", "flex", "accel", "gyro"]
        for key in required_keys:
            if key not in packet:
                return False, f"Missing key: {key}"
        
        # Validate timestamp
        ts = packet["timestamp_ms"]
        if isinstance(ts, bool) or not isinstance(ts, (int, float)):
            return False, "timestamp_ms must be a number (booleans not allowed)"
        if not _is_valid_number(ts):
            return False, "timestamp_ms must be a finite number"
        if ts < 0:
            return False, "timestamp_ms must be non-negative"
        
        # Validate flex sensor readings
        flex = packet["flex"]
        if not isinstance(flex, list) or len(flex) != 5:
            return False, "flex must be a list of 5 values"
        for i, val in enumerate(flex):
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                return False, f"flex[{i}] must be a number (booleans not allowed)"
            if not _is_valid_number(val):
                return False, f"flex[{i}] must be a finite number"
            if val < 0 or val > 4095:
                return False, f"flex[{i}] = {val} is outside range 0-4095"
        
        # Validate accelerometer
        accel = packet["accel"]
        if not isinstance(accel, list) or len(accel) != 3:
            return False, "accel must be a list of 3 values"
        for i, val in enumerate(accel):
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                return False, f"accel[{i}] must be a number (booleans not allowed)"
            if not _is_valid_number(val):
                return False, f"accel[{i}] = {val} is invalid (must be finite number)"
        
        # Validate gyroscope
        gyro = packet["gyro"]
        if not isinstance(gyro, list) or len(gyro) != 3:
            return False, "gyro must be a list of 3 values"
        for i, val in enumerate(gyro):
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                return False, f"gyro[{i}] must be a number (booleans not allowed)"
            if not _is_valid_number(val):
                return False, f"gyro[{i}] = {val} is invalid (must be finite number)"
        
        return True, None
    
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def get_model_path():
    """Get the path to the trained model file."""
    model_path = os.getenv("MODEL_PATH", "models/gesture_model.joblib")
    return PROJECT_ROOT / model_path


# Gesture class definitions
GESTURE_CLASSES = [
    "OPEN_PALM",
    "CLOSED_FIST",
    "POINTING",
    "PEACE",
    "THUMBS_UP",
    "RESTING",
]

# Gesture metadata (emojis and beginner-friendly descriptions)
GESTURE_INFO = {
    "OPEN_PALM": {
        "emoji": "🖐️",
        "description": "All fingers straight, palm facing forward",
        "meaning": "Hello / Stop",
    },
    "CLOSED_FIST": {
        "emoji": "✊",
        "description": "All fingers curled tightly into palm",
        "meaning": "Yes / Power",
    },
    "POINTING": {
        "emoji": "👉",
        "description": "Index finger extended, other fingers curled",
        "meaning": "You / That / Look",
    },
    "PEACE": {
        "emoji": "✌️",
        "description": "Index and middle fingers extended in a V-shape",
        "meaning": "Peace / Two / Victory",
    },
    "THUMBS_UP": {
        "emoji": "👍",
        "description": "Thumb pointing up, other four fingers curled",
        "meaning": "Good / Agree / Approval",
    },
    "RESTING": {
        "emoji": "✋",
        "description": "Hand relaxed in neutral position on desk",
        "meaning": "Idle / Neutral position",
    },
}

FLEX_SENSOR_NAMES = ["Thumb", "Index", "Middle", "Ring", "Little"]

RAW_SENSOR_COLUMNS = [
    "flex_thumb",
    "flex_index",
    "flex_middle",
    "flex_ring",
    "flex_little",
    "accel_x",
    "accel_y",
    "accel_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
]

DATASET_COLUMNS = [
    "timestamp_ms",
    *RAW_SENSOR_COLUMNS,
    "gesture",
    "participant_id",
    "session_id",
]

FEATURE_NAMES = [
    # 5 raw flex readings
    "flex_thumb",
    "flex_index",
    "flex_middle",
    "flex_ring",
    "flex_little",
    # 3 accelerometer axes
    "accel_x",
    "accel_y",
    "accel_z",
    # 3 gyroscope axes
    "gyro_x",
    "gyro_y",
    "gyro_z",
    # Derived flex features
    "flex_sum",
    "flex_mean",
    "flex_spread",
    "flex_ratio_index_thumb",
    "flex_ratio_middle_index",
    # Derived IMU features
    "accel_mag",
    "gyro_mag",
    "pitch_deg",
    "roll_deg",
]


def extract_features(packet_or_row):
    """
    Extract ML feature vector from a sensor packet (dict) or a dataframe row.
    
    Returns a dictionary of feature name -> float.
    Consistent across training and real-time prediction.
    """
    import math

    if isinstance(packet_or_row, dict) and "flex" in packet_or_row:
        # It's a raw JSON packet from ESP32
        f = [float(x) for x in packet_or_row["flex"]]
        ax, ay, az = [float(x) for x in packet_or_row["accel"]]
        gx, gy, gz = [float(x) for x in packet_or_row["gyro"]]
    else:
        # It's a row/series or flat dict with RAW_SENSOR_COLUMNS keys
        f = [
            float(packet_or_row["flex_thumb"]),
            float(packet_or_row["flex_index"]),
            float(packet_or_row["flex_middle"]),
            float(packet_or_row["flex_ring"]),
            float(packet_or_row["flex_little"]),
        ]
        ax = float(packet_or_row["accel_x"])
        ay = float(packet_or_row["accel_y"])
        az = float(packet_or_row["accel_z"])
        gx = float(packet_or_row["gyro_x"])
        gy = float(packet_or_row["gyro_y"])
        gz = float(packet_or_row["gyro_z"])

    # Derived flex features
    flex_sum = sum(f)
    flex_mean = flex_sum / 5.0
    flex_spread = max(f) - min(f)
    # Avoid division by zero
    denom_it = f[0] if abs(f[0]) > 1e-4 else 1e-4
    ratio_it = f[1] / denom_it
    denom_mi = f[1] if abs(f[1]) > 1e-4 else 1e-4
    ratio_mi = f[2] / denom_mi

    # Derived IMU features
    accel_mag = math.sqrt(ax * ax + ay * ay + az * az)
    gyro_mag = math.sqrt(gx * gx + gy * gy + gz * gz)

    # Roll & Pitch angles (degrees)
    # Pitch: rotation around Y-axis (-90 to +90)
    # Roll: rotation around X-axis (-180 to +180)
    denom_pitch = max(1e-4, math.sqrt(ay * ay + az * az))
    pitch_deg = math.atan2(-ax, denom_pitch) * 180.0 / math.pi
    roll_deg = math.atan2(ay, az) * 180.0 / math.pi

    features = {
        "flex_thumb": f[0],
        "flex_index": f[1],
        "flex_middle": f[2],
        "flex_ring": f[3],
        "flex_little": f[4],
        "accel_x": ax,
        "accel_y": ay,
        "accel_z": az,
        "gyro_x": gx,
        "gyro_y": gy,
        "gyro_z": gz,
        "flex_sum": flex_sum,
        "flex_mean": flex_mean,
        "flex_spread": flex_spread,
        "flex_ratio_index_thumb": ratio_it,
        "flex_ratio_middle_index": ratio_mi,
        "accel_mag": accel_mag,
        "gyro_mag": gyro_mag,
        "pitch_deg": pitch_deg,
        "roll_deg": roll_deg,
    }
    return features


def packet_to_csv_row(packet, gesture, participant_id="P01", session_id="S01"):
    """Convert a validated sensor packet into a flat dict matching DATASET_COLUMNS."""
    return {
        "timestamp_ms": int(packet["timestamp_ms"]),
        "flex_thumb": packet["flex"][0],
        "flex_index": packet["flex"][1],
        "flex_middle": packet["flex"][2],
        "flex_ring": packet["flex"][3],
        "flex_little": packet["flex"][4],
        "accel_x": float(packet["accel"][0]),
        "accel_y": float(packet["accel"][1]),
        "accel_z": float(packet["accel"][2]),
        "gyro_x": float(packet["gyro"][0]),
        "gyro_y": float(packet["gyro"][1]),
        "gyro_z": float(packet["gyro"][2]),
        "gesture": gesture,
        "participant_id": participant_id,
        "session_id": session_id,
    }

