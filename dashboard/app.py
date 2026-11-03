"""
app.py — Telemetry console for the AI Smart Sign Language Glove
Team 2 — Senior Design Project

Design intent: this is a measurement instrument, not a marketing page. The
interface is a light, paper-like report surface with hairline structure, one
accent colour, monospaced tabular figures for every measured value, and no
decorative gradients or emoji. Colour carries state only where state is real
(recognised / below gate / device missing); everything else is hierarchy from
type, spacing and rules.

Structure:
- Session meta in the header: data source, elapsed time, frame rate, gate
- Current recognition + class probabilities against the confidence gate
- Five flex channels as a measurement table, not five decorated cards
- IMU attitude: derived pitch/roll/resultant, then per-axis acceleration and rate
- Session log: committed gesture tokens with the confidence that committed them
- Measurement notes: what the console shows, and what it does not
"""

import math
import random
import sys
import time
from collections import deque
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import plotly.graph_objects as go

from backend.utils import (
    find_serial_ports,
    DEFAULT_BAUD_RATE,
    GESTURE_INFO,
    FLEX_SENSOR_NAMES,
)
from backend.predictor import GesturePredictor
from backend.serial_reader import SerialReader

# ============================================================
# PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="Telemetry console · Sign Language Glove",
    page_icon="🧤",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# DESIGN TOKENS
# Every colour and font in the UI and in the charts comes from here.
# Ratios measured with the ui-ux-design contrast script (WCAG 2.2 AA):
#   text/bg 17.72:1 · text-2/bg 7.73:1 · text-3/bg 5.28:1
#   accent/bg 5.58:1 · ok/bg 7.29:1 · warn/bg 5.93:1 · danger/bg 6.57:1
# ============================================================
T: Dict[str, str] = {
    "bg": "#FFFFFF",
    "surface": "#FAFAFA",
    "surface_2": "#F4F4F5",
    "surface_3": "#EBEBEE",
    "line": "rgba(24,24,27,0.10)",
    "line_strong": "rgba(24,24,27,0.18)",
    "text": "#18181B",
    "text_2": "#52525B",
    "text_3": "#6B6B74",
    "accent": "#1B62D6",
    "accent_soft": "rgba(27,98,214,0.10)",
    "on_ink": "#FFFFFF",
    "ok": "#12633F",
    "ok_soft": "rgba(18,99,63,0.07)",
    "ok_line": "rgba(18,99,63,0.26)",
    "warn": "#8A5A00",
    "warn_soft": "rgba(138,90,0,0.07)",
    "warn_line": "rgba(138,90,0,0.26)",
    "danger": "#B42318",
    "danger_soft": "rgba(180,35,24,0.06)",
    "danger_line": "rgba(180,35,24,0.24)",
    "bar": "rgba(24,24,27,0.72)",
    "bar_neutral": "rgba(24,24,27,0.18)",
    "sans": '-apple-system, "Segoe UI", Inter, "Helvetica Neue", Arial, sans-serif',
    "mono": 'ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace',
}

