# 🤟 AI Smart Sign Language Glove

![Team 2](https://img.shields.io/badge/Team-2-blue?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-ESP32-green?style=for-the-badge)
![AI](https://img.shields.io/badge/AI-scikit--learn-orange?style=for-the-badge)
![Dashboard](https://img.shields.io/badge/Dashboard-Streamlit-red?style=for-the-badge)

## 📋 Project Description

A wearable glove that detects finger bending and hand movement using **flex sensors** and an **MPU6050 accelerometer/gyroscope**, processes sensor data through an **ESP32 microcontroller**, and uses **machine learning** to recognize predefined gestures and convert them into text or alerts.

> [!IMPORTANT]
> **This is a prototype for custom gesture recognition. It does not claim to translate an entire natural sign language.**

---

## 🏗️ System Architecture

```
┌─────────────┐     USB Serial     ┌─────────────────┐     Prediction     ┌─────────────────┐
│  ESP32 +    │ ─────────────────► │  Python Backend  │ ─────────────────► │  Web Dashboard   │
│  Sensors    │   Raw sensor data  │  + AI Model      │   Gesture labels   │  (Streamlit)     │
│             │                    │  (scikit-learn)   │                    │                  │
│ • 5 Flex    │                    │                   │                    │ • Live readings  │
│ • MPU6050   │                    │ • Read serial     │                    │ • Gesture display│
│ • LED       │                    │ • Preprocess      │                    │ • Charts         │
└─────────────┘                    │ • Classify        │                    │ • Alerts         │
                                   └─────────────────┘                    └─────────────────┘
```

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Firmware** | C++ / Arduino Framework | Reads sensors, sends data over serial |
| **Build System** | PlatformIO | Compile and upload firmware to ESP32 |
| **Backend** | Python 3.10+ | Serial communication, data processing, ML |
| **Machine Learning** | scikit-learn | Train and run gesture classification models |
| **Dashboard** | Streamlit | Real-time web UI for monitoring and display |
| **Hardware** | ESP32 DevKit V1 | Wi-Fi/BLE microcontroller with ADC pins |

---

## 🔩 Hardware Components

| Component | Quantity | Purpose |
|---|---|---|
| ESP32 DevKit V1 (or SparkFun IoT RedBoard) | 1 | Main microcontroller |
| Flex sensors (4.5″) | 5 (+1 spare) | Detect finger bending |
| 10kΩ resistors | 5 | Voltage dividers for flex sensors |
| MPU6050 / GY-521 module | 1 | Accelerometer + gyroscope |
| LED (any color) | 1 | Visual feedback |
| 220Ω resistor | 1 | LED current limiter |
| Breadboard (full-size) | 1 | Prototyping |
| Jumper wires (M-M, M-F) | ~20 | Connections |
| USB data cable (micro-USB) | 1 | Programming and serial data |

> See [docs/HARDWARE_WIRING.md](docs/HARDWARE_WIRING.md) for full wiring instructions.

---

## 🚀 Quick Start

Full installation details are in **[docs/INSTALLATION.md](docs/INSTALLATION.md)**.

1. **Clone the repository** and `cd` into it
2. **Set up Python** — create a virtual environment and install `requirements.txt`
3. **Install PlatformIO** — VS Code extension or CLI
4. **Wire the hardware** — follow [docs/HARDWARE_WIRING.md](docs/HARDWARE_WIRING.md)
5. **Upload firmware** — `pio run --target upload`
6. **Open Serial Monitor** — verify sensor data is streaming
7. **Run the dashboard** — `streamlit run dashboard/app.py`

---

## 📁 Project Structure

```
ai-smart-sign-language-glove/
│
├── README.md                   ← You are here
├── requirements.txt            ← Python dependencies
├── .env.example                ← Environment variables template
├── AGENTS.md                   ← Architecture rules & hardware specs
│
├── firmware/                   ← ESP32 firmware (PlatformIO project)
│   ├── platformio.ini          ← Build configuration (DevKit V1 & RedBoard)
│   ├── src/
│   │   └── main.cpp            ← Multi-sensor stream & LED feedback firmware
│   └── include/
│       └── config.h            ← Pin definitions, rates, and settings
│
├── backend/                    ← Python ML & communication modules
│   ├── __init__.py
│   ├── utils.py                ← Feature extraction, validation & constants
│   ├── serial_reader.py        ← Auto-detect port, JSON streaming, mock mode
│   ├── data_collector.py       ← Interactive gesture dataset recorder
│   ├── generate_sample_data.py ← Realistic synthetic data generator
│   ├── train_model.py          ← Random Forest pipeline (session-based split)
│   └── predictor.py            ← Real-time inference with temporal debouncing
│
├── dashboard/                  ← Streamlit real-time web application
│   └── app.py                  ← Live gauges, IMU charts, simulation mode
│
├── dataset/                    ← Gesture CSV recordings (with sample dataset)
│
├── models/                     ← Saved ML artifacts (gesture_model.joblib)
│
├── tests/                      ← Automated pytest suite (34 unit tests)
│   ├── test_utils.py
│   ├── test_model.py
│   ├── test_predictor.py
│   ├── test_serial_reader.py
│   └── test_data_collector.py
│
└── docs/                       ← Documentation
    ├── INSTALLATION.md         ← Setup guide
    ├── HARDWARE_WIRING.md      ← Wiring diagrams and pin tables
    ├── CALIBRATION.md          ← Sensor calibration procedure
    └── TROUBLESHOOTING.md      ← Common issues and fixes
```

---

## 🏃 Running the System

### 1. Run the Interactive Web Dashboard
The web dashboard supports both **physical ESP32 hardware** and **Interactive Simulation Mode** (with preset gestures and manual finger sliders):
```bash
streamlit run dashboard/app.py
```

### 2. Test Real-Time Inference in Terminal
Stream predictions from physical glove or simulated ESP32:
```bash
# Physical ESP32 (auto-detects port)
python backend/predictor.py

# Without hardware (Mock simulation mode)
python backend/predictor.py --mock
```

### 3. Record New Gesture Training Sessions
```bash
# Interactive recording menu (with countdown & progress bar)
python backend/data_collector.py

# Record with mock simulation mode
python backend/data_collector.py --mock --gesture OPEN_PALM --samples 100
```

### 4. Train or Retrain the AI Model
```bash
# Trains Random Forest with session-based split (prevents data leakage)
python backend/train_model.py
```

### 5. Run the Automated Test Suite
```bash
python -m pytest tests/ -v
```

---

## 📅 Development Phases

| # | Phase | Status | Details |
|---|---|---|---|
| 1 | Project Setup | ✅ Done | Repo structure, requirements.txt, .env.example, hardware docs |
| 2 | Read Single Flex Sensor | ✅ Done | ADC1 analogRead, voltage conversion, stuck/error detection |
| 3 | Read 5 Flex Sensors | ✅ Done | 5-channel sampling (GPIO 32-36), moving average filter |
| 4 | MPU6050 IMU Integration | ✅ Done | I2C (SDA=21, SCL=22), addresses 0x68/0x69, disconnect fallback |
| 5 | Combined Sensor Data | ✅ Done | Standard JSON streaming format at 25-50 Hz (default 25 Hz) |
| 6 | Python Serial Communication | ✅ Done | Auto-detect port, packet validation, CSV logging, mock mode |
| 7 | Gesture Dataset Collection | ✅ Done | Labeled session recorder (OPEN_PALM, CLOSED_FIST, POINTING, PEACE, THUMBS_UP, RESTING) |
| 8 | Machine Learning Pipeline | ✅ Done | Random Forest classifier, session-based split (no leakage), joblib artifact |
| 9 | Real-Time Prediction Engine | ✅ Done | Confidence thresholding with UNKNOWN fallback, temporal debounce smoothing |
| 10 | Streamlit Dashboard | ✅ Done | Live bend gauges, IMU visualizer, interactive simulation mode |
| 11 | Glove LED Feedback | ✅ Done | GPIO18 feedback indicator triggered on gesture recognition over serial |
| 12 | Automated Tests & Offline Data | ✅ Done | 34 automated pytest unit tests, synthetic data generator |


---

## 👥 Team

**Team 2** — AI Smart Sign Language Glove

<!-- Add team member names here -->
<!-- | Name | Role | -->
<!-- |---|---| -->

---

## 📄 License

<!-- Choose a license for your project -->
<!-- Recommended: MIT License for educational projects -->

This project is for educational purposes.

---

*Built with ❤️ by Team 2*
