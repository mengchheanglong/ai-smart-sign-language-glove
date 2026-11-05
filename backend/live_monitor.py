"""
live_monitor.py — Real-Time Terminal Visualizer for ESP32 Gesture Recognition Glove
Team 2 — Senior Design Project

Displays live ASCII bend gauges, IMU 3D attitude, voltages, and gesture states in terminal.
Works with both the flex sensor diagnostic and the GY-87 / MPU6050 IMU test.
"""

import sys
import os
import time
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import serial
from backend.utils import find_serial_ports, DEFAULT_BAUD_RATE

CALIBRATION = {
    "GPIO32": {"straight": 1050, "bent": 370},
    "GPIO33": {"straight": 1200, "bent": 400},
    "GPIO34": {"straight": 1150, "bent": 380},
    "GPIO35": {"straight": 1150, "bent": 380},
    "GPIO36": {"straight": 1150, "bent": 380},
}


def compute_bend_pct(pin_name: str, adc: int) -> int:
    if adc < 80:
        return 0
    cal = CALIBRATION.get(pin_name, {"straight": 1150, "bent": 380})
    straight = cal["straight"]
    bent = cal["bent"]
    fraction = (straight - adc) / float(straight - bent)
    fraction = max(0.0, min(1.0, fraction))
    return int(round(fraction * 100))