CSS_TEMPLATE = Template("""
<style>
:root {
  --bg: $bg; --surface: $surface; --surface-2: $surface_2; --surface-3: $surface_3;
  --line: $line; --line-strong: $line_strong;
  --text: $text; --text-2: $text_2; --text-3: $text_3;
  --accent: $accent; --accent-soft: $accent_soft; --on-ink: $on_ink;
  --ok: $ok; --ok-soft: $ok_soft; --ok-line: $ok_line;
  --warn: $warn; --warn-soft: $warn_soft; --warn-line: $warn_line;
  --danger: $danger; --danger-soft: $danger_soft; --danger-line: $danger_line;
  --sans: $sans; --mono: $mono;
}
html, body, .stApp { font-family: var(--sans); }
.stApp { background: var(--bg); color: var(--text); }
.block-container { padding-top: 1.6rem; padding-bottom: 3.5rem; max-width: 1340px; }
#MainMenu, footer { visibility: hidden; }

/* Streamlit chrome, aligned to the token set */
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--line); }
[data-testid="stSidebar"] > div:first-child { padding-top: 1.1rem; }
[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
.stApp button { font-family: inherit; font-size: 13px; }
.stApp button[kind="secondary"], .stApp [data-testid="stBaseButton-secondary"] {
  background: var(--bg); color: var(--text); border: 1px solid var(--line-strong);
  border-radius: 8px; font-weight: 500;
}
.stApp button[kind="secondary"]:hover, .stApp [data-testid="stBaseButton-secondary"]:hover {
  background: var(--surface-2); border-color: var(--text-3); color: var(--text);
}
.stApp button[kind="primary"], .stApp [data-testid="stBaseButton-primary"] {
  background: var(--text); color: var(--on-ink); border: 1px solid var(--text);
  border-radius: 8px; font-weight: 600;
}
.stApp button[kind="primary"]:hover, .stApp [data-testid="stBaseButton-primary"]:hover {
  background: var(--text-2); border-color: var(--text-2); color: var(--on-ink);
}
.stApp :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
[data-testid="stExpander"] details { border: 1px solid var(--line); border-radius: 10px; background: var(--bg); }
[data-testid="stExpander"] summary { font-size: 13px; font-weight: 500; color: var(--text-2); }
[data-testid="stMetric"] { background: transparent; }
hr { border-color: var(--line); }

/* Header */
.console-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 28px; flex-wrap: wrap; }
.eyebrow { font-family: var(--mono); font-size: 11px; color: var(--text-3); }
.console-title { font-size: 24px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.25; margin-top: 5px; color: var(--text); }
.console-sub { font-size: 13px; color: var(--text-2); margin-top: 5px; }
.head-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 10px; }
.meta-row { display: flex; gap: 26px; }
.mi-k { font-family: var(--mono); font-size: 10px; color: var(--text-3); }
.mi-v { font-family: var(--mono); font-size: 13px; color: var(--text); font-variant-numeric: tabular-nums; margin-top: 2px; }

/* Status chips: colour plus an explicit word, never colour alone */
.chip { display: inline-flex; align-items: center; gap: 8px; padding: 4px 11px; border-radius: 999px; font-size: 12px; font-weight: 500; border: 1px solid var(--line-strong); color: var(--text-2); background: var(--bg); white-space: nowrap; }
.chip-ok { color: var(--ok); border-color: var(--ok-line); background: var(--ok-soft); }
.chip-warn { color: var(--warn); border-color: var(--warn-line); background: var(--warn-soft); }
.chip-danger { color: var(--danger); border-color: var(--danger-line); background: var(--danger-soft); }
.dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.dot-open { background: transparent; box-shadow: inset 0 0 0 1.5px currentColor; }
.dot-half { background: linear-gradient(90deg, currentColor 50%, transparent 50%); box-shadow: inset 0 0 0 1.5px currentColor; }

.notice { font-size: 13px; color: var(--warn); background: var(--warn-soft); border: 1px solid var(--warn-line); border-radius: 8px; padding: 10px 14px; margin: 14px 0 0; }

/* Section headers: the one heading pattern, used everywhere */
.sec { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin: 30px 0 4px; padding-bottom: 8px; border-bottom: 1px solid var(--line); }
.sec-title { font-size: 13px; font-weight: 600; color: var(--text); }
.sec-meta { font-family: var(--mono); font-size: 11px; color: var(--text-3); }
.sec-note { font-size: 12px; color: var(--text-3); margin: 6px 0 0; }

/* Recognition readout */
.recog { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-top: 18px; }
.recog-value { font-size: 31px; font-weight: 600; letter-spacing: -0.025em; line-height: 1.05; color: var(--text); }
.recog-id { font-family: var(--mono); font-size: 11px; color: var(--text-3); margin-top: 7px; }
.recog-gloss { font-size: 16px; color: var(--text-2); margin-top: 15px; }
.recog-gloss b { color: var(--text); font-weight: 600; }
.readout { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; margin-top: 20px; border-top: 1px solid var(--line); }
.rcell { padding: 12px 0 0; border-left: 1px solid var(--line); padding-left: 16px; }
.rcell:first-child { border-left: none; padding-left: 0; }
.rcell .k { font-size: 11px; color: var(--text-3); }
.rcell .v { font-family: var(--mono); font-size: 14px; font-weight: 500; color: var(--text); font-variant-numeric: tabular-nums; margin-top: 4px; }
.rcell .unit { font-family: var(--sans); font-size: 11px; color: var(--text-3); font-weight: 400; }
.readout-note { font-size: 12px; color: var(--text-3); margin-top: 16px; line-height: 1.55; }

/* Measurement table */
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 14px; }
.tbl th { text-align: left; font-family: var(--mono); font-weight: 500; font-size: 10px; color: var(--text-3); padding: 0 12px 8px; border-bottom: 1px solid var(--line); }
.tbl td { padding: 10px 12px; border-bottom: 1px solid var(--line); color: var(--text-2); }
.tbl tr:last-child td { border-bottom: none; }
.tbl td.name { color: var(--text); font-weight: 500; }
.tbl .num { font-family: var(--mono); font-variant-numeric: tabular-nums; color: var(--text); }
.tbl .r, .tbl th.r { text-align: right; }
.bendcell { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
.meter { display: inline-block; width: 62px; height: 4px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
.meter > i { display: block; height: 100%; background: var(--text); opacity: 0.72; border-radius: 999px; }
.state { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--text-2); }
.tbl-note { font-size: 12px; color: var(--text-3); margin-top: 10px; line-height: 1.55; }

/* IMU summary strip */
.stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 18px; border-top: 1px solid var(--line); }
.stat { padding: 12px 0 0 16px; border-left: 1px solid var(--line); }
.stat:first-child { border-left: none; padding-left: 0; }
.stat .k { font-size: 11px; color: var(--text-3); }
.stat .v { font-family: var(--mono); font-size: 17px; font-weight: 500; color: var(--text); font-variant-numeric: tabular-nums; margin-top: 5px; }
.stat .unit { font-family: var(--sans); font-size: 11px; color: var(--text-3); font-weight: 400; }

/* Translation line and session log */
.gloss-line { display: flex; align-items: baseline; gap: 16px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); padding: 13px 16px; margin-top: 16px; }
.gloss-label { font-family: var(--mono); font-size: 10px; color: var(--text-3); white-space: nowrap; }
.gloss-text { font-family: var(--mono); font-size: 15px; color: var(--text); letter-spacing: 0.02em; line-height: 1.5; }
.gloss-empty { font-size: 13px; color: var(--text-3); }
.log-empty { border: 1px solid var(--line); border-radius: 10px; padding: 18px; margin-top: 14px; }
.log-empty .t { font-size: 13px; font-weight: 600; color: var(--text); }
.log-empty .d { font-size: 12px; color: var(--text-2); margin-top: 5px; line-height: 1.6; }

/* Claim and limit, equal weight */
.notes { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--line); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; margin-top: 16px; }
.note { background: var(--bg); padding: 16px 18px; }
.note.limit { background: var(--surface); }
.note h4 { margin: 0 0 9px; font-size: 12px; font-weight: 600; color: var(--text-2); }
.note ul { margin: 0; padding-left: 15px; }
.note li { font-size: 12px; color: var(--text-2); line-height: 1.65; }

/* Sidebar */
.side-title { font-family: var(--mono); font-size: 10px; color: var(--text-3); margin: 20px 0 4px; }
.side-note { font-size: 11px; color: var(--text-3); line-height: 1.6; margin-top: 6px; }
.side-note code { font-family: var(--mono); font-size: 11px; color: var(--text-2); }

@media (max-width: 900px) {
  .readout, .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .rcell:nth-child(3), .stat:nth-child(3) { border-left: none; padding-left: 0; }
  .rcell:nth-child(3), .rcell:nth-child(4), .stat:nth-child(3), .stat:nth-child(4) { padding-top: 14px; }
  .notes { grid-template-columns: 1fr; }
  .meta-row { gap: 18px; }
  .console-title { font-size: 21px; }
}
</style>
""")

