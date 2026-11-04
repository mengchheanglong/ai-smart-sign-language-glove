/*
 * main.cpp — AI Smart Sign Language Glove Firmware
 * 
 * PHASES 2–5 & 11: Multi-Sensor Glove Controller
 * 
 * WHAT THIS DOES:
 *   1. Reads 5 flex sensors (Thumb, Index, Middle, Ring, Little) on ADC1 pins.
 *   2. Applies a moving average filter to smooth analog noise.
 *   3. Reads hand orientation from MPU6050 IMU over I2C (SDA=21, SCL=22).
 *   4. Formats data into standard JSON packets at 25-50 Hz (default 25 Hz / 40 ms):
 *        {"timestamp_ms": 12345, "flex": [f1,f2,f3,f4,f5], "accel": [ax,ay,az], "gyro": [gx,gy,gz]}
 *   5. Receives feedback commands from the Python ML backend over Serial
 *      to blink the LED (GPIO18) when a gesture is recognized.
 *   6. Supports dynamic mode switching (JSON vs Human-readable table) via Serial.
 * 
 * HARDWARE SETUP:
 *   - ESP32-WROOM-32 DevKit V1 (or SparkFun IoT RedBoard ESP32)
 *   - 5 × Flex Sensors on GPIO 32, 33, 34, 35, 36 (voltage dividers with 10kΩ to GND)
 *   - 1 × MPU6050 6-DOF IMU on I2C (SDA=GPIO21, SCL=GPIO22, 3.3V, GND)
 *   - 1 × Feedback LED on GPIO18 (with 220Ω series resistor to GND)
 * 
 * SERIAL PROTOCOL:
 *   - Baud rate: 115200
 *   - Output: 1 JSON line per sample (when in JSON mode)
 *   - Input commands from computer:
 *       'j' or 'J' -> Switch to JSON output mode (default)
 *       'h' or 'H' -> Switch to Human-readable table mode
 *       'b' or 'B' -> Blink feedback LED
 *       {"led": 1} -> Trigger recognition blink from Python predictor
 * 
 * TEAM 2 — Senior Design Project
 */

#include <Arduino.h>
#include <Wire.h>
#include "config.h"

// ============================================================
// GLOBAL STATE & VARIABLES
// ============================================================

// Current output mode (JSON or Human-readable)
int currentOutputFormat = OUTPUT_FORMAT;

// Timing control for non-blocking sensor loop
unsigned long lastSampleTimeMs = 0;
unsigned long packetCounter = 0;

// LED feedback state (non-blocking pulse)
bool ledActive = false;
unsigned long ledOffTimeMs = 0;

// Filter buffers for moving average smoothing on the 5 flex sensors
int filterBuffer[NUM_FLEX_SENSORS][FILTER_SAMPLES];
int filterIndex = 0;
bool filterFilled = false;

// Filtered flex readings
int flexReadings[NUM_FLEX_SENSORS] = {0};

// MPU6050 state and data
bool imuAvailable = false;
uint8_t imuAddress = MPU6050_ADDRESS_PRIMARY;

float accel_x = 0.0f;
float accel_y = 0.0f;
float accel_z = 9.81f; // default gravity along Z when flat

float gyro_x = 0.0f;
float gyro_y = 0.0f;
float gyro_z = 0.0f;

// Stuck-sensor detection counters for each flex sensor
int stuckCounters[NUM_FLEX_SENSORS] = {0};
int lastRawReadings[NUM_FLEX_SENSORS] = {-1, -1, -1, -1, -1};

// Runtime calibration limits (initialized from config.h defaults)
int flexStraight[NUM_FLEX_SENSORS] = {
  DEFAULT_FLEX_STRAIGHT[0],
  DEFAULT_FLEX_STRAIGHT[1],
  DEFAULT_FLEX_STRAIGHT[2],
  DEFAULT_FLEX_STRAIGHT[3],
  DEFAULT_FLEX_STRAIGHT[4]
};

int flexBent[NUM_FLEX_SENSORS] = {
  DEFAULT_FLEX_BENT[0],
  DEFAULT_FLEX_BENT[1],
  DEFAULT_FLEX_BENT[2],
  DEFAULT_FLEX_BENT[3],
  DEFAULT_FLEX_BENT[4]
};

// Current sensor operating mode (Phase 2 single-sensor vs Phase 3-5 5-sensor)
int sensorMode = SENSOR_MODE_MULTI_5CH;

