# 🔌 Hardware Wiring Guide

This guide explains how to connect all the electronic components to your ESP32. Follow the diagrams carefully — **incorrect wiring can damage your components**.

> [!CAUTION]
> Always disconnect the USB cable before changing wiring. Never connect or disconnect components while the board is powered on.

---

## 🧰 Components Needed

| Component | Quantity | Purpose |
|---|---|---|
| ESP32 30-Pin DevKit V1 Type-C (CH340) | 1 | Main microcontroller with USB-C |
| Flex sensor (2.2″ or 4.5″) | 5 (+1 spare) | Detect finger bending |
| 10kΩ resistor | 5 | Voltage dividers for flex sensors |
| GY-87 10DOF Module (with MPU6050) | 1 | Hand orientation (accel + gyro at I2C 0x68) |
| LED (any color) | 1 | Visual recognition feedback |
| 220Ω resistor | 1 | LED current limiter |
| Passive Buzzer Board Module (3-pin) | 1 | Audible recognition beep (PWM driven) |
| Breadboard (full-size) | 1 | Prototyping connections |
| Jumper wires (M-M, M-F) | ~20 | Connections |
| USB Type-C data cable | 1 | Programming and power (must support DATA) |

---

## 📌 ESP32 30-Pin Type-C DevKit V1 Pinout

Your **30-pin ESP32** has 15 pins on the left and 15 pins on the right. 

> [!IMPORTANT]
> **Where is Pin 36?** On almost all 30-pin ESP32 boards, **GPIO36 is labeled `VP`** (Sensor VP). In code and configuration, GPIO36 and `VP` are the exact same physical pin!

```
                    ┌────────────────────────┐
                    │      [TYPE-C USB]      │
                    │      CH340 BRIDGE      │
              EN ───┤ 1                   30 ├─── D23 (GPIO23)
 (GPIO36) **VP** ───┤ 2 (Little Flex)     29 ├─── D22 (GPIO22 - I2C SCL)
 (GPIO39)     VN ───┤ 3                   28 ├─── TX0 (GPIO1)
 (GPIO34)    D34 ───┤ 4 (Middle Flex)     27 ├─── RX0 (GPIO3)
 (GPIO35)    D35 ───┤ 5 (Ring Flex)       26 ├─── D21 (GPIO21 - I2C SDA)
 (GPIO32)    D32 ───┤ 6 (Thumb Flex)      25 ├─── D19 (GPIO19 - Buzzer SIG)
 (GPIO33)    D33 ───┤ 7 (Index Flex)      24 ├─── D18 (GPIO18 - LED Anode)
             D25 ───┤ 8                   23 ├─── D5  (GPIO5)
             D26 ───┤ 9                   22 ├─── TX2 (GPIO17)
             D27 ───┤ 10                  21 ├─── RX2 (GPIO16)
             D14 ───┤ 11                  20 ├─── D4  (GPIO4)
             D12 ───┤ 12                  19 ├─── D2  (GPIO2)
             D13 ───┤ 13                  18 ├─── D15 (GPIO15)
             GND ───┤ 14 (Ground Rail)    17 ├─── GND (Ground Rail)
         VIN(5V) ───┤ 15                  16 ├─── 3V3 (3.3V Power Rail)
                    └────────────────────────┘
```

---

## 📌 Pin Assignment Table

| Component | ESP32 Pin Label | GPIO Number | Function / Notes |
|---|---|---|---|
| Thumb flex sensor | `D32` | GPIO32 | ADC1_CH4 voltage divider |
| Index flex sensor | `D33` | GPIO33 | ADC1_CH5 voltage divider |
| Middle flex sensor | `D34` | GPIO34 | ADC1_CH6 (input-only pin) |
| Ring flex sensor | `D35` | GPIO35 | ADC1_CH7 (input-only pin) |
| Little flex sensor | `VP` | GPIO36 | ADC1_CH0 (input-only, labeled `VP`) |
| GY-87 / MPU6050 SDA | `D21` | GPIO21 | I²C Data Line |
| GY-87 / MPU6050 SCL | `D22` | GPIO22 | I²C Clock Line |
| Status LED (+) | `D18` | GPIO18 | Through 220Ω series resistor |
| Passive Buzzer (SIG) | `D19` | GPIO19 | PWM Tone frequency (e.g. 2000 Hz) |
| Power Rail (+) | `3V3` | 3.3V | Supplies flex sensors & GY-87 |
| Ground Rail (−) | `GND` | GND | Common circuit ground |