st.markdown(CSS_TEMPLATE.substitute(T), unsafe_allow_html=True)

# Constants used by the console
SOURCE_SIM = "Simulated feed"
SOURCE_SERIAL = "ESP32 serial"
PIN_LABELS = ["GPIO32", "GPIO33", "GPIO34", "GPIO35", "GPIO36 (VP)"]
CLASS_LABELS = {
    "OPEN_PALM": "Open palm",
    "CLOSED_FIST": "Closed fist",
    "POINTING": "Pointing",
    "PEACE": "Peace sign",
    "THUMBS_UP": "Thumbs up",
    "RESTING": "Resting",
    "UNKNOWN": "Unclassified",
}
CHART_CONFIG = {"displayModeBar": False}


# ============================================================
# SESSION STATE
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
    st.session_state.history_tokens = []
if "event_log" not in st.session_state:
    st.session_state.event_log = []
if "last_stable_gesture" not in st.session_state:
    st.session_state.last_stable_gesture = None
if "gesture_hold_count" not in st.session_state:
    st.session_state.gesture_hold_count = 0
if "sim_preset_idx" not in st.session_state:
    st.session_state.sim_preset_idx = 0
if "sim_last_cycle" not in st.session_state:
    st.session_state.sim_last_cycle = time.time()
if "session_start" not in st.session_state:
    st.session_state.session_start = time.time()
if "frames_seen" not in st.session_state:
    st.session_state.frames_seen = 0


# ============================================================
# HELPERS
# ============================================================
def raw_to_bend_pct(raw_adc: int, straight_adc: int = 3200, bent_adc: int = 1100) -> float:
    """Map a raw ADC reading to 0-100% bend against the divider calibration."""
    if straight_adc == bent_adc:
        return 0.0
    pct = ((straight_adc - raw_adc) / float(straight_adc - bent_adc)) * 100.0
    return max(0.0, min(100.0, pct))


def adc_to_voltage(raw_adc: int) -> float:
    return (raw_adc / 4095.0) * 3.3


def bend_state(pct: float) -> Tuple[str, str]:
    """Return (label, dot class). Shape carries the state, so colour is optional."""
    if pct > 65:
        return "Bent", "dot"
    if pct > 30:
        return "Flexed", "dot dot-half"
    return "Straight", "dot dot-open"


def generate_simulated_packet(preset_name: str, noise: bool = True) -> Dict[str, Any]:
    """Generate a synthetic glove packet for a preset pose."""
    from backend.generate_sample_data import GESTURE_PROFILES

    if preset_name in GESTURE_PROFILES:
        profile = GESTURE_PROFILES[preset_name]
        f = list(profile["flex"])
        ax, ay, az = profile["accel"]
        gx, gy, gz = profile["gyro"]
    else:
        f = [2400, 2400, 2400, 2400, 2400]
        ax, ay, az = 0.0, 0.0, 9.81
        gx, gy, gz = 0.0, 0.0, 0.0

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


def chip(text: str, tone: str = "", dot: str = "dot") -> str:
    cls = f"chip chip-{tone}" if tone else "chip"
    return f'<span class="{cls}"><span class="{dot}"></span>{text}</span>'


def styled(fig: go.Figure, height: int = 210) -> go.Figure:
    """Apply the shared chart style so every plot in the console matches."""
    fig.update_layout(
        height=height,
        margin=dict(l=6, r=10, t=10, b=6),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=T["sans"], size=11, color=T["text_2"]),
        showlegend=False,
        bargap=0.45,
        hoverlabel=dict(font=dict(family=T["sans"], size=12), bgcolor=T["bg"], bordercolor=T["line_strong"]),
    )
    return fig


