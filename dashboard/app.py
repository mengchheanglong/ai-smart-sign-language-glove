"""
app.py — Modern UI/UX Interactive Telemetry & AI Dashboard
AI Smart Sign Language Glove — Team 2 Senior Design Project

Features:
- High-contrast, glassmorphism visual styling suitable for university presentations
- Live Hero Gesture recognition card with confidence gauge and translation meaning
- Live Sentence / Gesture History timeline (translating continuous gestures into words)
- 5-Finger interactive flex telemetry cards with color-coded bend indicators
- 6-DOF IMU motion & hand posture attitude telemetry (pitch, roll, total acceleration)
- Bidirectional hardware controls: 💡 Blink LED, 🔊 Beep Buzzer, 🔄 Refresh Ports
- Dual input mode: Real ESP32 USB Serial (COM7 auto-detect) vs Interactive Simulation
"""

import sys
import os
import time
import math
import random
from pathlib import Path
from typing import Dict, Any, Optional, List

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
)
from backend.predictor import GesturePredictor
from backend.serial_reader import SerialReader

# ============================================================
# STREAMLIT PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="AI Sign Language Glove Telemetry",
    page_icon="🧤",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# PREMIUM GLASSMORPHISM & MODERN CSS DESIGN SYSTEM
# ============================================================
st.markdown("""
<style>
    /* Global Typography & Background */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    /* Top Navigation Header */
    .header-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(12px);
        padding: 18px 24px;
        border-radius: 16px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25);
    }
    .header-title {
        font-size: 1.7rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38BDF8 0%, #818CF8 50%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        line-height: 1.2;
    }
    .header-subtitle {
        font-size: 0.85rem;
        color: #94A3B8;
        margin-top: 4px;
        font-weight: 500;
    }
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        letter-spacing: 0.3px;
    }
    .badge-live {
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.4);
        color: #34D399;
    }
    .badge-sim {
        background: rgba(168, 85, 247, 0.15);
        border: 1px solid rgba(168, 85, 247, 0.4);
        color: #C084FC;
    }
    .pulse-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: currentColor;
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.8; }
        50% { transform: scale(1.3); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.8; }
    }

    /* Hero Gesture Banner */
    .hero-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 20px;
        padding: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        position: relative;
        overflow: hidden;
    }
    .gesture-emoji {
        font-size: 4.2rem;
        line-height: 1;
        filter: drop-shadow(0 4px 12px rgba(0,0,0,0.3));
    }
    .gesture-name {
        font-size: 2.2rem;
        font-weight: 800;
        color: #F8FAFC;
        letter-spacing: -0.5px;
        margin: 6px 0 2px 0;
    }
    .gesture-meaning {
        font-size: 1.15rem;
        font-weight: 600;
        color: #38BDF8;
    }

    /* Finger Cards */
    .finger-box {
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 16px 14px;
        text-align: center;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .finger-box:hover {
        transform: translateY(-2px);
        border-color: rgba(56, 189, 248, 0.4);
    }
    .finger-header {
        font-size: 0.95rem;
        font-weight: 700;
        color: #F1F5F9;
        margin-bottom: 8px;
    }
    .finger-adc {
        font-size: 1.5rem;
        font-weight: 800;
        color: #F8FAFC;
        margin: 4px 0;
    }
    .finger-meta {
        font-size: 0.8rem;
        color: #94A3B8;
    }

    /* Translation Ticker / Sentence Builder */
    .ticker-container {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 12px;
        padding: 12px 18px;
        margin: 16px 0 24px 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .ticker-label {
        font-size: 0.8rem;
        font-weight: 700;
        color: #38BDF8;
        text-transform: uppercase;
        letter-spacing: 1px;
        white-space: nowrap;
    }
    .ticker-text {
        font-size: 1.15rem;
        font-weight: 600;
        color: #F8FAFC;
        flex-grow: 1;
        letter-spacing: 0.2px;
    }

    /* Card Panels */
    .panel-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 18px;
        margin-bottom: 16px;
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

if "history_tokens" not in st.session_state:
    st.session_state.history_tokens = ["HELLO"]

if "last_stable_gesture" not in st.session_state:
    st.session_state.last_stable_gesture = None

if "gesture_hold_count" not in st.session_state:
    st.session_state.gesture_hold_count = 0

if "sim_preset_idx" not in st.session_state:
    st.session_state.sim_preset_idx = 0

if "sim_last_cycle" not in st.session_state:
    st.session_state.sim_last_cycle = time.time()


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def raw_to_bend_pct(raw_adc: int, straight_adc: int = 3200, bent_adc: int = 1100) -> float:
    """Map raw ADC reading to 0-100% bend."""
    if straight_adc == bent_adc:
        return 0.0
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
        f = [2400, 2400, 2400, 2400, 2400]
        ax, ay, az = [0.0, 0.0, 9.81]
        gx, gy, gz = [0.0, 0.0, 0.0]

    if noise:
        f = [int(val + random.gauss(0, 25)) for val in f]
        ax += random.gauss(0, 0.06)
        ay += random.gauss(0, 0.06)
        az += random.gauss(0, 0.06)
        gx += random.gauss(0, 0.08)
        gy += random.gauss(0, 0.08)
        gz += random.gauss(0, 0.08)

    f = [max(0, min(4095, val)) for val in f]
    return {
        "timestamp_ms": int(time.time() * 1000) % 10000000,
        "flex": f,
        "accel": [round(ax, 2), round(ay, 2), round(az, 2)],
        "gyro": [round(gx, 2), round(gy, 2), round(gz, 2)],
    }


# ============================================================
# SIDEBAR NAVIGATION & HARDWARE CONTROLS
# ============================================================
st.sidebar.markdown("### 🎛️ Glove Control Station")

# Auto-detect available serial ports
available_ports = find_serial_ports(prefer_usb=True)
has_real_hardware = len(available_ports) > 0 and any("ch34" in p.get("description", "").lower() or "com7" in p.get("port", "").lower() for p in available_ports)

default_source_idx = 1 if has_real_hardware else 0

input_source = st.sidebar.radio(
    "Data Source Mode",
    ["Interactive Simulation", "ESP32 USB Serial"],
    index=default_source_idx,
    help="Toggle between live ESP32 serial communication and simulated virtual telemetry."
)

if input_source == "ESP32 USB Serial":
    st.sidebar.markdown("#### 🔌 Serial Port Configuration")
    
    col_port_sel, col_port_ref = st.sidebar.columns([3, 1])
    with col_port_sel:
        port_names = [p["port"] for p in available_ports]
        if port_names:
            # Default to COM7 if present
            default_port_idx = port_names.index("COM7") if "COM7" in port_names else 0
            selected_port = st.selectbox("Select Active Port", port_names, index=default_port_idx)
        else:
            selected_port = st.text_input("Port Name (Manual)", value="COM7")
    
    with col_port_ref:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄", help="Scan USB ports"):
            st.rerun()

    baud_rate = st.sidebar.selectbox("Baud Rate", [115200, 9600, 57600], index=0)

    # Connect / Disconnect Buttons
    col_conn, col_disc = st.sidebar.columns(2)
    if col_conn.button("⚡ Connect", use_container_width=True, type="primary"):
        try:
            reader = SerialReader(port=selected_port, baud_rate=baud_rate)
            if reader.connect():
                st.session_state.reader = reader
                st.sidebar.success(f"Connected to {selected_port}!")
            else:
                st.sidebar.error("Could not open port. Check USB cable.")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

    if col_disc.button("Disconnect", use_container_width=True):
        if st.session_state.reader:
            st.session_state.reader.disconnect()
            st.session_state.reader = None
            st.sidebar.info("Disconnected from ESP32.")

    # Hardware Feedback Buttons
    st.sidebar.markdown("#### 💡 Hardware Actuators")
    col_led, col_buzz = st.sidebar.columns(2)
    with col_led:
        if st.button("💡 Test LED", use_container_width=True, help="Send pulse to GPIO18 LED"):
            if st.session_state.reader and st.session_state.reader.is_connected:
                st.session_state.reader.send_command("b\n")
                st.toast("Sent LED Pulse Command ('b') to ESP32", icon="💡")
            else:
                st.toast("Connect ESP32 first to test LED", icon="⚠️")
    with col_buzz:
        if st.button("🔊 Test Buzzer", use_container_width=True, help="Send 2400Hz beep to GPIO19"):
            if st.session_state.reader and st.session_state.reader.is_connected:
                st.session_state.reader.send_command("z\n")
                st.toast("Sent Buzzer Tone Command ('z') to ESP32", icon="🔊")
            else:
                st.toast("Connect ESP32 first to test Buzzer", icon="⚠️")

else:  # Interactive Simulation Mode
    st.sidebar.markdown("#### 🧪 Virtual Hand Simulation")
    sim_mode = st.sidebar.selectbox(
        "Simulation Routine",
        ["Live Playback Loop", "OPEN_PALM", "CLOSED_FIST", "POINTING", "PEACE", "THUMBS_UP", "RESTING", "Manual Sliders"],
        help="Select a predefined gesture pose or test individual finger sliders."
    )
    sim_noise = st.sidebar.checkbox("Add Natural Sensor Jitter / Noise", value=True)

    manual_packet = None
    if sim_mode == "Manual Sliders":
        st.sidebar.markdown("##### 🖐️ Finger Bending Levels")
        m_thumb = st.sidebar.slider("Thumb (D32)", 800, 3600, 3200)
        m_index = st.sidebar.slider("Index (D33)", 800, 3600, 3200)
        m_middle = st.sidebar.slider("Middle (D34)", 800, 3600, 3200)
        m_ring = st.sidebar.slider("Ring (D35)", 800, 3600, 3200)
        m_little = st.sidebar.slider("Little (VP)", 800, 3600, 3200)

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

# Model Tuning
st.sidebar.divider()
st.sidebar.markdown("#### 🧠 AI Model Tuning")
conf_threshold = st.sidebar.slider("Confidence Gate", 0.50, 0.95, 0.70, 0.05, help="Predictions below this threshold fall back to UNKNOWN.")
smoothing_window = st.sidebar.slider("Debounce Window (Frames)", 1, 10, 5, 1, help="Number of rolling frames required for majority vote.")

if st.session_state.predictor:
    st.session_state.predictor.confidence_threshold = conf_threshold
    st.session_state.predictor.smoothing_window = smoothing_window

# Stream Toggle
st.sidebar.divider()
stream_active = st.sidebar.toggle("⚡ Real-Time Auto Refresh", value=True)


# ============================================================
# DATA RETRIEVAL (SERIAL VS SIMULATED)
# ============================================================
current_packet: Optional[Dict[str, Any]] = None

if input_source == "Interactive Simulation":
    badge_html = '<div class="status-badge badge-sim"><span class="pulse-dot"></span> VIRTUAL SIMULATOR</div>'
    if sim_mode == "Manual Sliders":
        current_packet = manual_packet
    elif sim_mode == "Live Playback Loop":
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
        badge_html = f'<div class="status-badge badge-live"><span class="pulse-dot"></span> LIVE: {reader.port} @ 115200</div>'
        is_valid, packet, _ = reader.read_packet()
        if is_valid and packet:
            st.session_state.last_packet = packet
            current_packet = packet
        elif "last_packet" in st.session_state:
            current_packet = st.session_state.last_packet
        else:
            current_packet = generate_simulated_packet("RESTING", noise=False)
    else:
        badge_html = '<div class="status-badge" style="background: rgba(239, 68, 68, 0.15); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.3);">⚠️ HARDWARE DISCONNECTED</div>'
        current_packet = generate_simulated_packet("RESTING", noise=False)


# ============================================================
# TOP HEADER BAR
# ============================================================
st.markdown(f"""
<div class="header-bar">
    <div>
        <h1 class="header-title">AI Smart Sign Language Glove</h1>
        <div class="header-subtitle">Senior Design Project • Team 2 | Real-Time Multimodal Sign Translation Telemetry</div>
    </div>
    <div>
        {badge_html}
    </div>
</div>
""", unsafe_allow_html=True)

# Verification check for model
if not st.session_state.predictor:
    st.error(f"❌ ML Model not found in `models/gesture_model.joblib`. Run `python backend/train_model.py` to train it.")
    st.stop()


# ============================================================
# AI INFERENCE & SENTENCE BUILDER
# ============================================================
gesture, confidence, prob_dict = st.session_state.predictor.predict(current_packet)
info = GESTURE_INFO.get(gesture, {})
emoji = info.get("emoji", "❓")
meaning = info.get("meaning", "Transitioning or unrecognized")
description = info.get("description", "")

# Update Sentence Builder / History
if gesture not in ["UNKNOWN", "RESTING"]:
    if gesture == st.session_state.last_stable_gesture:
        st.session_state.gesture_hold_count += 1
        # Add to sentence after holding stably for ~1.5 seconds (12 frames)
        if st.session_state.gesture_hold_count == 12:
            meaning_token = meaning.split("/")[0].strip().upper()
            st.session_state.history_tokens.append(meaning_token)
            if len(st.session_state.history_tokens) > 6:
                st.session_state.history_tokens.pop(0)
    else:
        st.session_state.last_stable_gesture = gesture
        st.session_state.gesture_hold_count = 1
else:
    st.session_state.gesture_hold_count = 0

# Determine Card Gradient & Tone
if gesture == "UNKNOWN":
    banner_accent = "rgba(100, 116, 139, 0.3)"
    status_label = "TRANSITIONING / UNCERTAIN"
    badge_color = "#94A3B8"
elif gesture == "RESTING":
    banner_accent = "rgba(51, 65, 85, 0.4)"
    status_label = "RESTING / NEUTRAL HAND"
    badge_color = "#64748B"
else:
    banner_accent = "rgba(16, 185, 129, 0.25)"
    status_label = "RECOGNIZED GESTURE"
    badge_color = "#10B981"


# ============================================================
# SECTION 1: HERO GESTURE CARD & PROBABILITY SPECTRUM
# ============================================================
col_hero, col_prob_bars = st.columns([1.3, 1.0])

with col_hero:
    st.markdown(f"""
    <div class="hero-card" style="border-left: 6px solid {badge_color}; background: radial-gradient(circle at top right, {banner_accent}, rgba(15, 23, 42, 0.9) 60%);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div style="font-size: 0.8rem; font-weight: 700; letter-spacing: 1.5px; color: {badge_color}; text-transform: uppercase;">
                {status_label}
            </div>
            <div style="background: rgba(255,255,255,0.08); padding: 4px 10px; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; color: #E2E8F0;">
                Confidence: <span style="color: {badge_color}; font-weight: 800;">{confidence*100:.1f}%</span>
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 20px; margin: 16px 0;">
            <div class="gesture-emoji">{emoji}</div>
            <div>
                <div class="gesture-name">{gesture}</div>
                <div class="gesture-meaning">"{meaning}"</div>
            </div>
        </div>
        <div style="font-size: 0.85rem; color: #94A3B8; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 10px;">
            <b>Description:</b> {description}
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_prob_bars:
    # Modern horizontal probability breakdown
    prob_df = pd.DataFrame({
        "Gesture": list(prob_dict.keys()),
        "Confidence": [v * 100 for v in prob_dict.values()]
    }).sort_values(by="Confidence", ascending=True)

    fig_probs = go.Figure()
    fig_probs.add_trace(go.Bar(
        x=prob_df["Confidence"],
        y=prob_df["Gesture"],
        orientation="h",
        text=prob_df["Confidence"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside",
        textfont=dict(size=11, color="#CBD5E1"),
        marker=dict(
            color=prob_df["Confidence"],
            colorscale=[[0, "#334155"], [0.4, "#38BDF8"], [1.0, "#10B981"]],
            line=dict(width=0),
        ),
    ))
    fig_probs.update_layout(
        height=195,
        margin=dict(l=10, r=45, t=10, b=10),
        xaxis=dict(range=[0, 115], showgrid=False, showticklabels=False),
        yaxis=dict(tickfont=dict(size=12, color="#E2E8F0")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_probs, use_container_width=True)

# Translation History Ticker Bar
sentence_str = " ".join([f"[{t}]" for t in st.session_state.history_tokens])
col_tick, col_clear = st.columns([5, 1])
with col_tick:
    st.markdown(f"""
    <div class="ticker-container">
        <div class="ticker-label">🗣️ Sign Stream:</div>
        <div class="ticker-text">{sentence_str}</div>
    </div>
    """, unsafe_allow_html=True)
with col_clear:
    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    if st.button("Clear Ticker", use_container_width=True):
        st.session_state.history_tokens = []
        st.rerun()


# ============================================================
# SECTION 2: 5-FINGER FLEX SENSOR TELEMETRY CARDS
# ============================================================
st.markdown("### 🖐️ 5-Finger Flex Sensors Telemetry")

flex_cols = st.columns(5)
flex_values = current_packet["flex"]
finger_emojis = ["👍", "☝️", "🖕", "💍", "🤙"]
pin_labels = ["D32", "D33", "D34", "D35", "VP (36)"]

for i, col in enumerate(flex_cols):
    raw_val = flex_values[i]
    bend_pct = raw_to_bend_pct(raw_val)
    volt = adc_to_voltage(raw_val)
    finger_name = FLEX_SENSOR_NAMES[i]
    emoji_ico = finger_emojis[i]
    pin_tag = pin_labels[i]

    # Color code bend state
    if bend_pct > 65:
        state_badge = '<span style="color: #F43F5E; font-weight: 700;">🔴 Bent (90°)</span>'
        bar_color = "#F43F5E"
    elif bend_pct > 30:
        state_badge = '<span style="color: #FBBF24; font-weight: 700;">🟡 Flexed</span>'
        bar_color = "#FBBF24"
    else:
        state_badge = '<span style="color: #34D399; font-weight: 700;">🟢 Flat / Straight</span>'
        bar_color = "#34D399"

    with col:
        st.markdown(f"""
        <div class="finger-box">
            <div class="finger-header">{emoji_ico} {finger_name} <span style="font-size: 0.75rem; color: #64748B;">({pin_tag})</span></div>
            <div class="finger-adc">{raw_val} <span style="font-size: 0.8rem; color: #94A3B8;">ADC</span></div>
            <div class="finger-meta">{volt:.2f} V • {bend_pct:.0f}% Bend</div>
            <div style="background: rgba(255,255,255,0.1); height: 6px; border-radius: 999px; margin: 10px 0 8px 0; overflow: hidden;">
                <div style="background: {bar_color}; width: {bend_pct}%; height: 100%; border-radius: 999px;"></div>
            </div>
            <div style="font-size: 0.8rem;">{state_badge}</div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# SECTION 3: MPU6050 6-DOF IMU MOTION & HAND ATTITUDE
# ============================================================
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
st.markdown("### 🧭 Hand Orientation & Motion (MPU6050 6-DOF IMU)")

imu_col1, imu_col2, imu_col3 = st.columns([1.1, 1.1, 1.0])

ax, ay, az = current_packet["accel"]
gx, gy, gz = current_packet["gyro"]

# Math: Approximate Roll & Pitch angles
eps = 1e-4
pitch = math.atan2(-ax, math.sqrt(ay*ay + az*az + eps)) * 180.0 / math.pi
roll = math.atan2(ay, az + eps) * 180.0 / math.pi
accel_mag = math.sqrt(ax*ax + ay*ay + az*az)

# Posture description
if abs(pitch) < 15 and abs(roll) < 15:
    posture_desc = "Palm Flat / Level"
elif pitch > 35:
    posture_desc = "Fingers Tilted Upward"
elif pitch < -35:
    posture_desc = "Fingers Pointing Downward"
elif roll > 35:
    posture_desc = "Hand Rolled Right"
elif roll < -35:
    posture_desc = "Hand Rolled Left"
else:
    posture_desc = "Angled Orientation"

with imu_col1:
    st.markdown("##### 📈 Linear Acceleration (m/s²)")
    fig_accel = go.Figure(go.Bar(
        x=["X (Side)", "Y (Fwd)", "Z (Vert)"],
        y=[ax, ay, az],
        marker=dict(color=["#38BDF8", "#34D399", "#F43F5E"]),
        text=[f"{v:.1f}" for v in [ax, ay, az]],
        textposition="outside",
    ))
    fig_accel.update_layout(
        height=175,
        margin=dict(l=20, r=20, t=10, b=20),
        yaxis=dict(range=[-14, 14], showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8"),
    )
    st.plotly_chart(fig_accel, use_container_width=True)

with imu_col2:
    st.markdown("##### 🔄 Angular Velocity (°/s)")
    fig_gyro = go.Figure(go.Bar(
        x=["Pitch Rate", "Roll Rate", "Yaw Rate"],
        y=[gx, gy, gz],
        marker=dict(color=["#818CF8", "#F59E0B", "#06B6D4"]),
        text=[f"{v:.0f}" for v in [gx, gy, gz]],
        textposition="outside",
    ))
    fig_gyro.update_layout(
        height=175,
        margin=dict(l=20, r=20, t=10, b=20),
        yaxis=dict(range=[-180, 180], showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8"),
    )
    st.plotly_chart(fig_gyro, use_container_width=True)

with imu_col3:
    st.markdown("##### 📐 Hand Attitude / Posture")
    st.markdown(f"""
    <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 14px; margin-bottom: 8px;">
        <div style="font-size: 0.8rem; color: #94A3B8;">Estimated Posture:</div>
        <div style="font-size: 1.15rem; font-weight: 700; color: #38BDF8; margin: 2px 0 10px 0;">{posture_desc}</div>
        <div style="display: flex; justify-content: space-between; font-size: 0.85rem; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px;">
            <span>Pitch: <b style="color: #F8FAFC;">{pitch:+.1f}°</b></span>
            <span>Roll: <b style="color: #F8FAFC;">{roll:+.1f}°</b></span>
            <span>G-Force: <b style="color: #F8FAFC;">{accel_mag/9.81:.2f}G</b></span>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# SECTION 4: STREAM DIAGNOSTICS & PACKET INSPECTOR
# ============================================================
with st.expander("🔍 System Diagnostics & Raw JSON Telemetry Packet", expanded=False):
    d_col1, d_col2 = st.columns([1, 2])
    with d_col1:
        st.write("**Stream Telemetry:**")
        st.write(f"- Timestamp: `{current_packet['timestamp_ms']} ms`")
        st.write(f"- Mode: `{input_source}`")
        if input_source == "ESP32 USB Serial" and st.session_state.reader:
            st.write(f"- Valid Frames Received: `{st.session_state.reader.valid_packets}`")
            st.write(f"- Data Rate: `{st.session_state.reader.get_packet_rate():.1f} Hz`")
    with d_col2:
        st.write("**Raw JSON Packet Payload:**")
        st.json(current_packet)


# Continuous streaming loop when live toggle is on
if stream_active:
    time.sleep(0.08)  # ~12 FPS refresh rate for buttery smooth UI without freezing the browser
    st.rerun()
