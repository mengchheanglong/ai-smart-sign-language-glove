# Installation and demo setup

From the project root on macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt platformio
cd firmware
pio run -e esp32dev
```

The build does not require a connected ESP32. **Hardware required:** connect the board using a USB data cable, inspect available ports with `ls /dev/cu.*`, then upload:

```bash
pio run -e esp32dev -t upload --upload-port /dev/cu.usbserial-REPLACE
cd ..
streamlit run dashboard/app.py
```

Replace the port with the actual CH340 device shown on your Mac. Select ESP32 serial in the dashboard and connect. Follow [calibration](CALIBRATION.md), then the collection and training commands in the [README](../README.md). Close/disconnect each serial client before opening another. Firmware upload may reset the device. Hardware remains unverified until tested.