// ============================================================
// HELPER: VOLTAGE CONVERSION & NORMALIZED BEND
// ============================================================

/**
 * Convert raw 12-bit ADC reading (0-4095) to estimated voltage (0-3.3V).
 */
float adcToVoltage(int rawValue) {
  return (rawValue / (float)ADC_MAX_VALUE) * ADC_REF_VOLTAGE;
}

/**
 * Map raw ADC reading to 0-100% normalized bend based on calibration limits.
 */
int rawToBendPercent(int rawValue, int straightVal, int bentVal) {
  if (straightVal == bentVal) return 0;
  long pct = ((long)(straightVal - rawValue) * 100) / (straightVal - bentVal);
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return (int)pct;
}

/**
 * Check if raw ADC reading is within expected operational range.
 */
bool isReadingValid(int rawValue) {
  return (rawValue >= ADC_MIN_EXPECTED && rawValue <= ADC_MAX_EXPECTED);
}

// ============================================================
// MPU6050 I2C DRIVER (Direct Wire implementation — zero external deps)
// ============================================================

/**
 * Initialize MPU6050.
 * Probes primary address 0x68 and fallback 0x69.
 * Wakes up device by clearing sleep bit in PWR_MGMT_1 (register 0x6B).
 */
bool initMPU6050() {
  Wire.begin(MPU6050_SDA_PIN, MPU6050_SCL_PIN);
  Wire.setClock(400000); // 400kHz fast I2C clock

  // Try primary address 0x68 first
  Wire.beginTransmission(MPU6050_ADDRESS_PRIMARY);
  if (Wire.endTransmission() == 0) {
    imuAddress = MPU6050_ADDRESS_PRIMARY;
  } else {
    // Try secondary address 0x69
    Wire.beginTransmission(MPU6050_ADDRESS_SECONDARY);
    if (Wire.endTransmission() == 0) {
      imuAddress = MPU6050_ADDRESS_SECONDARY;
    } else {
      return false; // Neither address responded
    }
  }

  // Wake up MPU6050 (reset sleep bit in register 0x6B)
  Wire.beginTransmission(imuAddress);
  Wire.write(0x6B); // PWR_MGMT_1
  Wire.write(0x00); // Set to 0 to wake up
  if (Wire.endTransmission() != 0) {
    return false;
  }

  // Configure Accelerometer to ±2g range (register 0x1C = 0x00)
  Wire.beginTransmission(imuAddress);
  Wire.write(0x1C);
  Wire.write(0x00);
  Wire.endTransmission();

  // Configure Gyroscope to ±250 deg/s range (register 0x1B = 0x00)
  Wire.beginTransmission(imuAddress);
  Wire.write(0x1B);
  Wire.write(0x00);
  Wire.endTransmission();

  return true;
}

/**
 * Read Accelerometer and Gyroscope from MPU6050 registers (0x3B to 0x48).
 * Accelerometer sensitivity (±2g): 16384 LSB/g -> scaled to m/s^2 (* 9.80665)
 * Gyroscope sensitivity (±250 dps): 131.0 LSB/(deg/s)
 */
bool readMPU6050() {
  if (!imuAvailable) {
    // Graceful fallback: simulated upright resting orientation
    accel_x = 0.0f;
    accel_y = 0.0f;
    accel_z = 9.81f;
    gyro_x = 0.0f;
    gyro_y = 0.0f;
    gyro_z = 0.0f;
    return false;
  }

  Wire.beginTransmission(imuAddress);
  Wire.write(0x3B); // Starting register ACCEL_XOUT_H
  if (Wire.endTransmission(false) != 0) {
    // Bus error or disconnected
    return false;
  }

  // Request 14 bytes: 6 accel, 2 temp, 6 gyro
  uint8_t bytesRead = Wire.requestFrom((int)imuAddress, 14, (int)true);
  if (bytesRead != 14) {
    return false;
  }

  int16_t raw_ax = (Wire.read() << 8) | Wire.read();
  int16_t raw_ay = (Wire.read() << 8) | Wire.read();
  int16_t raw_az = (Wire.read() << 8) | Wire.read();
  
  // Skip temperature registers (0x41, 0x42)
  Wire.read();
  Wire.read();

  int16_t raw_gx = (Wire.read() << 8) | Wire.read();
  int16_t raw_gy = (Wire.read() << 8) | Wire.read();
  int16_t raw_gz = (Wire.read() << 8) | Wire.read();

  // Convert to m/s^2 (±2g range, 16384 LSB/g, 1g = 9.80665 m/s^2)
  accel_x = (raw_ax / 16384.0f) * 9.80665f;
  accel_y = (raw_ay / 16384.0f) * 9.80665f;
  accel_z = (raw_az / 16384.0f) * 9.80665f;

  // Convert to deg/s (±250 deg/s range, 131.0 LSB/(deg/s))
  gyro_x = raw_gx / 131.0f;
  gyro_y = raw_gy / 131.0f;
  gyro_z = raw_gz / 131.0f;

  return true;
}

