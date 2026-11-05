# Expected wiring — verify physically before powering

| Component | ESP32 pin |
|---|---|
| Thumb, index, middle, ring, little flex junctions | GPIO32, 33, 34, 35, 36 (VP), respectively |
| GY-87 MPU6050 SDA, SCL | GPIO21, GPIO22 |
| Passive buzzer signal | GPIO19 |

**Current setup:** four sensors are enabled on GPIO32–35. The table above is the original expected mapping, not the confirmed mapping for this glove. GPIO36 is disabled; the user has not connected a thumb sensor. Label and verify each channel physically before assigning finger names. The GY-87 and buzzer are not connected yet.

Each flex divider is **3.3 V → flex sensor → ADC junction → 10 kΩ → GND**. Each finger needs its own junction and resistor; share ground. GPIO34–36 are input-only. Connect GY-87 power and ground according to the actual module's voltage specifications and ensure I2C signal levels are safe for the ESP32. MPU6050 address is 0x68. Connect the buzzer module's power and ground according to its specifications; GPIO19 provides the signal. Confirm your module's pin labels and drive requirements before connecting. Do not assume an LED is installed.

After upload, check one finger at a time, move the GY-87 and observe its readings, and use **Test buzzer**. Inspect wiring if values do not respond. Software cannot conclusively detect every disconnected or miswired sensor.