def axes(fig: go.Figure, *, y_range: Tuple[float, float], y_dtick: float, y_title: str) -> go.Figure:
    fig.update_xaxes(
        showgrid=False,
        ticks="",
        linecolor=T["line"],
        tickfont=dict(family=T["sans"], size=11, color=T["text_2"]),
    )
    fig.update_yaxes(
        range=list(y_range),
        dtick=y_dtick,
        gridcolor=T["line"],
        griddash="dot",
        zeroline=True,
        zerolinecolor=T["line_strong"],
        zerolinewidth=1,
        ticks="",
        title=dict(text=y_title, font=dict(family=T["mono"], size=10, color=T["text_3"])),
        tickfont=dict(family=T["mono"], size=10, color=T["text_3"]),
    )
    return fig


def readout_cell(label: str, value: str, unit: str = "") -> str:
    u = f'<span class="unit"> {unit}</span>' if unit else ""
    return f'<div class="rcell"><div class="k">{label}</div><div class="v">{value}{u}</div></div>'


# ============================================================
# SIDEBAR — SESSION CONTROLS
# ============================================================
st.sidebar.markdown('<div class="side-title" style="margin-top:0;">DATA SOURCE</div>', unsafe_allow_html=True)

available_ports = find_serial_ports(prefer_usb=True)
has_real_hardware = any(
    "ch34" in p.get("description", "").lower() or "com7" in p.get("port", "").lower()
    for p in available_ports
)

input_source = st.sidebar.radio(
    "Data source",
    [SOURCE_SIM, SOURCE_SERIAL],
    index=1 if has_real_hardware else 0,
    label_visibility="collapsed",
    help="Simulated feed replays recorded pose profiles. ESP32 serial reads the glove over USB.",
)

if input_source == SOURCE_SERIAL:
    st.sidebar.markdown('<div class="side-title">DEVICE</div>', unsafe_allow_html=True)
    col_port, col_refresh = st.sidebar.columns([4, 1])
    with col_port:
        port_names = [p["port"] for p in available_ports]
        if port_names:
            default_port_idx = port_names.index("COM7") if "COM7" in port_names else 0
            selected_port = st.selectbox("Port", port_names, index=default_port_idx, label_visibility="collapsed")
        else:
            selected_port = st.text_input("Port", value="COM7", label_visibility="collapsed")
    with col_refresh:
        if st.button("Scan", help="Rescan USB serial ports"):
            st.rerun()

    baud_rate = st.sidebar.selectbox(
        "Baud rate",
        [DEFAULT_BAUD_RATE, 9600, 57600],
        index=0,
        label_visibility="collapsed",
    )

    col_conn, col_disc = st.sidebar.columns(2)
    if col_conn.button("Connect", width="stretch", type="primary"):
        try:
            reader = SerialReader(port=selected_port, baud_rate=baud_rate)
            if reader.connect():
                st.session_state.reader = reader
                st.sidebar.success(f"Connected to {selected_port}")
            else:
                st.sidebar.error("Port did not open. Check the USB cable and driver.")
        except Exception as e:
            st.sidebar.error(f"Connection failed: {e}")

    if col_disc.button("Disconnect", width="stretch"):
        if st.session_state.reader:
            st.session_state.reader.disconnect()
            st.session_state.reader = None
            st.sidebar.info("Disconnected")

    st.sidebar.markdown('<div class="side-title">DEVICE FEEDBACK</div>', unsafe_allow_html=True)
    col_led, col_buzz = st.sidebar.columns(2)
    with col_led:
        if st.button("Blink LED", width="stretch", help="Pulse the status LED on GPIO18"):
            if st.session_state.reader and st.session_state.reader.is_connected:
                st.session_state.reader.send_command("b\n")
                st.toast("LED pulse sent", icon="💡")
            else:
                st.toast("Connect the ESP32 first", icon="⚠️")
    with col_buzz:
        if st.button("Buzzer", width="stretch", help="Sound a 2400 Hz tone on GPIO19"):
            if st.session_state.reader and st.session_state.reader.is_connected:
                st.session_state.reader.send_command("z\n")
                st.toast("Buzzer tone sent", icon="🔊")
            else:
                st.toast("Connect the ESP32 first", icon="⚠️")

