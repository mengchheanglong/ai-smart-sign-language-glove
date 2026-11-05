# AGENTS.md — ESP32 Gesture Recognition Glove

## Project Overview
Wearable glove with flex sensors + MPU6050 → ESP32 → Python ML backend → Streamlit dashboard.

## Directory Structure
- `firmware/` — ESP32 PlatformIO project (C++, Arduino framework)
- `backend/` — Python modules (serial reader, data collector, ML pipeline, predictor)
- `dashboard/` — Streamlit web dashboard
- `dataset/` — CSV gesture recordings (gitignored, except .gitkeep)
- `models/` — Saved ML model artifacts (gitignored, except .gitkeep)
- `tests/` — Python unit tests
- `docs/` — Project documentation

## Coding Conventions
- ESP32 firmware: C++ with Arduino framework, PlatformIO build system
- Python: Python 3.10+, use virtual environment, follow PEP 8
- Hardware config: All pin assignments in `firmware/include/config.h`
- Serial protocol: JSON-per-line at 115200 baud
- Data format: CSV with headers for dataset files

## Key Configuration Files
- `firmware/platformio.ini` — PlatformIO build configuration
- `firmware/include/config.h` — Hardware pin assignments and constants
- `.env` — Local environment settings (serial port, paths)
- `requirements.txt` — Python dependencies

## Important Notes
- Core hardware: ESP32 30Pin Type-C (CH340), GY-87 10DOF Module (MPU6050 @ 0x68), Passive Buzzer Module on GPIO19
- ADC1 pins only for analog reads (GPIO32-36); on 30-pin board GPIO36 is silkscreened as VP
- Flex sensor voltage divider: 3.3V → Flex → ADC_Pin → 10kΩ → GND
- GY-87 MPU6050 on I2C: SDA=GPIO21, SCL=GPIO22 (primary address 0x68)
- Passive Buzzer Module on GPIO19: driven with PWM audio tones (e.g. 2000 Hz) via tone()