// ============================================================
// FLEX SENSOR SAMPLING & FILTERING
// ============================================================

/**
 * Sample all 5 flex sensors and update moving average filter.
 */
void sampleFlexSensors() {
  for (int i = 0; i < NUM_FLEX_SENSORS; i++) {
    int raw = analogRead(FLEX_PINS[i]);

    // Check stuck sensor
    if (raw == lastRawReadings[i]) {
      stuckCounters[i]++;
    } else {
      stuckCounters[i] = 0;
    }
    lastRawReadings[i] = raw;

    // Store in filter buffer
    filterBuffer[i][filterIndex] = raw;

    // Compute moving average
    long sum = 0;
    int count = filterFilled ? FILTER_SAMPLES : (filterIndex + 1);
    for (int k = 0; k < count; k++) {
      sum += filterBuffer[i][k];
    }
    flexReadings[i] = (int)(sum / count);
  }

  filterIndex++;
  if (filterIndex >= FILTER_SAMPLES) {
    filterIndex = 0;
    filterFilled = true;
  }
}

// ============================================================
// LED FEEDBACK
// ============================================================

/**
 * Trigger a brief LED blink to confirm gesture recognition.
 */
void triggerLedBlink(unsigned long durationMs = LED_BLINK_DURATION_MS) {
  digitalWrite(LED_PIN, HIGH);
  ledActive = true;
  ledOffTimeMs = millis() + durationMs;
}

/**
 * Update LED pulse timing in non-blocking loop.
 */
void updateLed() {
  if (ledActive && millis() >= ledOffTimeMs) {
    digitalWrite(LED_PIN, LOW);
    ledActive = false;
  }
}

// ============================================================
// BUZZER FEEDBACK (PASSIVE BUZZER MODULE)
// ============================================================

#ifdef BUZZER_ENABLED
bool buzzerActive = false;
unsigned long buzzerOffTimeMs = 0;

/**
 * Trigger an audible tone on passive buzzer module using PWM.
 */
void triggerBuzzerTone(int freq = BUZZER_TONE_FREQ, unsigned long durationMs = BUZZER_BEEP_MS) {
  tone(BUZZER_PIN, freq, durationMs);
  buzzerActive = true;
  buzzerOffTimeMs = millis() + durationMs;
}

/**
 * Update buzzer shutoff in non-blocking loop.
 */
void updateBuzzer() {
  if (buzzerActive && millis() >= buzzerOffTimeMs) {
    noTone(BUZZER_PIN);
    buzzerActive = false;
  }
}
#endif

// ============================================================
// CALIBRATION WIZARD (Phase 3)
// ============================================================

/**
 * Interactive calibration sequence:
 * 1. Guides user to lay hand flat (straight fingers) and records 30 samples.
 * 2. Guides user to make a tight fist (bent fingers) and records 30 samples.
 * 3. Calculates per-channel averages, updates runtime thresholds,
 *    and prints formatted C++ snippet for config.h.
 */
