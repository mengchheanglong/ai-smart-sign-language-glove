# Troubleshooting

- **Port missing or busy:** connect a USB data cable; run `ls /dev/cu.*`; install an appropriate CH340 driver if needed. Close other serial monitors, dashboard connections, and collectors before retrying.
- **No data or old firmware:** upload `firmware` environment `esp32dev`, baud 115200. Boot output may contain non-JSON text.
- **Uncalibrated or small range:** capture straight and bent again, holding still. Verify the individual divider, resistor, signal junction, sensor orientation, and ground. Extreme or constant readings are hints, not a diagnosis. Do not substitute guessed calibration numbers.
- **IMU unavailable:** verify GY-87 power, common ground, SDA GPIO21, SCL GPIO22, and MPU6050 address 0x68. Recognition pauses when IMU data is missing.
- **No model:** collect real data for at least two gestures across several sessions, then run the training command in the README. Restart/reload the dashboard.
- **Buzzer silent:** check GPIO19, module power/ground and module specifications, then use Test buzzer. Hardware operation has to be verified physically.
- **Poor recognition:** gather more varied real sessions, use a held-out session, check calibration and glove fit, and test untrained poses. Confidence is not validated accuracy. The raw-ADC model depends on glove fit and calibration.