else:
    st.sidebar.markdown('<div class="side-title">SIMULATION</div>', unsafe_allow_html=True)
    sim_mode = st.sidebar.selectbox(
        "Routine",
        ["Live Playback Loop", "OPEN_PALM", "CLOSED_FIST", "POINTING", "PEACE", "THUMBS_UP", "RESTING", "Manual Sliders"],
        label_visibility="collapsed",
        help="Replay a recorded pose profile, or drive the sensors by hand.",
    )
    sim_noise = st.sidebar.checkbox("Add sensor jitter", value=True, help="Adds Gaussian noise to the simulated channels.")

    manual_packet = None
    if sim_mode == "Manual Sliders":
        st.sidebar.markdown('<div class="side-title">FLEX CHANNELS (ADC)</div>', unsafe_allow_html=True)
        m_thumb = st.sidebar.slider("Thumb · GPIO32", 800, 3600, 3200)
        m_index = st.sidebar.slider("Index · GPIO33", 800, 3600, 3200)
        m_middle = st.sidebar.slider("Middle · GPIO34", 800, 3600, 3200)
        m_ring = st.sidebar.slider("Ring · GPIO35", 800, 3600, 3200)
        m_little = st.sidebar.slider("Little · GPIO36", 800, 3600, 3200)

        st.sidebar.markdown('<div class="side-title">ACCELEROMETER (m/s²)</div>', unsafe_allow_html=True)
        m_ax = st.sidebar.slider("X · side tilt", -10.0, 10.0, 0.0)
        m_ay = st.sidebar.slider("Y · forward tilt", -10.0, 10.0, 0.0)
        m_az = st.sidebar.slider("Z · gravity", -10.0, 10.0, 9.8)

        manual_packet = {
            "timestamp_ms": int(time.time() * 1000) % 10000000,
            "flex": [m_thumb, m_index, m_middle, m_ring, m_little],
            "accel": [m_ax, m_ay, m_az],
            "gyro": [0.0, 0.0, 0.0],
        }

st.sidebar.markdown('<div class="side-title">INFERENCE</div>', unsafe_allow_html=True)
conf_threshold = st.sidebar.slider(
    "Confidence gate",
    0.50,
    0.95,
    0.70,
    0.05,
    help="Readings whose best class falls below this probability are reported as unclassified.",
)
smoothing_window = st.sidebar.slider(
    "Majority window",
    1,
    10,
    5,
    1,
    help="Frames in the rolling vote that settles the reported gesture.",
)

if st.session_state.predictor:
    st.session_state.predictor.confidence_threshold = conf_threshold
    st.session_state.predictor.set_smoothing_window(smoothing_window)

st.sidebar.markdown('<div class="side-title">STREAM</div>', unsafe_allow_html=True)
stream_active = st.sidebar.toggle("Live refresh", value=True, help="Re-runs the console about 12 times a second to follow the glove.")