void runCalibrationRoutine() {
  Serial.println();
  Serial.println("==================================================");
  Serial.println("  🖐️  FLEX SENSOR INTERACTIVE CALIBRATION WIZARD");
  Serial.println("  AI Smart Sign Language Glove — Team 2");
  Serial.println("==================================================");
  Serial.println("STEP 1: Lay your hand FLAT on the table.");
  Serial.println("Keep all fingers completely straight and relaxed.");
  Serial.println("Sampling begins in 3 seconds...");

  for (int i = 3; i > 0; i--) {
    Serial.printf("  ⏱️  %d...\n", i);
    digitalWrite(LED_PIN, HIGH);
    delay(100);
    digitalWrite(LED_PIN, LOW);
    delay(900);
  }

  Serial.println("Measuring straight positions (30 samples)...");
  long sumStraight[NUM_FLEX_SENSORS] = {0};
  for (int s = 0; s < 30; s++) {
    for (int i = 0; i < NUM_FLEX_SENSORS; i++) {
      sumStraight[i] += analogRead(FLEX_PINS[i]);
    }
    delay(40);
  }
  for (int i = 0; i < NUM_FLEX_SENSORS; i++) {
    flexStraight[i] = (int)(sumStraight[i] / 30);
  }

  Serial.println("\nSTEP 2: Make a TIGHT FIST.");
  Serial.println("Bend all fingers as far as comfortable.");
  Serial.println("Sampling begins in 3 seconds...");

  for (int i = 3; i > 0; i--) {
    Serial.printf("  ⏱️  %d...\n", i);
    digitalWrite(LED_PIN, HIGH);
    delay(100);
    digitalWrite(LED_PIN, LOW);
    delay(900);
  }

  Serial.println("Measuring bent positions (30 samples)...");
  long sumBent[NUM_FLEX_SENSORS] = {0};
  for (int s = 0; s < 30; s++) {
    for (int i = 0; i < NUM_FLEX_SENSORS; i++) {
      sumBent[i] += analogRead(FLEX_PINS[i]);
    }
    delay(40);
  }
  for (int i = 0; i < NUM_FLEX_SENSORS; i++) {
    flexBent[i] = (int)(sumBent[i] / 30);
  }

  Serial.println("\n✅ CALIBRATION COMPLETE!");
  Serial.println("==================================================");
  Serial.println("Finger   | Straight (ADC) | Bent (ADC) | Range");
  Serial.println("---------+----------------+------------+------");
  const char* names[5] = {"Thumb ", "Index ", "Middle", "Ring  ", "Little"};
  for (int i = 0; i < NUM_FLEX_SENSORS; i++) {
    int range = abs(flexStraight[i] - flexBent[i]);
    Serial.printf("%s   | %14d | %10d | %5d\n",
      names[i], flexStraight[i], flexBent[i], range);
  }
  Serial.println("==================================================");
  Serial.println("Copy and paste these lines into firmware/include/config.h:\n");
  Serial.printf("static const int DEFAULT_FLEX_STRAIGHT[NUM_FLEX_SENSORS] = {%d, %d, %d, %d, %d};\n",
    flexStraight[0], flexStraight[1], flexStraight[2], flexStraight[3], flexStraight[4]);
  Serial.printf("static const int DEFAULT_FLEX_BENT[NUM_FLEX_SENSORS]     = {%d, %d, %d, %d, %d};\n",
    flexBent[0], flexBent[1], flexBent[2], flexBent[3], flexBent[4]);
  Serial.println("==================================================\n");

  // Success indicator: 5 rapid LED blinks
  for (int b = 0; b < 5; b++) {
    digitalWrite(LED_PIN, HIGH);
    delay(60);
    digitalWrite(LED_PIN, LOW);
    delay(60);
  }
}

// ============================================================
// SERIAL COMMAND PROCESSING
// ============================================================

/**
 * Read incoming serial commands from Python backend or user monitor.
 */
void processSerialInput() {
  while (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() == 0) continue;

    // Single character quick commands
    if (cmd.equalsIgnoreCase("j")) {
      currentOutputFormat = OUTPUT_FORMAT_JSON;
      sensorMode = SENSOR_MODE_MULTI_5CH;
    } else if (cmd.equalsIgnoreCase("h")) {
      currentOutputFormat = OUTPUT_FORMAT_HUMAN;
      sensorMode = SENSOR_MODE_MULTI_5CH;
      Serial.println("\n[MODE] Switched to Human-Readable Table output (5-Sensor mode)");
    } else if (cmd.equalsIgnoreCase("c")) {
      runCalibrationRoutine();
    } else if (cmd.equals("1")) {
      sensorMode = SENSOR_MODE_SINGLE_CH;
      currentOutputFormat = OUTPUT_FORMAT_HUMAN;
      Serial.println("\n[MODE] Switched to Phase 2 Single-Sensor Test Mode (Thumb GPIO32)");
    } else if (cmd.equals("5")) {
      sensorMode = SENSOR_MODE_MULTI_5CH;
      Serial.println("\n[MODE] Switched to 5-Sensor Multi-Channel Mode");
    } else if (cmd.equalsIgnoreCase("b")) {
      triggerLedBlink();
#ifdef BUZZER_ENABLED
      triggerBuzzerTone();
#endif
    } else if (cmd.equalsIgnoreCase("z")) {
#ifdef BUZZER_ENABLED
      triggerBuzzerTone(2400, 150);
      Serial.println("[BUZZER] Tested passive buzzer tone on GPIO" + String(BUZZER_PIN));
#else
      Serial.println("[BUZZER] Buzzer support is disabled in config.h");
#endif
    } else if (cmd.indexOf("\"led\": 1") >= 0 || cmd.indexOf("\"led\":1") >= 0 ||
               cmd.indexOf("\"led\": true") >= 0 || cmd.indexOf("\"led\":true") >= 0 ||
               cmd.indexOf("gesture") >= 0 || cmd.indexOf("blink") >= 0) {
      // JSON feedback from Python predictor: e.g. {"led": 1}
      triggerLedBlink();
#ifdef BUZZER_ENABLED
      triggerBuzzerTone();
#endif
    }
  }
}

