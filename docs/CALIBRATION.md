# Calibrate the glove (hardware required)

1. Upload the current PlatformIO firmware, close the serial monitor, run the dashboard, select ESP32 serial, and connect.
2. Hold all five fingers comfortably straight and still. Click **Capture straight** and hold for approximately 5 seconds until capture returns to idle.
3. Hold all five fingers comfortably bent and still. Click **Capture bent** and hold until capture returns to idle. Bend sensors smoothly in their intended direction; do not fold them or bend near terminals.
4. Expand **Calibration measurements**. Verify each finger shows valid, with distinct straight and bent averages and a range of at least 50 ADC counts. Values that fluctuate by more than 120 counts during either capture or reach extreme ADC values are rejected. These limits are starting checks, not proof of sensor health.
5. Bend each finger independently. Verify its raw ADC changes and its percentage moves approximately 0–100% in the expected direction. Check the MPU6050 and buzzer.

If any finger fails, check its wiring and retry both capture steps. The workflow retries all fingers together; it reports validity independently. Firmware saves valid calibration in ESP32 nonvolatile storage. **Clear calibration** removes it; capturing straight starts a new calibration and invalidates the previous one. The straight capture must be repeated after reset before a new bent capture. ADC values can increase or decrease with bending. Old example values are not measurements. States use hysteresis (straight→half at 30%, half→straight at 20%, half→bent at 70%, bent→half at 60%).

For a serial-only workflow, close the dashboard and run `cd firmware && pio device monitor -b 115200 -p /dev/cu.usbserial-REPLACE`. Send `straight`, wait until `capture` is `idle`, then send `bent` and wait. Each command must end with a newline. `clear` and `buzzer` are also supported. The JSON lines contain all calibration values and statuses. Close the monitor before reopening the dashboard.

## Current four-sensor setup

The current firmware enables thumb through ring on GPIO32–35. GPIO36/little is disabled and marked `DISCONNECTED`; do not connect or calibrate it until the firmware configuration is changed. Hold the four connected fingers straight or bent during the capture. A retry records all four again. The disabled fifth slot is transmitted as a zero placeholder for dataset compatibility; it is not a physical reading. Collect fresh four-sensor data and retrain a matching model before recognition.