> [!IMPORTANT]
> All 5 flex sensors use **ADC1** pins exclusively. ADC2 pins (GPIO0, 2, 4, 12, 13, 14, 15, 25, 26, 27) cannot be sampled when ESP32 Wi-Fi is active.

---

## ⚡ Flex Sensor Voltage Divider Circuit

Each flex sensor needs a **voltage divider** circuit to convert its changing resistance into a voltage the ESP32 can read.

### Circuit diagram (one sensor)

```
    3.3V (from ESP32)
     │
     │
    ┌┴┐
    │ │  Flex Sensor
    │ │  (variable resistance: ~25kΩ straight, ~100kΩ bent)
    └┬┘
     │
     ├──────────────► ESP32 GPIO pin (ADC input)
     │                (this is where we read the voltage)
     │
    ┌┴┐
    │ │  10kΩ Fixed Resistor
    │ │
    └┬┘
     │
     │
    GND (from ESP32)
```

### How the voltage divider works (simple explanation)

Think of the flex sensor and the 10kΩ resistor as two parts of a seesaw:

1. The **flex sensor** and the **10kΩ resistor** are connected in series between 3.3V and GND
2. The ESP32 reads the voltage at the **middle point** (between the two components)
3. When the finger is **straight**: the flex sensor has **lower resistance** (~25kΩ) → more voltage reaches the middle → **higher ADC reading** (around 2000–3500)
4. When the finger is **bent**: the flex sensor has **higher resistance** (~100kΩ) → less voltage reaches the middle → **lower ADC reading** (around 500–1500)

**In short:** Straight finger = higher reading, Bent finger = lower reading

> [!NOTE]
> The exact numbers depend on your specific sensor and resistor. That's why we calibrate — see [CALIBRATION.md](CALIBRATION.md).

---

## 🟢 Phase 2 Wiring: Single Flex Sensor (Thumb)

Start with just one sensor to make sure everything works before wiring all five.

### Step-by-step instructions

1. **Power rails:** Connect the ESP32 **3.3V** pin to the breadboard's **red (+) power rail**
2. **Ground rail:** Connect the ESP32 **GND** pin to the breadboard's **blue (−) ground rail**
3. **Flex sensor lead 1:** Insert one lead of the flex sensor into the **red (+) power rail** (3.3V)
4. **Flex sensor lead 2:** Insert the other lead into an **empty breadboard row** (e.g., row 10)
5. **Signal wire:** From that **same row** (row 10), run a jumper wire to **ESP32 GPIO32**
6. **Pull-down resistor:** From that **same row** (row 10), connect a **10kΩ resistor** to the **blue (−) ground rail**
7. **USB cable:** Connect the ESP32 to your computer with the USB data cable

### Breadboard layout (top view)

```
    Power Rail (+)  ─────────────────────────────────  3.3V from ESP32
    │
    │ row 10:  [Flex Sensor lead]──[junction]──[10kΩ to GND]
    │                                  │
    │                                  └── jumper wire to GPIO32
    │
    Ground Rail (−) ─────────────────────────────────  GND from ESP32
```

### Verify it works

1. Upload the firmware
2. Open the Serial Monitor (115200 baud)
3. You should see the Thumb reading change when you bend the flex sensor
4. Straight ≈ 2000–3500 | Bent ≈ 500–1500

---

## 🖐️ Full Wiring: All Five Flex Sensors (Phase 5)

Repeat the same voltage divider circuit for each finger:

| Finger | Flex Sensor → | ESP32 Pin | 10kΩ Resistor → |
|---|---|---|---|
| Thumb | 3.3V rail → sensor → row A | GPIO32 | Row A → GND rail |
| Index | 3.3V rail → sensor → row B | GPIO33 | Row B → GND rail |
| Middle | 3.3V rail → sensor → row C | GPIO34 | Row C → GND rail |
| Ring | 3.3V rail → sensor → row D | GPIO35 | Row D → GND rail |
| Little | 3.3V rail → sensor → row E | GPIO36 (SVP) | Row E → GND rail |

Each sensor has the **same circuit** — only the GPIO pin changes.

> [!TIP]
> Use different colored jumper wires for each finger to keep track of which sensor connects where. For example: red = thumb, orange = index, yellow = middle, green = ring, blue = little.

---

## 🔄 GY-87 10DOF Module Wiring (with MPU6050)

Your project uses the **GY-87 10DOF Flight Control Module**. 

### What is on the GY-87?
The GY-87 board is a high-precision multi-sensor module that packs:
1. **InvenSense MPU6050** — 3-axis accelerometer + 3-axis gyroscope at I²C address `0x68` (this is our primary orientation sensor!)
2. **HMC5883L / QMC5883L** — 3-axis digital compass / magnetometer at I²C address `0x1E`
3. **BMP180** — Barometric pressure and temperature sensor at I²C address `0x77`
4. **On-board 3.3V LDO Voltage Regulator & Logic Converter**

> [!NOTE]
> The MPU6050 on the GY-87 is 100% compatible with standard MPU6050 software. It answers directly at `0x68`. The firmware queries the MPU6050 registers seamlessly without needing any changes.

### GY-87 Pinout & Connections

| GY-87 Pin | Connect to ESP32 Pin | Purpose / Notes |
|---|---|---|
| **VCC_IN** (or VCC) | **3.3V** | Power supply (Connect to 3.3V rail) |
| **GND** | **GND** | Common ground (Connect to GND rail) |
| **SCL** | **GPIO22** (`D22`) | I²C Clock Line |
| **SDA** | **GPIO21** (`D21`) | I²C Data Line |
| **3.3V** | *Do NOT connect* | Regulated 3.3V output (leave empty) |
| **FSYNC** | *Do NOT connect* | Frame synchronization (camera sync, not needed) |
| **INTA** | *Do NOT connect* | MPU6050 interrupt (we use 25 Hz polling) |
| **DRDY** | *Do NOT connect* | Compass data ready (not needed) |

### Wiring Diagram

```
    GY-87 10DOF Module                    ESP32 30-Pin DevKit
    ┌──────────────────┐                 ┌────────────────────┐
    │ VCC_IN ──────────┼─────────────────┤ 3V3 (3.3V)         │
    │ GND    ──────────┼─────────────────┤ GND                │
    │ SCL    ──────────┼─────────────────┤ D22 (GPIO22)       │
    │ SDA    ──────────┼─────────────────┤ D21 (GPIO21)       │
    │ 3.3V   (leave NC)│                 │                    │
    │ FSYNC  (leave NC)│                 │                    │
    │ INTA   (leave NC)│                 │                    │
    │ DRDY   (leave NC)│                 │                    │
    └──────────────────┘                 └────────────────────┘
```

---

## 💡 LED Wiring (Phase 11)

The LED provides visual feedback when a gesture is recognized.

```
ESP32 GPIO18 (D18) ──► 220Ω Resistor ──► LED Anode (+, longer leg) ──► LED Cathode (−, shorter leg) ──► GND
```

### Step-by-step

1. Connect a **220Ω resistor** from **GPIO18** (`D18`) to an empty breadboard row
2. Insert the **LED anode** (longer leg, +) into that same row
3. Insert the **LED cathode** (shorter leg, −) into the **GND rail**

---

## 🔊 Passive Buzzer Board Module Wiring

Your kit features a **Passive Buzzer Board Module** (3-pin module with an onboard transistor driver).