def make_bar(pin_name: str, adc: int, width: int = 24) -> str:
    if adc < 80:
        return "[" + "·" * width + "] (No wire)"
    pct = compute_bend_pct(pin_name, adc)
    filled = int(round((pct / 100.0) * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:3d}%"


def classify_bend(pin_name: str, adc: int) -> str:
    if adc < 80:
        return "DISCONNECTED"
    pct = compute_bend_pct(pin_name, adc)
    if pct < 25:
        return "STRAIGHT   "
    elif pct < 65:
        return "HALF-BENT  "
    else:
        return "BENT       "


def main():
    ports = find_serial_ports(prefer_usb=True)
    if ports:
        port = ports[0]["port"]
    else:
        port = os.getenv("SERIAL_PORT", "/dev/cu.usbserial-10")

    baud = DEFAULT_BAUD_RATE

    print("\033[2J\033[H", end="") # Clear screen
    print("=" * 75)
    print("  🧤 ESP32 Gesture Recognition Glove — Live Sensor & IMU Monitor")
    print(f"  Port: {port}  |  Baud: {baud}  |  Running continuously (Ctrl+C to stop)")
    print("=" * 75)

    pins = ["GPIO32", "GPIO33", "GPIO34", "GPIO35", "GPIO36"]
    pin_labels = ["Thumb (GPIO32)", "Index (GPIO33)", "Middle(GPIO34)", "Ring  (GPIO35)", "Little(GPIO36)"]

    ser = None

    while True:
        try:
            if ser is None or not ser.is_open:
                try:
                    ser = serial.Serial(port, baud, timeout=1)
                    time.sleep(0.2)
                    ser.reset_input_buffer()
                except Exception:
                    time.sleep(0.5)
                    continue

            try:
                line = ser.readline().decode("utf-8", errors="replace").strip()
            except (serial.SerialException, OSError):
                time.sleep(0.05)
                continue

            if not line:
                continue

            flex_vals = None
            imu_info = None

            # Pattern 1: GY-87 / MPU6050 output
            # "Accel: [-10.36, -19.61,  3.21] m/s² | Gyro: [  -1.0,   -8.8,   -0.3] °/s | Angle: [P: +28°, R: -81°] | TILTED DOWN            | Flex: [D32=646, D33=94]"
            if "Accel:" in line and "Gyro:" in line:
                try:
                    acc_m = re.search(r"Accel:\s*\[\s*([^,]+),\s*([^,]+),\s*([^\]]+)\]", line)
                    gyro_m = re.search(r"Gyro:\s*\[\s*([^,]+),\s*([^,]+),\s*([^\]]+)\]", line)
                    angle_m = re.search(r"Angle:\s*\[P:\s*([^,]+),\s*R:\s*([^\]]+)\]", line)
                    orient_m = re.search(r"\|\s*([A-Za-z\- \(\)]+?)\s*\|\s*Flex:", line)
                    flex_m = re.search(r"Flex:\s*\[D32=(\d+),\s*D33=(\d+)\]", line)

                    if acc_m and angle_m:
                        imu_info = {
                            "ax": float(acc_m.group(1)),
                            "ay": float(acc_m.group(2)),
                            "az": float(acc_m.group(3)),
                            "gx": float(gyro_m.group(1)) if gyro_m else 0.0,
                            "gy": float(gyro_m.group(2)) if gyro_m else 0.0,
                            "gz": float(gyro_m.group(3)) if gyro_m else 0.0,
                            "pitch": angle_m.group(1).strip(),
                            "roll": angle_m.group(2).strip(),
                            "orient": orient_m.group(1).strip() if orient_m else "UNKNOWN",
                        }
                    if flex_m:
                        flex_vals = [int(flex_m.group(1)), int(flex_m.group(2)), 0, 0, 0]
                except Exception:
                    pass

            # Pattern 2: test_single_flex diagnostic output
            elif "All ADC1:" in line:
                m = re.findall(r"\[\d+\]=(\d+)", line)
                if len(m) >= 5:
                    flex_vals = [int(v) for v in m[:5]]

            # Pattern 3: JSON packet from main firmware
            elif line.startswith("{") and line.endswith("}"):
                import json
                try:
                    p = json.loads(line)
                    if "flex" in p and len(p["flex"]) >= 5:
                        flex_vals = p["flex"][:5]
                    if "accel" in p and len(p["accel"]) >= 3:
                        imu_info = {
                            "ax": p["accel"][0], "ay": p["accel"][1], "az": p["accel"][2],
                            "gx": p.get("gyro", [0,0,0])[0], "gy": p.get("gyro", [0,0,0])[1], "gz": p.get("gyro", [0,0,0])[2],
                            "pitch": f"{p['accel'][0]:+.0f}°", "roll": f"{p['accel'][1]:+.0f}°",
                            "orient": "ACTIVE",
                        }
                except Exception:
                    pass

            if imu_info is not None or flex_vals is not None:
                sys.stdout.write("\033[5;1H")
                output_lines = []

                if imu_info:
                    output_lines.append(f"🔄 HAND ORIENTATION : \033[1;32m{imu_info['orient']}\033[0m\033[K")
                    output_lines.append(f"   Pitch (Tilt Up/Dn) : {imu_info['pitch']:<8} | Roll (Tilt L/R) : {imu_info['roll']:<8}\033[K")
                    output_lines.append(f"   Accel (m/s²)       : X: {imu_info['ax']:+5.2f}   Y: {imu_info['ay']:+5.2f}   Z: {imu_info['az']:+5.2f}\033[K")
                    output_lines.append(f"   Gyro  (°/s)        : X: {imu_info['gx']:+5.1f}   Y: {imu_info['gy']:+5.1f}   Z: {imu_info['gz']:+5.1f}\033[K")
                    output_lines.append("-" * 75 + "\033[K")

                if flex_vals:
                    output_lines.append("Channel          | Reading   | Voltage | State        | Finger Bend Gauge\033[K")
                    output_lines.append("-" * 75 + "\033[K")
                    for p_name, label, val in zip(pins, pin_labels, flex_vals):
                        volts = (val / 4095.0) * 3.3
                        state = classify_bend(p_name, val)
                        bar = make_bar(p_name, val)
                        output_lines.append(f"{label:<16} | {val:4d} ADC  |  {volts:4.2f}V  | {state}  | {bar}\033[K")
                    output_lines.append("-" * 75 + "\033[K")

                output_lines.append(f"Streaming live... [{time.strftime('%H:%M:%S')}]  |  Tilt GY-87 or bend sensors to test!\033[K")
                sys.stdout.write("\n".join(output_lines) + "\n")
                sys.stdout.flush()

        except KeyboardInterrupt:
            print("\n\n👋 Stopped live monitor.")
            break
        except Exception:
            time.sleep(0.1)

    if ser and ser.is_open:
        try:
            ser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
