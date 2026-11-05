# AI Smart Sign Language Glove

A five-sensor ESP32 glove and MPU6050 stream measurements to a Python gesture classifier and Streamlit dashboard. It recognizes only custom gestures represented in its training data; it is not a complete sign-language translator. Physical wiring, calibration, buzzer, and recognition accuracy require testing with your glove.

**Current hardware configuration:** four flex sensors are enabled on GPIO32–35; GPIO36 is disabled. The physical finger-to-pin mapping is not yet confirmed. The GY-87 and buzzer are not currently connected. The dashboard labels sensors by pin. Existing datasets and models use historical finger-named columns; collect fresh data for this wiring once the IMU is connected.

## Mac quick start

```bash
cd /Users/macbookpro/Documents/ai-smart-sign-language-glove
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt platformio
cd firmware
pio run -e esp32dev
cd ..
streamlit run dashboard/app.py
```

Choose **Simulated feed** to explore without the device; simulated values and models trained on synthetic data do not establish hardware performance. To use the real glove, follow [installation](docs/INSTALLATION.md), [wiring](docs/HARDWARE_WIRING.md), and [calibration](docs/CALIBRATION.md). Only one program can use the USB serial port at a time. Close the Arduino/PlatformIO monitor or disconnect the dashboard before collecting data.

## Collect, train, and demo

After wiring, upload, and successful calibration with all five fingers and the IMU available, disconnect the dashboard. Record several examples per class in separate sessions; reposition the glove between sessions. For example, for each of `OPEN_PALM`, `CLOSED_FIST`, and `POINTING`, repeat the following with sessions `S01`, `S02`, and `S03` (replace the gesture and session):

```bash
python backend/data_collector.py --port /dev/cu.usbserial-REPLACE --gesture OPEN_PALM --participant P01 --session S01 --samples 150
python backend/train_model.py --split-by session --test-session S03
streamlit run dashboard/app.py
```

Select ESP32 serial and connect. Check sensor status and hold a trained gesture steady. The buzzer sounds once when a stable recognition is committed. Model probabilities are not a guarantee of correctness. Recollect data if glove fit or calibration changes; the current model uses raw ADC values as features. Held-out session performance is still only an estimate and requires real-world validation.

See [troubleshooting](docs/TROUBLESHOOTING.md) and the test suite: `python -m pytest -q`.

## Serial protocol

Application telemetry is one JSON object per line at 115200 baud, approximately 10 Hz. `flex` contains five filtered raw ADC values; `calibrated`, `straight`, `bent`, `bend_pct` (null until calibrated), and `bend_state` use thumb-to-little order. `capture`, `capture_count`, and `straight_ready` report calibration progress. `imu_valid` is false and `accel`/`gyro` are null when unavailable; otherwise units are m/s² and degrees/s. USB boot messages may precede application telemetry and must be ignored. Send newline-terminated `straight`, `bent`, `clear`, or `buzzer` commands. Never run two serial clients concurrently.
