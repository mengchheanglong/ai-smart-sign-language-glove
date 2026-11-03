# 🎛️ Sensor Calibration Guide

This guide explains how to calibrate the flex sensors so the firmware can accurately map raw ADC readings to a **0–100% bend percentage**.

---

## Why Calibrate?

Every flex sensor is slightly different. Even two sensors from the same batch will give different readings because:

- **Manufacturing variations** — each sensor has slightly different resistance characteristics
- **Resistor tolerance** — your 10kΩ resistors have ±5% tolerance, so the voltage divider output varies
- **Wiring differences** — contact resistance on the breadboard affects readings
- **Sensor age and wear** — flex sensors change slightly over time

**Without calibration**, the firmware doesn't know what "fully straight" or "fully bent" means for *your* specific sensor. Calibration tells it the range so it can convert raw numbers into meaningful percentages.

---

## What You Need

- ESP32 with flex sensor(s) wired up (see [HARDWARE_WIRING.md](HARDWARE_WIRING.md))
- USB cable connected to your computer
- Serial Monitor open (115200 baud)
- Something to write down numbers (notepad, text file, etc.)

---

## Calibration Procedure

### Step 1: Upload the firmware

Upload the current firmware to the ESP32 (calibration firmware will be provided in Phase 3 with additional features, but the basic firmware works for getting readings):

```bash
cd firmware
pio run --target upload
```

### Step 2: Open the Serial Monitor

```bash
pio device monitor
```

Or use the Serial Monitor in VS Code / Arduino IDE at **115200 baud**.

### Step 3: Record straight readings

For each finger sensor:

1. **Lay your hand flat** on a table with the glove on
2. Keep the finger **completely straight** and relaxed
3. Watch the Serial Monitor and note the **ADC reading** for that finger
4. This is your **"straight" value** (the maximum reading)

### Step 4: Record bent readings

For each finger sensor:

1. **Bend the finger** as far as it naturally goes (make a tight fist)
2. Hold the position steady
3. Watch the Serial Monitor and note the **ADC reading** for that finger
4. This is your **"bent" value** (the minimum reading)

### Step 5: Record your values

Fill in this table with your readings:

| Finger | Straight (flat) | Bent (fist) |
|---|---|---|
| Thumb (GPIO32) | ________ | ________ |
| Index (GPIO33) | ________ | ________ |
| Middle (GPIO34) | ________ | ________ |
| Ring (GPIO35) | ________ | ________ |
| Little (GPIO36) | ________ | ________ |

### Step 6: Enter values in the configuration

Open `firmware/include/config.h` and update the calibration values:

```cpp
// Calibration values — replace with YOUR readings
#define THUMB_STRAIGHT   3100    // your thumb straight reading
#define THUMB_BENT       800     // your thumb bent reading

#define INDEX_STRAIGHT   3000    // your index straight reading
#define INDEX_BENT       750     // your index bent reading

#define MIDDLE_STRAIGHT  2900    // your middle straight reading
#define MIDDLE_BENT      700     // your middle bent reading

#define RING_STRAIGHT    2950    // your ring straight reading
#define RING_BENT        720     // your ring bent reading

#define LITTLE_STRAIGHT  3050    // your little straight reading
#define LITTLE_BENT      780     // your little bent reading
```

### Step 7: Re-upload and verify

1. Save `config.h`
2. Upload the firmware again: `pio run --target upload`
3. Open the Serial Monitor
4. Verify that readings now show **0–100%** (or close to it)
   - Straight finger should be near **0%** (no bend)
   - Fully bent finger should be near **100%** (full bend)

---

## Expected Ranges

Here are typical ADC values for reference. Your values may differ — that's normal.

| Condition | Typical ADC Reading | Notes |
|---|---|---|
| Finger straight (flat) | 2000–3500 | Higher voltage → higher reading |
| Finger fully bent | 500–1500 | Lower voltage → lower reading |
| No sensor connected | 0 or fluctuating | Check wiring |
| Stuck at 4095 | — | Resistor missing or disconnected |

### If your readings seem reversed

If bending the sensor makes the reading go **up** instead of **down**:
- Your flex sensor leads may be **swapped** in the voltage divider
- Try switching which lead connects to 3.3V and which connects to the resistor/GPIO junction
- Or simply swap the "straight" and "bent" values in `config.h`

### If readings don't change at all

- Check your wiring against [HARDWARE_WIRING.md](HARDWARE_WIRING.md)
- Make sure the flex sensor is bending in the **correct direction** (most flex sensors only respond to bending one way)
- Try a different flex sensor (the spare one)
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more help

---

## Tips for Good Calibration

1. **Wear the glove** during calibration — the sensor behaves differently when it's flat on a table vs. attached to a glove on your hand

2. **Relax your hand** for straight readings — tension in your fingers will give false readings

3. **Bend fully** for bent readings — make a tight fist so you capture the full range

4. **Repeat 3 times and average** — take three readings for each position and use the average for better accuracy:
   ```
   Example:
   Straight readings: 3100, 3050, 3120 → Average: 3090
   Bent readings: 780, 810, 790 → Average: 793
   ```

5. **Recalibrate if you change hardware** — if you swap a resistor, move wires, or replace a sensor, recalibrate that finger

6. **Check periodically** — flex sensors can drift over time, especially new ones. Recalibrate every few sessions until the values stabilize

---

## Quick Reference

```
Straight finger → Low resistance → High voltage → High ADC value → 0% bend
Bent finger     → High resistance → Low voltage → Low ADC value → 100% bend
```

The firmware maps raw ADC values to percentages using this formula:

```
bend_percent = map(raw_reading, STRAIGHT_VALUE, BENT_VALUE, 0, 100)
```

Where:
- `raw_reading` = the current ADC reading from the sensor
- `STRAIGHT_VALUE` = your calibrated straight reading (high number)
- `BENT_VALUE` = your calibrated bent reading (low number)
- Result is clamped to 0–100%

---

*Next step: Proceed to Phase 3 tasks or see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if you're having issues.*