### Active vs. Passive Buzzer: Why It Matters
- **Active buzzer:** Contains an internal oscillating crystal. When given simple DC voltage (`HIGH`), it beeps continuously.
- **Passive buzzer:** Has **no internal oscillator**. Applying static DC voltage (`HIGH`) only makes a single faint "click". To produce sound, it requires an **audio AC / PWM frequency** (e.g., 2,000 Hz tone).
- **The Module Advantage:** Raw buzzers draw 30–50 mA (too much for an ESP32 pin). Your buzzer is mounted on a PCB with an onboard transistor (like S8550/S8050) and a base resistor. This means it **safely draws power from 3.3V**, while the ESP32 pin only supplies a tiny control signal.

### Pinout & Connections

| Buzzer Module Pin | ESP32 Pin | Purpose / Wire Color |
|---|---|---|
| **VCC** (or `+`) | **3.3V** (or VIN) | Power rail |
| **GND** (or `-`) | **GND** | Ground rail |
| **I/O** (or `S` / Signal) | **GPIO19** (`D19`) | Audio PWM tone output |

```
    Passive Buzzer Module                 ESP32 30-Pin DevKit
    ┌──────────────────┐                 ┌────────────────────┐
    │ VCC (+) ─────────┼─────────────────┤ 3V3 (3.3V)         │
    │ GND (-) ─────────┼─────────────────┤ GND                │
    │ I/O (S) ─────────┼─────────────────┤ D19 (GPIO19)       │
    └──────────────────┘                 └────────────────────┘
```

> [!TIP]
> The firmware uses the non-blocking `tone(BUZZER_PIN, 2000, 80)` function to play a crisp 2000 Hz beep for 80 ms whenever a gesture is recognized with high confidence! You can also type `'z'` in the Serial Monitor to test the beep anytime.

---

## 🔄 Switching to SparkFun IoT RedBoard

If your team is using the **SparkFun ESP32 IoT RedBoard** instead of the generic DevKit V1:

1. **Pin numbers are the same in software** — GPIO32, GPIO33, etc. work identically
2. **Physical pin layout differs** — check the [SparkFun pinout diagram](https://learn.sparkfun.com/tutorials/esp32-thing-plus-hookup-guide) for where each pin is located on the board
3. **PlatformIO config:** In `platformio.ini`, uncomment the `sparkfun_redboard` environment and comment out `esp32dev`:
   ```ini
   ; [env:esp32dev]
   ; board = esp32dev

   [env:sparkfun_redboard]
   board = sparkfun_esp32_iot_redboard
   ```
4. **Firmware config:** In `config.h`, define `USE_SPARKFUN_BOARD` before including config, or add it to build flags:
   ```ini
   build_flags = -DUSE_SPARKFUN_BOARD
   ```
5. **USB driver:** The SparkFun board uses an **FTDI chip** — you may need the [FTDI driver](https://ftdichip.com/drivers/vcp-drivers/) instead of CP2102

---

## 📋 Complete Wiring Checklist

Use this checklist to verify all connections:

- [ ] ESP32 3.3V → Breadboard power rail (+)
- [ ] ESP32 GND → Breadboard ground rail (−)
- [ ] Thumb flex sensor → voltage divider → GPIO32
- [ ] Index flex sensor → voltage divider → GPIO33
- [ ] Middle flex sensor → voltage divider → GPIO34
- [ ] Ring flex sensor → voltage divider → GPIO35
- [ ] Little flex sensor → voltage divider → GPIO36
- [ ] MPU6050 VCC → 3.3V
- [ ] MPU6050 GND → GND
- [ ] MPU6050 SDA → GPIO21
- [ ] MPU6050 SCL → GPIO22
- [ ] MPU6050 AD0 → GND
- [ ] LED → 220Ω resistor → GPIO18
- [ ] USB data cable connected

---

*Next step: [CALIBRATION.md](CALIBRATION.md) — calibrate your flex sensors*
