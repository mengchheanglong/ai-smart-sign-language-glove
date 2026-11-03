"""
app.py — Interactive Real-Time Dashboard for AI Smart Sign Language Glove

Features:
- Live gesture prediction banner with emoji and confidence
- 5-Finger flex sensor visual progress bars and voltage meters
- 6-DOF IMU orientation & angular velocity visualization
- Real-time ESP32 USB Serial streaming with auto-port detection
- Full interactive Simulation Mode with gesture presets and manual finger sliders
- Stream diagnostic metrics (Hz, packet counts, latency)
- Dataset recording launcher from web UI

Team 2 — Senior Design Project
"""

import sys
import os
import time
import math
import random
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from backend.utils import (
    find_serial_ports,
    DEFAULT_BAUD_RATE,
    GESTURE_CLASSES,
    GESTURE_INFO,
    FLEX_SENSOR_NAMES,
    DATASET_DIR,
    packet_to_csv_row,
    DATASET_COLUMNS,
)
from backend.predictor import GesturePredictor
from backend.serial_reader import SerialReader

# ============================================================
# STREAMLIT PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="AI Smart Sign Language Glove",
    page_icon="🧤",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for crisp, high-contrast dashboard styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0px;
        color: #1E88E5;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #757575;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #e0e0e0;
        text-align: center;
    }
    .gesture-banner {
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .finger-card {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================
if "predictor" not in st.session_state:
    try:
        st.session_state.predictor = GesturePredictor()
    except Exception as e:
        st.session_state.predictor = None
        st.session_state.predictor_error = str(e)

if "reader" not in st.session_state:
    st.session_state.reader = None

if "is_streaming" not in st.session_state:
    st.session_state.is_streaming = False

if "sim_mode" not in st.session_state:
    st.session_state.sim_mode = "Preset Loop"

if "sim_preset_idx" not in st.session_state:
    st.session_state.sim_preset_idx = 0

if "sim_last_cycle" not in st.session_state:
    st.session_state.sim_last_cycle = time.time()


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def raw_to_bend_pct(raw_adc: int, straight_adc: int = 3200, bent_adc: int = 1100) -> float:
    """Map raw ADC value to 0-100% bend."""
    if straight_adc == bent_adc:
        return 0.0
    # Higher ADC = straighter, Lower ADC = more bent
    pct = ((straight_adc - raw_adc) / float(straight_adc - bent_adc)) * 100.0
    return max(0.0, min(100.0, pct))


def adc_to_voltage(raw_adc: int) -> float:
    return (raw_adc / 4095.0) * 3.3


def generate_simulated_packet(preset_name: str, noise: bool = True) -> Dict[str, Any]:
    """Generates synthetic glove packet for chosen preset."""
    from backend.generate_sample_data import GESTURE_PROFILES

    if preset_name in GESTURE_PROFILES:
        profile = GESTURE_PROFILES[preset_name]
        f = list(profile["flex"])
        ax, ay, az = profile["accel"]
        gx, gy, gz = profile["gyro"]
    else:
        # Neutral default
        f = [2400, 2400, 2400, 2400, 2400]
        ax, ay, az = [0.0, 0.0, 9.81]
        gx, gy, gz = [0.0, 0.0, 0.0]

    if noise:
        f = [int(val + random.gauss(0, 25)) for val in f]
        ax += random.gauss(0, 0.08)
        ay += random.gauss(0, 0.08)
        az += random.gauss(0, 0.08)
        gx += random.gauss(0, 0.1)
        gy += random.gauss(0, 0.1)
        gz += random.gauss(0, 0.1)

    f = [max(0, min(4095, val)) for val in f]
    return {
        "timestamp_ms": int(time.time() * 1000) % 10000000,
        "flex": f,
        "accel": [round(ax, 2), round(ay, 2), round(az, 2)],
        "gyro": [round(gx, 2), round(gy, 2), round(gz, 2)],
    }


# ============================================================
# SIDEBAR CONTROLS
# ============================================================
st.sidebar.title("🎛️ Glove Controls")

input_source = st.sidebar.radio(
    "Data Source",
    ["Interactive Simulation", "ESP32 USB Serial"],
    index=0,
    help="Switch between physical ESP32 glove and interactive virtual simulation."
)

if input_source == "ESP32 USB Serial":
    st.sidebar.subheader("Serial Connection")
    ports = find_serial_ports()
    port_options = [p["port"] for p in ports]
    
    if port_options:
        selected_port = st.sidebar.selectbox("Select Port", port_options)
    else:
        selected_port = st.sidebar.text_input("Port (manual)", value="COM3")
        st.sidebar.caption("⚠️ No active USB serial ports auto-detected.")

    baud_rate = st.sidebar.selectbox("Baud Rate", [115200, 9600, 57600], index=0)

    col_btn1, col_btn2 = st.sidebar.columns(2)
    if col_btn1.button("🔌 Connect", use_container_width=True):
        try:
            reader = SerialReader(port=selected_port, baud_rate=baud_rate)
            if reader.connect():
                st.session_state.reader = reader
                st.sidebar.success(f"Connected to {selected_port}")
            else:
                st.sidebar.error("Failed to connect.")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

    if col_btn2.button("Disconnect", use_container_width=True):
        if st.session_state.reader:
            st.session_state.reader.disconnect()
            st.session_state.reader = None
            st.sidebar.info("Disconnected.")

else:  # Interactive Simulation
    st.sidebar.subheader("Simulation Settings")
    sim_mode = st.sidebar.selectbox(
        "Simulation Preset",
        ["Live Playback Loop", "OPEN_PALM", "CLOSED_FIST", "POINTING", "PEACE", "THUMBS_UP", "RESTING", "Manual Sliders"]
    )
    sim_noise = st.sidebar.checkbox("Add Natural Sensor Jitter / Noise", value=True)

    manual_packet = None
    if sim_mode == "Manual Sliders":
        st.sidebar.markdown("##### 🖐️ Finger Flex Levels")
        m_thumb = st.sidebar.slider("Thumb Bend (ADC)", 800, 3600, 3200)
        m_index = st.sidebar.slider("Index Bend (ADC)", 800, 3600, 3200)
        m_middle = st.sidebar.slider("Middle Bend (ADC)", 800, 3600, 3200)
        m_ring = st.sidebar.slider("Ring Bend (ADC)", 800, 3600, 3200)
        m_little = st.sidebar.slider("Little Bend (ADC)", 800, 3600, 3200)

        st.sidebar.markdown("##### 🧭 IMU Hand Tilt")
        m_ax = st.sidebar.slider("Accel X (Side-tilt)", -10.0, 10.0, 0.0)
        m_ay = st.sidebar.slider("Accel Y (Forward-tilt)", -10.0, 10.0, 0.0)
        m_az = st.sidebar.slider("Accel Z (Vertical gravity)", -10.0, 10.0, 9.8)

        manual_packet = {
            "timestamp_ms": int(time.time() * 1000) % 10000000,
            "flex": [m_thumb, m_index, m_middle, m_ring, m_little],
            "accel": [m_ax, m_ay, m_az],
            "gyro": [0.0, 0.0, 0.0],
        }

st.sidebar.divider()
st.sidebar.subheader("Model Inference Settings")
conf_threshold = st.sidebar.slider("Confidence Threshold", 0.50, 0.95, 0.70, 0.05)
smoothing_window = st.sidebar.slider("Smoothing Window Size", 1, 10, 5, 1)

if st.session_state.predictor:
    st.session_state.predictor.confidence_threshold = conf_threshold
    st.session_state.predictor.smoothing_window = smoothing_window

# Stream Toggle
st.sidebar.divider()
stream_active = st.sidebar.toggle("⚡ Start Live Stream Animation", value=True)


# ============================================================
# MAIN INTERFACE
# ============================================================
st.markdown('<div class="main-title">🧤 AI Smart Sign Language Glove</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Senior Design Project — Team 2 | Real-Time Gesture Recognition & Telemetry</div>', unsafe_allow_html=True)

# Status notification if predictor or reader has issues
if not st.session_state.predictor:
    st.error(f"❌ ML Model not loaded: {getattr(st.session_state, 'predictor_error', 'Unknown error')}. Please run backend/train_model.py.")
    st.stop()

# Prepare current packet to display
current_packet: Optional[Dict[str, Any]] = None

if input_source == "Interactive Simulation":
    if sim_mode == "Manual Sliders":
        current_packet = manual_packet
    elif sim_mode == "Live Playback Loop":
        # Cycle through gestures every 5 seconds
        presets = ["OPEN_PALM", "CLOSED_FIST", "POINTING", "PEACE", "THUMBS_UP", "RESTING"]
        if time.time() - st.session_state.sim_last_cycle > 4.5:
            st.session_state.sim_last_cycle = time.time()
            st.session_state.sim_preset_idx = (st.session_state.sim_preset_idx + 1) % len(presets)
        current_preset = presets[st.session_state.sim_preset_idx]
        current_packet = generate_simulated_packet(current_preset, noise=sim_noise)
    else:
        current_packet = generate_simulated_packet(sim_mode, noise=sim_noise)

elif input_source == "ESP32 USB Serial":
    reader = st.session_state.reader
    if reader and reader.is_connected:
        is_valid, packet, _ = reader.read_packet()
        if is_valid and packet:
            st.session_state.last_packet = packet
            current_packet = packet
        elif "last_packet" in st.session_state:
            current_packet = st.session_state.last_packet
        else:
            current_packet = generate_simulated_packet("RESTING", noise=False)
    else:
        st.info("💡 ESP32 is not connected. Connect via sidebar or switch Data Source to 'Interactive Simulation'.")
        current_packet = generate_simulated_packet("RESTING", noise=False)


# ============================================================
# REAL-TIME INFERENCE COMPUTATION
# ============================================================
gesture, confidence, prob_dict = st.session_state.predictor.predict(current_packet)
info = GESTURE_INFO.get(gesture, {})
emoji = info.get("emoji", "❓")
meaning = info.get("meaning", "Transitioning or unrecognized")
description = info.get("description", "")

# Determine banner color based on state
if gesture == "UNKNOWN":
    banner_color = "#757575"  # Grey
    status_label = "UNKNOWN / LOW CONFIDENCE"
elif gesture == "RESTING":
    banner_color = "#37474F"  # Dark Slate
    status_label = "RESTING / NEUTRAL"
else:
    banner_color = "#2E7D32"  # Success Green
    status_label = "GESTURE RECOGNIZED"


# ============================================================
# TOP SECTION: GESTURE PREDICTION BANNER & PROBABILITIES
# ============================================================
col_banner, col_probs = st.columns([1.2, 1.0])

with col_banner:
    st.markdown(f"""
    <div class="gesture-banner" style="background-color: {banner_color};">
        <div style="font-size: 0.9rem; letter-spacing: 2px; text-transform: uppercase; opacity: 0.85;">{status_label}</div>
        <div style="font-size: 3.5rem; margin: 10px 0;">{emoji} {gesture}</div>
        <div style="font-size: 1.3rem; font-weight: 600;">{meaning}</div>
        <div style="font-size: 0.9rem; opacity: 0.85; margin-top: 5px;">Confidence: <b>{confidence*100:.1f}%</b> | {description}</div>
    </div>
    """, unsafe_allow_html=True)

with col_probs:
    # Bar chart of class probabilities
    prob_df = pd.DataFrame({
        "Gesture": list(prob_dict.keys()),
        "Probability": [v * 100 for v in prob_dict.values()]
    }).sort_values(by="Probability", ascending=True)

    fig_probs = px.bar(
        prob_df,
        x="Probability",
        y="Gesture",
        orientation="h",
        text=prob_df["Probability"].apply(lambda v: f"{v:.1f}%"),
        color="Probability",
        color_continuous_scale="Blues",
        range_x=[0, 100],
        height=220,
    )
    fig_probs.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Confidence (%)",
        yaxis_title="",
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig_probs, use_container_width=True)


# ============================================================
# MIDDLE SECTION: 5 FLEX SENSORS BEND GAUGES
# ============================================================
st.subheader("🖐️ 5-Finger Flex Sensors Telemetry")

flex_cols = st.columns(5)
flex_values = current_packet["flex"]

for i, col in enumerate(flex_cols):
    raw_val = flex_values[i]
    bend_pct = raw_to_bend_pct(raw_val)
    volt = adc_to_voltage(raw_val)
    finger_name = FLEX_SENSOR_NAMES[i]

    # Finger state label
    if bend_pct > 65:
        state_text = "🔴 Bent"
    elif bend_pct > 30:
        state_text = "🟡 Partial"
    else:
        state_text = "🟢 Straight"

    with col:
        st.markdown(f"**{finger_name}**")
        st.progress(int(bend_pct))
        st.metric(
            label=f"{bend_pct:.0f}% Bend",
            value=f"{raw_val} ADC",
            delta=f"{volt:.2f} V",
            delta_color="off"
        )
        st.caption(f"State: {state_text}")


# ============================================================
# LOWER SECTION: MPU6050 ORIENTATION & MOTION
# ============================================================
st.subheader("🧭 Hand Orientation & Motion (MPU6050 IMU)")

imu_col1, imu_col2, imu_col3 = st.columns(3)

ax, ay, az = current_packet["accel"]
gx, gy, gz = current_packet["gyro"]

# Calculate approximate Roll & Pitch angles
eps = 1e-4
pitch = math.atan2(-ax, math.sqrt(ay*ay + az*az + eps)) * 180.0 / math.pi
roll = math.atan2(ay, az + eps) * 180.0 / math.pi
accel_mag = math.sqrt(ax*ax + ay*ay + az*az)

with imu_col1:
    st.markdown("##### Accelerometer (m/s²)")
    fig_accel = go.Figure(go.Bar(
        x=["X (Side)", "Y (Fwd)", "Z (Vert)"],
        y=[ax, ay, az],
        marker_color=["#1976D2", "#388E3C", "#D32F2F"],
    ))
    fig_accel.update_layout(
        height=180,
        margin=dict(l=20, r=20, t=10, b=20),
        yaxis=dict(range=[-12, 12], title="m/s²"),
    )
    st.plotly_chart(fig_accel, use_container_width=True)

with imu_col2:
    st.markdown("##### Gyroscope (°/s)")
    fig_gyro = go.Figure(go.Bar(
        x=["X", "Y", "Z"],
        y=[gx, gy, gz],
        marker_color=["#7B1FA2", "#F57C00", "#0097A7"],
    ))
    fig_gyro.update_layout(
        height=180,
        margin=dict(l=20, r=20, t=10, b=20),
        yaxis=dict(range=[-180, 180], title="°/s"),
    )
    st.plotly_chart(fig_gyro, use_container_width=True)

with imu_col3:
    st.markdown("##### Hand Posture Tilt")
    st.metric("Pitch (Tilt forward/back)", f"{pitch:.1f}°")
    st.metric("Roll (Rotate side/side)", f"{roll:.1f}°")
    st.caption(f"Total Acceleration: {accel_mag:.2f} m/s² (1G ≈ 9.81 m/s²)")


# ============================================================
# BOTTOM SECTION: DIAGNOSTICS & PACKET INSPECTOR
# ============================================================
with st.expander("🔍 Stream Diagnostics & Raw JSON Packet Inspector", expanded=False):
    d_col1, d_col2 = st.columns([1, 2])
    with d_col1:
        st.write("**Packet Metadata:**")
        st.write(f"- Timestamp: `{current_packet['timestamp_ms']} ms`")
        st.write(f"- Source: `{input_source}`")
        if input_source == "ESP32 USB Serial" and st.session_state.reader:
            st.write(f"- Valid Packets: `{st.session_state.reader.valid_packets}`")
            st.write(f"- Packet Rate: `{st.session_state.reader.get_packet_rate():.1f} Hz`")
    with d_col2:
        st.write("**Raw JSON Payload:**")
        st.json(current_packet)


# Continuous streaming loop when live toggle is on
if stream_active:
    time.sleep(0.08)  # ~12 FPS refresh for smooth UI without freezing browser
    st.rerun()