// ============================================================
// DATA OUTPUT ROUTINES
// ============================================================

/**
 * Output data as a single-line JSON packet.
 * Format:
 * {"timestamp_ms": 1234, "flex": [1200, 1800, 2100, 1500, 1900], "accel": [0.10, -0.20, 9.81], "gyro": [0.00, 0.10, -0.05]}
 */
void printJsonPacket(unsigned long timestampMs) {
  Serial.print("{\"timestamp_ms\":");
  Serial.print(timestampMs);

  // Flex sensor array
  Serial.print(",\"flex\":[");
  for (int i = 0; i < NUM_FLEX_SENSORS; i++) {
    Serial.print(flexReadings[i]);
    if (i < NUM_FLEX_SENSORS - 1) Serial.print(",");
  }
  Serial.print("]");

  // Accelerometer array [ax, ay, az] in m/s^2
  Serial.print(",\"accel\":[");
  Serial.print(accel_x, 2);
  Serial.print(",");
  Serial.print(accel_y, 2);
  Serial.print(",");
  Serial.print(accel_z, 2);
  Serial.print("]");

  // Gyroscope array [gx, gy, gz] in deg/s
  Serial.print(",\"gyro\":[");
  Serial.print(gyro_x, 2);
  Serial.print(",");
  Serial.print(gyro_y, 2);
  Serial.print(",");
  Serial.print(gyro_z, 2);
  Serial.print("]");

  // Hardware status flag distinguishing real MPU6050 from neutral fallback
  Serial.print(",\"imu_valid\":");
  Serial.print(imuAvailable ? "true" : "false");
  Serial.print("}\n");
}

/**
 * Output data as a human-readable table for debugging in Serial Monitor.
 * Displays both raw ADC and normalized bend percentage per finger.
 */
void printHumanTable(unsigned long timestampMs) {
  packetCounter++;
  if (packetCounter % 20 == 1) {
    Serial.println();
    Serial.println("Time(ms) | Thumb (Bend%)  | Index (Bend%)  | Mid   (Bend%)  | Ring  (Bend%)  | Pinky (Bend%)  | Accel(X,Y,Z) m/s²    | IMU");
    Serial.println("---------+----------------+----------------+----------------+----------------+----------------+----------------------+-----");
  }

  int b0 = rawToBendPercent(flexReadings[0], flexStraight[0], flexBent[0]);
  int b1 = rawToBendPercent(flexReadings[1], flexStraight[1], flexBent[1]);
  int b2 = rawToBendPercent(flexReadings[2], flexStraight[2], flexBent[2]);
  int b3 = rawToBendPercent(flexReadings[3], flexStraight[3], flexBent[3]);
  int b4 = rawToBendPercent(flexReadings[4], flexStraight[4], flexBent[4]);

  Serial.printf("%8lu | %4d (%3d%%) | %4d (%3d%%) | %4d (%3d%%) | %4d (%3d%%) | %4d (%3d%%) | %5.1f, %5.1f, %5.1f | %s\n",
    timestampMs,
    flexReadings[0], b0,
    flexReadings[1], b1,
    flexReadings[2], b2,
    flexReadings[3], b3,
    flexReadings[4], b4,
    accel_x, accel_y, accel_z,
    imuAvailable ? "OK" : "NONE"
  );
}

/**
 * Phase 2 Single-Sensor Diagnostic Output (Thumb GPIO32).
 */
