# 📦 Installation Guide

This guide walks you through setting up everything you need to work on the AI Smart Sign Language Glove project. Follow each step in order.

---

## Prerequisites

Before you begin, make sure you have:

| Tool | Version | Download |
|---|---|---|
| **Python** | 3.10 or newer (recommend 3.11 or 3.12) | [python.org/downloads](https://www.python.org/downloads/) |
| **VS Code** | Latest | [code.visualstudio.com](https://code.visualstudio.com/) |
| **Git** | Latest | [git-scm.com/downloads](https://git-scm.com/downloads/) |

> [!TIP]
> During Python installation on Windows, **check the box "Add Python to PATH"** — this saves a lot of headaches later.

---

## Step 1: Clone or Download the Project

Open a terminal (Command Prompt, PowerShell, or Terminal) and run:

```bash
git clone <your-repo-url>
cd ai-smart-sign-language-glove
```

If you downloaded a ZIP file instead, extract it and open a terminal inside the extracted folder.

---

## Step 2: Install Python Dependencies

We use a **virtual environment** to keep project dependencies isolated from your system Python.

### Create and activate the virtual environment

```bash
# Create the virtual environment (do this once)
python -m venv venv
```

Now **activate** it:

**Windows (Command Prompt):**
```cmd
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

> [!NOTE]
> If PowerShell says "running scripts is disabled", run this first:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

**macOS / Linux:**
```bash
source venv/bin/activate
```

You should see `(venv)` at the beginning of your terminal prompt. This means the virtual environment is active.

### Install the packages

```bash
pip install -r requirements.txt
```

This installs all the Python libraries the project needs (pyserial, scikit-learn, streamlit, etc.).

---

## Step 3: Install PlatformIO

PlatformIO is the tool we use to compile and upload code to the ESP32. You have two options:

### Option A: PlatformIO IDE Extension in VS Code (Recommended for Beginners)

1. Open **VS Code**
2. Click the **Extensions** icon in the sidebar (or press `Ctrl+Shift+X`)
3. Search for **"PlatformIO IDE"**
4. Click **Install**
5. Wait for it to finish installing — this takes a few minutes as it downloads compilers and tools
6. **Restart VS Code** when prompted

After restarting, you should see the PlatformIO home icon (a little alien/house) in the bottom toolbar.

### Option B: PlatformIO Core CLI

If you prefer using the command line:

```bash
pip install platformio
```

Verify the installation:

```bash
pio --version
```

---

## Step 4: Install USB-to-Serial Driver

Your ESP32 board has a USB-to-Serial chip that lets your computer talk to it. You need the correct driver for your specific chip.

### How to identify your chip

Look at the small chip near the USB connector on your ESP32 board:

| Chip Label | Driver | Download Link |
|---|---|---|
| **CP2102** or **CP2104** | Silicon Labs CP210x | [silabs.com/developers/usb-to-uart-bridge-vcp-drivers](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers) |
| **CH340** or **CH340G** | CH340 | [wch-ic.com/downloads/CH341SER_EXE.html](https://www.wch-ic.com/downloads/CH341SER_EXE.html) |
| **FTDI** or **FT232R** | FTDI VCP | [ftdichip.com/drivers/vcp-drivers](https://ftdichip.com/drivers/vcp-drivers/) |

### Platform-specific notes

**Windows:**
- Most drivers auto-install via Windows Update when you plug in the board
- If the board shows as "Unknown Device" in Device Manager, install the driver manually from the links above

**macOS:**
- CP2102 and CH340 drivers usually need to be installed manually
- Download the macOS version from the links above
- You may need to allow the driver in **System Preferences → Security & Privacy**

**Linux:**
- Drivers are usually built into the kernel — it should work out of the box
- However, you may need permission to access the serial port:

```bash
sudo usermod -aG dialout $USER
# Log out and log back in for the change to take effect
```

---

## Step 5: Connect Your ESP32 (CH340 Driver Setup)

Your board is an **ESP32 30-Pin Type-C** powered by the **WCH CH340 USB-to-UART bridge chip**.

### 1. Install the CH340 USB Driver (if needed)

If your computer doesn't automatically recognize the ESP32 when plugged in:

- **Windows:** Download and run the official installer: [WCH CH341SER.EXE Installer](https://www.wch-ic.com/downloads/CH341SER_EXE.html)
  - Run the downloaded file and click **"INSTALL"**.
  - Restart your computer if prompted.
- **macOS:** Download the [CH34xVCP Driver for macOS](https://www.wch-ic.com/downloads/CH341SER_MAC_ZIP.html).
- **Linux:** The CH340 driver is built into the Linux kernel (kernel 2.6.24+). You only need to grant serial dialout permissions:
  ```bash
  sudo usermod -a -G dialout $USER
  ```

### 2. Connect & Identify the COM Port

1. **Connect** your ESP32 to your computer using a **USB Type-C data cable**.
2. **Find the port** it's connected to:

**Windows:**
- Open **Device Manager** (press `Win + X` → Device Manager)
- Expand the **"Ports (COM & LPT)"** section
- Look for **"USB-SERIAL CH340 (COM3)"** (or another COM number like COM4, COM5)
- Note the **COM number**

**macOS:**
```bash
ls /dev/cu.wch*
# or
ls /dev/cu.usb*
```
You should see `/dev/cu.wchusbserial...`.

**Linux:**
```bash
ls /dev/ttyUSB*
```
You should see `/dev/ttyUSB0`.

> [!WARNING]
> **Type-C Cable Alert:** Many USB Type-C cables provided with phone chargers or power banks are **charge-only cables** that lack data wires. If no new COM port appears in Device Manager when plugging in the ESP32, immediately try a known **data-capable USB Type-C cable** (e.g., from an external SSD or smartphone PC transfer cable).

---

## Step 6: Upload First Firmware

Once PlatformIO is installed and your ESP32 is connected:

```bash
cd firmware
```

**Using PlatformIO CLI:**
```bash
pio run --target upload
```

**Using VS Code:**
- Click the **→ (right arrow)** icon in the PlatformIO toolbar at the bottom of VS Code
- Or open the Command Palette (`Ctrl+Shift+P`) and type **"PlatformIO: Upload"**

The first build takes several minutes because PlatformIO downloads the ESP32 toolchain. Subsequent builds are much faster.

> [!TIP]
> If the upload fails, try holding the **BOOT** button on the ESP32 while the upload starts, then release it when you see "Connecting…" in the output.

---

## Step 7: Open Serial Monitor

After uploading, open the Serial Monitor to see the sensor data:

**Using PlatformIO CLI:**
```bash
pio device monitor
```

**Using VS Code:**
- Click the **plug icon** 🔌 in the PlatformIO toolbar at the bottom of VS Code

**Using Arduino IDE:**
- Tools → Serial Monitor
- Set the baud rate to **115200** (bottom-right dropdown)

### What you should see

If everything is working, the Serial Monitor should show sensor readings like:

```
=== AI Sign Language Glove ===
Thumb: 2847
Index: 0
Middle: 0
Ring: 0
Little: 0
```

(Only the Thumb sensor will show real readings in Phase 2 — the others are not connected yet.)

Press `Ctrl+C` to exit the Serial Monitor.

---

## 🔄 Arduino IDE Alternative

If you prefer using the **Arduino IDE** instead of PlatformIO:

### 1. Download and install Arduino IDE
- Get it from [arduino.cc/en/software](https://www.arduino.cc/en/software)

### 2. Add ESP32 board support
1. Open Arduino IDE
2. Go to **File → Preferences**
3. In **"Additional Board Manager URLs"**, paste:
   ```
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```
4. Click **OK**

### 3. Install the ESP32 board package
1. Go to **Tools → Board → Boards Manager**
2. Search for **"esp32"**
3. Install **"esp32 by Espressif Systems"**

### 4. Configure the board
1. Go to **Tools → Board → ESP32 Arduino → ESP32 Dev Module**
2. Go to **Tools → Port** → Select the correct COM port

### 5. Load the firmware
1. Copy the contents of `firmware/src/main.cpp` into a new Arduino sketch
2. Copy `firmware/include/config.h` into the sketch folder (same directory as the `.ino` file)
3. Adjust `#include "config.h"` if the path differs
4. Click the **Upload** button (→ arrow)

---

## ✅ Verifying Everything Works

| Check | Expected Result |
|---|---|
| PlatformIO installed | `pio --version` shows a version number |
| Python packages installed | `pip list` shows pyserial, scikit-learn, streamlit |
| ESP32 connected | COM port appears in Device Manager (or `/dev/ttyUSB*`) |
| Firmware uploaded | "SUCCESS" message in PlatformIO output |
| Serial Monitor works | Sensor readings appear at 115200 baud |

### If something goes wrong

- See **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** for solutions to common problems
- Double-check your USB cable is a **data cable**, not a charge-only cable
- Make sure you selected the correct **COM port**
- Try a different USB port on your computer

---

*Next step: [HARDWARE_WIRING.md](HARDWARE_WIRING.md) — connect the sensors to your ESP32*