if st.session_state.predictor:
    st.sidebar.markdown(
        f'<div class="side-note">Model <code>{Path(st.session_state.predictor.model_path).name}</code>'
        f' · {len(st.session_state.predictor.classes)} classes</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# DATA ACQUISITION
# ============================================================
current_packet: Optional[Dict[str, Any]] = None
is_placeholder = False
device_label = "—"

if input_source == SOURCE_SIM:
    device_label = "simulated"
    if sim_mode == "Manual Sliders":
        current_packet = manual_packet
    elif sim_mode == "Live Playback Loop":
        presets = ["OPEN_PALM", "CLOSED_FIST", "POINTING", "PEACE", "THUMBS_UP", "RESTING"]
        if time.time() - st.session_state.sim_last_cycle > 4.5:
            st.session_state.sim_last_cycle = time.time()
            st.session_state.sim_preset_idx = (st.session_state.sim_preset_idx + 1) % len(presets)
        current_packet = generate_simulated_packet(presets[st.session_state.sim_preset_idx], noise=sim_noise)
    else:
        current_packet = generate_simulated_packet(sim_mode, noise=sim_noise)

else:
    reader = st.session_state.reader
    if reader and reader.is_connected:
        device_label = reader.port
        is_valid, packet, _ = reader.read_packet()
        if is_valid and packet:
            st.session_state.last_packet = packet
            current_packet = packet
        elif "last_packet" in st.session_state:
            current_packet = st.session_state.last_packet
        else:
            current_packet = generate_simulated_packet("RESTING", noise=False)
            is_placeholder = True
    else:
        device_label = "no device"
        current_packet = generate_simulated_packet("RESTING", noise=False)
        is_placeholder = True

st.session_state.frames_seen += 1
elapsed_s = max(1e-6, time.time() - st.session_state.session_start)
frame_rate = st.session_state.frames_seen / elapsed_s


# ============================================================
# HEADER
# ============================================================
reader_obj = st.session_state.get("reader")
if input_source == SOURCE_SERIAL:
    if reader_obj and reader_obj.is_connected:
        status_chip = chip(f"Live · {reader_obj.port}", "ok", "dot")
    else:
        status_chip = chip("Not connected", "danger", "dot dot-open")
else:
    status_chip = chip("Simulated feed", "", "dot dot-open")

elapsed_mm, elapsed_ss = divmod(int(time.time() - st.session_state.session_start), 60)

st.markdown(
    '<div class="console-head">'
    '<div>'
    '<div class="eyebrow">Senior design project · Team 2 · measurements are not clinical</div>'
    '<div class="console-title">AI Smart Sign Language Glove</div>'
    '<div class="console-sub">Telemetry console for glove-mounted flex and inertial sensors</div>'
    "</div>"
    '<div class="head-meta">'
    '<div class="meta-row">'
    f'<div><div class="mi-k">source</div><div class="mi-v">{device_label}</div></div>'
    f'<div><div class="mi-k">session</div><div class="mi-v">{elapsed_mm:02d}:{elapsed_ss:02d}</div></div>'
    f'<div><div class="mi-k">updates/s</div><div class="mi-v">{frame_rate:5.1f}</div></div>'
    f'<div><div class="mi-k">gate</div><div class="mi-v">{conf_threshold * 100:4.0f}%</div></div>'
    "</div>"
    f"{status_chip}"
    "</div>"
    "</div>",
    unsafe_allow_html=True,
)

if is_placeholder:
    st.markdown(
        '<div class="notice">No device is connected. The readings below are a placeholder resting pose, '
        "not measured glove data.</div>",
        unsafe_allow_html=True,
    )

# Model must be present before any measurement claim is made
if not st.session_state.predictor:
    reason = st.session_state.get("predictor_error", "The model artifact could not be loaded.")
    st.error(f"No trained model available, so nothing can be classified yet. {reason}")
    st.caption("Run `python backend/train_model.py` to train and save `models/gesture_model.joblib`, then reload this page.")
    st.stop()


# ============================================================
# INFERENCE
# ============================================================
gesture, confidence, prob_dict = st.session_state.predictor.predict(current_packet)
info = GESTURE_INFO.get(gesture, {})
meaning = info.get("meaning", "Unrecognised")
description = info.get("description", "")

# Commit a token once a gesture holds through 12 frames (~1 s at 12 fps) and its
# reported confidence clears the gate, so the log never records a sub-gate reading.
if gesture not in ("UNKNOWN", "RESTING"):
    if gesture == st.session_state.last_stable_gesture:
        st.session_state.gesture_hold_count += 1
        if st.session_state.gesture_hold_count == 12 and confidence >= conf_threshold:
            token = meaning.split("/")[0].strip().upper()
            st.session_state.history_tokens.append(token)
            st.session_state.event_log.append(
                {"t": time.strftime("%H:%M:%S"), "gesture": gesture, "confidence": confidence, "token": token}
            )
            st.session_state.event_log = st.session_state.event_log[-200:]
    else:
        st.session_state.last_stable_gesture = gesture
        st.session_state.gesture_hold_count = 1
else:
    st.session_state.gesture_hold_count = 0

label = CLASS_LABELS.get(gesture, gesture)
if gesture == "UNKNOWN":
    state_chip = chip("Below confidence gate", "warn", "dot dot-half")
elif gesture == "RESTING":
    state_chip = chip("Idle · resting hand", "", "dot dot-open")
elif confidence < conf_threshold:
    # Held by the majority window while this frame's confidence sits under the gate
    state_chip = chip("Sustained · below gate", "warn", "dot dot-half")
else:
    state_chip = chip("Recognised", "ok", "dot")

margin = (confidence - conf_threshold) * 100.0
held = st.session_state.gesture_hold_count


# ============================================================
# RECOGNITION
# ============================================================
st.markdown(
    '<div class="sec"><div class="sec-title">Current recognition</div>'
    f'<div class="sec-meta">window {smoothing_window} frames · gate {conf_threshold * 100:.0f}%</div></div>',
    unsafe_allow_html=True,
)

col_recog, col_probs = st.columns([1.15, 1.0], gap="large")

with col_recog:
    st.markdown(
        '<div class="recog">'
        '<div>'
        f'<div class="recog-value">{label}</div>'
        f'<div class="recog-id">{gesture}</div>'
        f'<div class="recog-gloss">Gloss: <b>{meaning}</b></div>'
        "</div>"
        f"<div>{state_chip}</div>"
        "</div>"
        '<div class="readout">'
        + readout_cell("Confidence", f"{confidence * 100:.1f}", "%")
        + readout_cell("Margin to gate", f"{margin:+.1f}", "pp")
        + readout_cell("Held for", f"{held}", "frames")
        + readout_cell("Best class", f"{max(prob_dict.values()) * 100:.1f}", "%")
        + "</div>"
        f'<div class="readout-note">{description}</div>',
        unsafe_allow_html=True,
    )

with col_probs:
    rows = sorted(prob_dict.items(), key=lambda kv: kv[1])
    values = [p * 100 for _, p in rows]
    best = max(values) if values else 0.0
    fig_probs = go.Figure(
        go.Bar(
            x=values,
            y=[CLASS_LABELS.get(k, k) for k, _ in rows],
            orientation="h",
            marker=dict(color=[T["accent"] if v == best else T["bar_neutral"] for v in values], line=dict(width=0)),
            text=[f"{v:.1f}" for v in values],
            textposition="outside",
            cliponaxis=False,
            textfont=dict(family=T["mono"], size=11, color=T["text_2"]),
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
        )
    )
    fig_probs.add_vline(
        x=conf_threshold * 100,
        line_color=T["warn"],
        line_width=1,
        line_dash="dot",
        annotation_text="gate",
        annotation_position="top",
        annotation_font=dict(family=T["mono"], size=10, color=T["warn"]),
    )
    styled(fig_probs, height=232)
    fig_probs.update_xaxes(
        range=[0, 108],
        dtick=25,
        ticksuffix="%",
        showgrid=True,
        gridcolor=T["line"],
        zeroline=False,
        ticks="",
        tickfont=dict(family=T["mono"], size=10, color=T["text_3"]),
    )
    fig_probs.update_yaxes(showgrid=False, ticks="", tickfont=dict(family=T["sans"], size=12, color=T["text"]))
    fig_probs.update_layout(margin=dict(l=6, r=22, t=22, b=4), bargap=0.5)
    st.plotly_chart(fig_probs, width="stretch", config=CHART_CONFIG)
    st.markdown(
        '<div class="tbl-note">Bars are this frame\'s class probabilities. The reported gesture is the '
        f"majority across the last {smoothing_window} frames, so it can lag the bars during a pose change.</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# FLEX CHANNELS
# ============================================================
st.markdown(
    '<div class="sec"><div class="sec-title">Flex channels</div>'
    '<div class="sec-meta">5 channels · 12-bit ADC · divider 3.3 V / 10 kΩ</div></div>',
    unsafe_allow_html=True,
)

flex_rows: List[str] = []
for i, raw_val in enumerate(current_packet["flex"]):
    bend = raw_to_bend_pct(raw_val)
    state_label, dot_class = bend_state(bend)
    flex_rows.append(
        "<tr>"
        f'<td class="name">{FLEX_SENSOR_NAMES[i]}</td>'
        f'<td class="num">{PIN_LABELS[i]}</td>'
        f'<td class="num r">{raw_val}</td>'
        f'<td class="num r">{adc_to_voltage(raw_val):.2f}</td>'
        f'<td><div class="bendcell"><span class="meter"><i style="width:{bend:.0f}%"></i></span>'
        f'<span class="num">{bend:.0f}%</span></div></td>'
        f'<td><span class="state"><span class="{dot_class}"></span>{state_label}</span></td>'
        "</tr>"
    )

st.markdown(
    '<table class="tbl">'
    "<thead><tr>"
    "<th>Channel</th><th>Pin</th><th class=\"r\">ADC</th><th class=\"r\">Volts</th>"
    "<th class=\"r\">Bend</th><th>State</th>"
    "</tr></thead><tbody>"
    + "".join(flex_rows)
    + "</tbody></table>"
    '<div class="tbl-note">Bend is normalised against the divider calibration (3200 ADC straight, 1100 ADC bent), '
    "so it is comparable across channels on this glove but not across different gloves.</div>",
    unsafe_allow_html=True,
)


# ============================================================
# ORIENTATION AND MOTION
# ============================================================
st.markdown(
    '<div class="sec"><div class="sec-title">Orientation and motion</div>'
    '<div class="sec-meta">MPU6050 · accelerometer and rate gyroscope</div></div>',
    unsafe_allow_html=True,
)

ax, ay, az = current_packet["accel"]
gx, gy, gz = current_packet["gyro"]

eps = 1e-4
pitch = math.atan2(-ax, math.sqrt(ay * ay + az * az + eps)) * 180.0 / math.pi
roll = math.atan2(ay, az + eps) * 180.0 / math.pi
accel_mag = math.sqrt(ax * ax + ay * ay + az * az)

if abs(pitch) < 15 and abs(roll) < 15:
    posture = "Level"
elif pitch > 35:
    posture = "Tilted up"
elif pitch < -35:
    posture = "Tilted down"
elif roll > 35:
    posture = "Rolled right"
elif roll < -35:
    posture = "Rolled left"
else:
    posture = "Angled"

st.markdown(
    '<div class="stats">'
    f'<div class="stat"><div class="k">Pitch</div><div class="v">{pitch:+.1f}<span class="unit"> °</span></div></div>'
    f'<div class="stat"><div class="k">Roll</div><div class="v">{roll:+.1f}<span class="unit"> °</span></div></div>'
    f'<div class="stat"><div class="k">Resultant</div><div class="v">{accel_mag / 9.81:.2f}<span class="unit"> g</span></div></div>'
    f'<div class="stat"><div class="k">Posture (estimated)</div><div class="v">{posture}</div></div>'
    "</div>",
    unsafe_allow_html=True,
)

col_accel, col_gyro = st.columns(2, gap="large")

with col_accel:
    fig_accel = go.Figure(
        go.Bar(
            x=["X", "Y", "Z"],
            y=[ax, ay, az],
            marker=dict(color=T["bar"], line=dict(width=0)),
            text=[f"{v:+.1f}" for v in [ax, ay, az]],
            textposition="outside",
            cliponaxis=False,
            textfont=dict(family=T["mono"], size=10, color=T["text_2"]),
            hovertemplate="%{x}: %{y:.2f} m/s²<extra></extra>",
        )
    )
    styled(fig_accel, height=196)
    axes(fig_accel, y_range=(-15.5, 15.5), y_dtick=5, y_title="m/s²")
    st.plotly_chart(fig_accel, width="stretch", config=CHART_CONFIG)
    st.markdown(
        '<div class="tbl-note">X side tilt · Y forward tilt · Z vertical (gravity at rest ≈ 9.8)</div>',
        unsafe_allow_html=True,
    )

with col_gyro:
    fig_gyro = go.Figure(
        go.Bar(
            x=["X", "Y", "Z"],
            y=[gx, gy, gz],
            marker=dict(color=T["bar"], line=dict(width=0)),
            text=[f"{v:+.0f}" for v in [gx, gy, gz]],
            textposition="outside",
            cliponaxis=False,
            textfont=dict(family=T["mono"], size=10, color=T["text_2"]),
            hovertemplate="%{x}: %{y:.0f} °/s<extra></extra>",
        )
    )
    styled(fig_gyro, height=196)
    axes(fig_gyro, y_range=(-180, 180), y_dtick=60, y_title="°/s")
    st.plotly_chart(fig_gyro, width="stretch", config=CHART_CONFIG)
    st.markdown(
        '<div class="tbl-note">Angular rate about X, Y and Z · fixed ±180 °/s scale for readability</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# SESSION LOG
# ============================================================
st.markdown(
    '<div class="sec"><div class="sec-title">Session log</div>'
    f'<div class="sec-meta">{len(st.session_state.event_log)} committed</div></div>',
    unsafe_allow_html=True,
)

tokens = st.session_state.history_tokens
if tokens:
    shown = tokens[-40:]
    gloss_html = " ".join(shown)
    trunc_note = (
        f'<span class="gloss-label">last {len(shown)} of {len(tokens)}</span>' if len(tokens) > len(shown) else ""
    )
    st.markdown(
        '<div class="gloss-line"><span class="gloss-label">translation</span>'
        f'<span class="gloss-text">{gloss_html}</span>{trunc_note}</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="gloss-line"><span class="gloss-label">translation</span>'
        '<span class="gloss-empty">Nothing committed yet — hold a gesture steady for about a second to add its gloss.</span></div>',
        unsafe_allow_html=True,
    )

log_rows = list(reversed(st.session_state.event_log))[:8]
if log_rows:
    body = "".join(
        "<tr>"
        f'<td class="num">{e["t"]}</td>'
        f'<td class="name">{CLASS_LABELS.get(e["gesture"], e["gesture"])}</td>'
        f'<td class="num r">{e["confidence"] * 100:.1f}%</td>'
        f'<td class="num">{e["token"]}</td>'
        "</tr>"
        for e in log_rows
    )
    st.markdown(
        '<table class="tbl"><thead><tr>'
        '<th>Time</th><th>Gesture</th><th class="r">Confidence</th><th>Gloss committed</th>'
        f"</tr></thead><tbody>{body}</tbody></table>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="log-empty"><div class="t">No gestures committed in this session</div>'
        '<div class="d">A row is added when a non-resting gesture is the majority result for 12 consecutive frames '
        "at the current window and gate. Nothing is broken — the log is simply empty.</div></div>",
        unsafe_allow_html=True,
    )

col_spacer, col_clear = st.columns([4, 1])
with col_clear:
    if st.button("Clear session", width="stretch", disabled=not st.session_state.event_log and not tokens):
        st.session_state.history_tokens = []
        st.session_state.event_log = []
        st.session_state.last_stable_gesture = None
        st.session_state.gesture_hold_count = 0
        st.rerun()


# ============================================================
# MEASUREMENT NOTES
# ============================================================
st.markdown(
    '<div class="sec"><div class="sec-title">Measurement notes</div>'
    '<div class="sec-meta">read before quoting these numbers</div></div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="notes">'
    '<div class="note"><h4>What this shows</h4><ul>'
    "<li>Per-channel flex ADC and the bend fraction implied by this glove's divider calibration.</li>"
    "<li>Class probabilities from the trained classifier, with the gate drawn on the chart.</li>"
    "<li>Accelerometer-derived pitch, roll and resultant, and the rate gyroscope triad.</li>"
    "<li>Which gestures were committed to the translation, with their confidence.</li>"
    "</ul></div>"
    '<div class="note limit"><h4>What it does not show</h4><ul>'
    "<li>Pitch and roll are accelerometer-only approximations; they are not fused with the gyroscope.</li>"
    "<li>Bend percentages are relative to one calibration and drift with glove fit and sensor wear.</li>"
    "<li>Probabilities are model outputs, not calibrated confidence; treat the gate as a filter, not a guarantee.</li>"
    "<li>Six static gestures only: no fingerspelling, motion signs or grammar.</li>"
    "</ul></div></div>",
    unsafe_allow_html=True,
)


# ============================================================
# DIAGNOSTICS
# ============================================================
with st.expander("Diagnostics and raw packet"):
    diag_left, diag_right = st.columns([1, 2], gap="large")
    with diag_left:
        st.markdown(
            f"**Stream**  \n"
            f"Timestamp `{current_packet['timestamp_ms']} ms`  \n"
            f"Source `{input_source}`  \n"
            f"Frames this session `{st.session_state.frames_seen}`  \n"
            f"Average rate `{frame_rate:.1f} Hz`  \n"
            f"Placeholder data `{'yes' if is_placeholder else 'no'}`"
        )
        if input_source == SOURCE_SERIAL and reader_obj:
            st.markdown(
                f"**Device**  \n"
                f"Valid frames `{reader_obj.valid_packets}`  \n"
                f"Device rate `{reader_obj.get_packet_rate():.1f} Hz`"
            )
        st.markdown(
            f"**Model**  \n"
            f"Artifact `{Path(st.session_state.predictor.model_path).name}`  \n"
            f"Classes `{', '.join(st.session_state.predictor.classes)}`  \n"
            f"Gate `{conf_threshold * 100:.0f}%` · window `{smoothing_window}` frames"
        )
    with diag_right:
        st.caption("Raw JSON packet as received")
        st.json(current_packet)


# Continuous refresh keeps the console following the stream
if stream_active:
    time.sleep(0.08)
    st.rerun()