void printSingleSensorDiagnostic(unsigned long timestampMs) {
  int rawThumb = analogRead(FLEX_THUMB_PIN);
  float voltage = adcToVoltage(rawThumb);
  int bendPct = rawToBendPercent(rawThumb, flexStraight[0], flexBent[0]);
  bool isStuck = (stuckCounters[0] >= STUCK_SENSOR_THRESHOLD);
  bool inRange = isReadingValid(rawThumb);

  Serial.printf("[PHASE 2 - GPIO%d] %8lu ms | ADC: %4d | Volt: %4.2fV | Bend: %3d%% | Valid: %s | Stuck: %s\n",
    FLEX_THUMB_PIN, timestampMs, rawThumb, voltage, bendPct,
    inRange ? "YES" : "NO (CHECK CIRCUIT)",
    isStuck ? "STUCK WARNING" : "OK");
}

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(SERIAL_BAUD_RATE);
  while (!Serial && millis() < 2000) {
    delay(10);
  }

  // Initialize LED pin
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

#ifdef BUZZER_ENABLED
  // Initialize passive buzzer pin
  pinMode(BUZZER_PIN, OUTPUT);
  // Startup chirp: 2 short friendly tones (2000Hz, then 2600Hz)
  tone(BUZZER_PIN, 2000, 60);
  delay(80);
  tone(BUZZER_PIN, 2600, 80);
#endif

  // Initialize ADC settings
  analogReadResolution(ADC_RESOLUTION);
  analogSetAttenuation(ADC_11db);

  // Configure flex sensor pins as inputs
  for (int i = 0; i < NUM_FLEX_SENSORS; i++) {
    pinMode(FLEX_PINS[i], INPUT);
  }

  // Initialize MPU6050 IMU
  imuAvailable = initMPU6050();

  // Startup LED indication (3 quick blinks to verify LED hardware)
  for (int b = 0; b < 3; b++) {
    digitalWrite(LED_PIN, HIGH);
    delay(80);
    digitalWrite(LED_PIN, LOW);
    delay(80);
  }

  if (currentOutputFormat == OUTPUT_FORMAT_HUMAN) {
    Serial.println();
    Serial.println("================================================");
    Serial.println("  AI Smart Sign Language Glove — Firmware v1.0");
    Serial.println("  Team 2 — Senior Design Project");
    Serial.println("================================================");
    Serial.printf("Flex Sensors: 5 channels on ADC1 (Pins: 32, 33, 34, 35, 36)\n");
    Serial.printf("IMU Status:   %s (Addr: 0x%02X)\n", imuAvailable ? "CONNECTED" : "DISCONNECTED (using fallback)", imuAddress);
    Serial.printf("Sampling:     %d ms (%d Hz)\n", SAMPLING_INTERVAL_MS, 1000 / SAMPLING_INTERVAL_MS);
    Serial.printf("LED Feedback: GPIO%d\n", LED_PIN);
#ifdef BUZZER_ENABLED
    Serial.printf("Buzzer:       Passive Module on GPIO%d (%d Hz tone)\n", BUZZER_PIN, BUZZER_TONE_FREQ);
#else
    Serial.println("Buzzer:       Disabled");
#endif
    Serial.println("Press 'j' for JSON mode, 'h' for Human mode, 'b' for LED, 'z' for Buzzer");
    Serial.println("================================================");
  }
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
  // Check for incoming commands from PC / Python
  processSerialInput();

  // Maintain LED pulse timing
  updateLed();

#ifdef BUZZER_ENABLED
  // Maintain buzzer pulse timing
  updateBuzzer();
#endif

  // Non-blocking sampling timer
  unsigned long now = millis();
  if (now - lastSampleTimeMs >= SAMPLING_INTERVAL_MS) {
    lastSampleTimeMs = now;

    // 1. Read all 5 flex sensors with moving average filter
    sampleFlexSensors();

    // 2. Read IMU data (or fallback if disconnected)
    if (imuAvailable) {
      if (!readMPU6050()) {
        // Attempt periodic re-init if communication drops
        static unsigned long lastReinitAttempt = 0;
        if (now - lastReinitAttempt > 3000) {
          lastReinitAttempt = now;
          imuAvailable = initMPU6050();
        }
      }
    }

    // 3. Output data in selected format
    if (currentOutputFormat == OUTPUT_FORMAT_JSON) {
      printJsonPacket(now);
    } else {
      if (sensorMode == SENSOR_MODE_SINGLE_CH) {
        printSingleSensorDiagnostic(now);
      } else {
        printHumanTable(now);
      }
    }
  }
}
