# 🔧 Troubleshooting Guide

Having problems? This guide covers the most common issues and their solutions. Find your symptom below and follow the steps.

---

## ESP32 Upload Failures

### "Failed to connect to ESP32" or "Timed out waiting for packet header"

This is the most common issue. Try these solutions **in order**:

1. **Hold the BOOT button** on the ESP32 while the upload starts. Release it when you see "Connecting…" or the upload progress begins.

2. **Try a different USB cable.** Many cables (especially those that come with phone chargers) are **charge-only** and don't carry data. You need a **data cable**. This is the #1 cause of connection issues.

3. **Check the COM port.** Make sure the correct port is selected:
   - PlatformIO usually auto-detects, but you can specify it in `platformio.ini`:
     ```ini
     upload_port = COM3  ; Windows
     ; upload_port = /dev/ttyUSB0  ; Linux
     ```

4. **Install or update the USB driver.** See the driver table in [INSTALLATION.md](INSTALLATION.md#step-4-install-usb-to-serial-driver).

5. **Reduce the upload speed.** Add this to `platformio.ini`:
   ```ini
   upload_speed = 115200
   ```

6. **Linux: Check permissions.**
   ```bash
   ls -la /dev/ttyUSB0
   ```
   If you don't have access:
   ```bash
   sudo usermod -aG dialout $USER
   # Log out and log back in
   ```

7. **Try a different USB port** on your computer. Front panel USB ports can sometimes be unreliable.

---

## Serial Monitor Shows Garbage Characters

### Random symbols like `⸮⸮⸮⸮` instead of readable text

1. **Check the baud rate.** It must be set to **115200** — this must match what the firmware uses in `Serial.begin(115200)`. This is the most common cause of garbage output.

2. **Close other programs** that might be using the same COM port. Only one program can use a serial port at a time.

3. **Reset the ESP32.** Press the **EN** (or **RST**) button on the board.

4. **Check the firmware** uploaded correctly. Try re-uploading.

---

## Serial Port Not Found

### No COM port appears when ESP32 is connected

1. **Try a different USB cable.** The cable **MUST** be a data cable (not charge-only). This is the most common cause.

2. **Try a different USB port.** Use a port directly on the computer, not a USB hub.

3. **Install the USB-to-Serial driver** for your specific chip:
   - CP2102: [Silicon Labs driver](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)
   - CH340: [WCH driver](https://www.wch-ic.com/downloads/CH341SER_EXE.html)
   - FTDI: [FTDI driver](https://ftdichip.com/drivers/vcp-drivers/)

4. **Platform-specific checks:**

   **Windows:** Open **Device Manager** → look under **"Other Devices"** for any device with a ⚠️ yellow warning icon. Right-click → Update Driver.

   **macOS:** Open **System Information** → **USB** → look for your device. If it appears here but not as a serial port, the driver isn't installed.

   **Linux:** Run this after plugging in the board:
   ```bash
   dmesg | tail
   ```
   This shows the most recent system messages — you should see the ESP32 being detected.

---

## Flex Sensor Issues

### Reading Stuck at 0

The sensor is reading zero voltage. **Possible causes:**

1. **Sensor not connected to 3.3V** — check that one lead of the flex sensor connects to the 3.3V power rail
2. **Wrong GPIO pin** — double-check you're reading from the correct pin (e.g., GPIO32 for thumb)
3. **Short circuit** — a wire might be bridging two rows that shouldn't be connected

**Diagnosis:** Use a multimeter to check voltage at the ADC pin. It should be between 0V and 3.3V when the circuit is correct.

---

### Reading Stuck at 4095

The sensor is reading maximum voltage (3.3V). **Possible causes:**

1. **Resistor missing** — the 10kΩ pull-down resistor isn't connected or isn't making contact
2. **Resistor not connected to GND** — check the resistor goes to the GND rail
3. **Wrong GPIO pin** — some pins might have internal pull-ups

**Diagnosis:** Make sure the voltage divider is complete: 3.3V → flex sensor → junction point (→ GPIO) → 10kΩ resistor → GND.

---

### Reading Doesn't Change When Bending

The reading stays the same no matter how you bend the sensor. **Possible causes:**

1. **Wrong bending direction** — most flex sensors only respond to bending **one way**. Try bending in the opposite direction.
2. **Resistor value too high or too low** — if the fixed resistor is too far from the sensor's resistance range, the voltage change will be tiny. 10kΩ should work well with most flex sensors.
3. **Bad breadboard contact** — push the components firmly into the breadboard. Old breadboards can have loose contacts.
4. **Damaged sensor** — flex sensors can break internally if bent at the base. Try the spare sensor.

**Diagnosis:** Check the raw ADC readings. Even a small change (e.g., 50 counts) means the sensor is working — you just need calibration.

---

## MPU6050 Issues (Phase 4+)

### "MPU6050 connection failed" message

1. **Check SDA and SCL wiring:**
   - SDA → **GPIO21**
   - SCL → **GPIO22**
   - Make sure they're not swapped

2. **Check power:**
   - VCC → **3.3V** (not 5V, unless your GY-521 module has a voltage regulator)
   - GND → **GND**

3. **Check the AD0 pin:**
   - AD0 → **GND** for I²C address **0x68**
   - AD0 → **3.3V** for I²C address **0x69**
   - If AD0 is left floating, the address may be unreliable

4. **Try the other address.** Change the address in `config.h`:
   ```cpp
   #define MPU6050_ADDR 0x69  // try this if 0x68 doesn't work
   ```

5. **Run an I²C scanner** to find the device. Create a simple sketch:
   ```cpp
   #include <Wire.h>

   void setup() {
     Serial.begin(115200);
     Wire.begin();
     Serial.println("I2C Scanner");

     for (byte addr = 1; addr < 127; addr++) {
       Wire.beginTransmission(addr);
       if (Wire.endTransmission() == 0) {
         Serial.print("Found device at 0x");
         Serial.println(addr, HEX);
       }
     }
     Serial.println("Scan complete");
   }

   void loop() {}
   ```

---

## Python Issues

### "ModuleNotFoundError: No module named 'serial'"

1. **Activate the virtual environment first:**

   **Windows:**
   ```cmd
   venv\Scripts\activate
   ```
   **macOS/Linux:**
   ```bash
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Important:** The correct package is `pyserial`, **NOT** `serial`. If you accidentally installed `serial`, remove it and install the right one:
   ```bash
   pip uninstall serial
   pip install pyserial
   ```

---

### Dashboard Won't Start

**Streamlit errors or blank page:**

1. **Check virtual environment is activated** — you should see `(venv)` in your terminal prompt

2. **Install/update dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Port conflict:** If port 8501 is already in use, try a different port:
   ```bash
   streamlit run dashboard/app.py --server.port 8502
   ```

4. **Check terminal output** for error messages — they usually tell you exactly what's wrong

5. **Try opening manually** — if the browser doesn't open automatically, go to `http://localhost:8501` in your browser

---

### Code Changes Not Appearing in the Dashboard

**`AttributeError: 'GesturePredictor' object has no attribute ...` after editing `backend/`:**

Streamlit re-runs `dashboard/app.py` on every interaction, but modules it has already imported
(`backend/predictor.py`, `backend/utils.py`) stay cached in the running server's memory. Editing a backend
module while the dashboard is running can pair the new UI code with an old backend class — the page then
raises `AttributeError` on a method that does exist on disk.

Confirm the method is in the file, then restart the dashboard (Ctrl+C in its terminal, then start it again):

```bash
streamlit run dashboard/app.py
```

Hot reload is reliable for `dashboard/app.py` itself; restart the server after changing anything under `backend/`.

---

### Model File Not Found

**"FileNotFoundError: model.joblib"**

1. **Train the model first.** The model file is created during Phase 8 (Model Training). You need to:
   - Collect training data (Phase 7-8)
   - Run the training script: `python python/train_model.py`

2. **Check the models/ directory:**
   ```bash
   ls models/       # macOS/Linux
   dir models\      # Windows
   ```
   There should be a `model.joblib` file.

3. **Check the file path** in your config matches where the model was actually saved.

---

## GY-87 10DOF & MPU6050 Issues

### I2C Scanner shows multiple devices (e.g. 0x68, 0x1E, 0x77)
**This is completely normal!** The GY-87 board is a 10DOF module that contains:
- `0x68`: MPU6050 (3-axis Accel + 3-axis Gyro) — this is what our firmware uses!
- `0x1E`: HMC5883L (Magnetometer / Compass)
- `0x77`: BMP180 (Barometer & Temperature)

Our firmware targets `0x68` directly. The presence of the other two chips does not interfere with gesture tracking.

### "MPU6050 init failed" with GY-87
1. Ensure **VCC_IN** connects to **3.3V** (do NOT leave VCC_IN disconnected).
2. Ensure the pin marked **3.3V** on the GY-87 is left **unconnected** (it is an output from the onboard regulator, not a power input).
3. Ensure SDA connects to `GPIO21` (`D21`) and SCL connects to `GPIO22` (`D22`).
4. Ensure GND connects to ESP32 `GND`.

---

## Passive Buzzer Module Issues

### Buzzer only makes a tiny "click" or is silent
1. **Passive buzzers require a frequency tone:** A passive buzzer does not beep when sent a continuous `HIGH` DC voltage. Our firmware uses `tone(BUZZER_PIN, 2000, 80)` to produce audio waves.
2. **Check module pinout:**
   - `+` or `VCC` → ESP32 `3.3V` (or `VIN`)
   - `-` or `GND` → ESP32 `GND`
   - `S` or `I/O` → ESP32 `GPIO19` (`D19`)
3. **Test command:** Open the Serial Monitor at 115200 baud and type `z` + Enter. The ESP32 will output a manual 2400 Hz test beep and print `[BUZZER] Tested passive buzzer tone`.

---

## ESP32 30-Pin Board: Cannot find Pin 36

### Where is Pin 36 on the 30-Pin board?
On standard 30-pin ESP32 DevKit boards, **GPIO36 is silkscreened as `VP`** (next to pin `EN`).
In code and configuration:
- `GPIO36` == `VP` (Pin 2 on the left header).
Connect your Little finger flex sensor voltage divider output to pin `VP`!

---

## General Tips

### "I followed all the steps but it still doesn't work"

1. **Start simple.** Disconnect everything and test with just the ESP32 (no sensors). Upload a basic "Hello World" sketch that just prints to Serial.

2. **Add one component at a time.** Wire up one sensor, test it, then add the next.

3. **Read the error message carefully.** Most error messages tell you exactly what's wrong — read the whole message, not just the first line.

4. **Check the basics:**
   - Is the USB cable a data cable? (Try transferring a file to your phone with it)
   - Is the virtual environment activated? (Look for `(venv)` in the prompt)
   - Is the correct COM port selected?
   - Is the baud rate set to 115200?

5. **Ask for help.** Share the **complete error message** and a **photo of your wiring** — this makes it much easier for others to help you.

---

## Quick Reference: Common Fixes

| Problem | Most likely fix |
|---|---|
| Can't upload to ESP32 | Hold BOOT button during upload |
| No COM port | Try a different USB cable (data cable!) |
| Garbage in Serial Monitor | Set baud rate to 115200 |
| Sensor reads 0 | Check 3.3V connection |
| Sensor reads 4095 | Check GND resistor |
| Sensor doesn't change | Bend the other way |
| Python import error | Activate venv, then `pip install -r requirements.txt` |
| MPU6050 not found | Check SDA→GPIO21, SCL→GPIO22 |

---

*Still stuck? Check [HARDWARE_WIRING.md](HARDWARE_WIRING.md) to verify your wiring, or ask your team for help.*
