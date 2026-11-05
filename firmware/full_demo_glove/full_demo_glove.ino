/*
 * full_demo_glove.ino — Complete 5-Finger AI Smart Sign Language Glove
 * 
 * HARDWARE MAPPING:
 *   - Thumb  Flex:  GPIO 32 (D32)
 *   - Index  Flex:  GPIO 33 (D33)
 *   - Middle Flex:  GPIO 34 (D34)
 *   - Ring   Flex:  GPIO 35 (D35)
 *   - Little Flex:  GPIO 36 (VP)
 *   - GY-87 / MPU6050 IMU: SDA = GPIO 21, SCL = GPIO 22 (I2C addr 0x68)
 *   - Passive Buzzer Module: GPIO 19 (PWM tones)
 *   - Recognition LED:       GPIO 18 (220Ω resistor)
 * 
 * ZERO EXTERNAL LIBRARIES REQUIRED (Uses only built-in Wire.h and Arduino.h)
 */

#include <Arduino.h>
#include <Wire.h>

// ============================================================
// 1. PIN ASSIGNMENTS (ESP32 30-Pin Dev Module)
// ============================================================
const int PIN_THUMB  = 32;
const int PIN_INDEX  = 33;
const int PIN_MIDDLE = 34;
const int PIN_RING   = 35;
const int PIN_LITTLE = 36; // Labeled "VP" on 30-pin board

const int NUM_SENSORS = 5;
const int SENSOR_PINS[NUM_SENSORS] = { PIN_THUMB, PIN_INDEX, PIN_MIDDLE, PIN_RING, PIN_LITTLE };
const char* SENSOR_NAMES[NUM_SENSORS] = { "Thumb ", "Index ", "Middle", "Ring  ", "Little" };

const int PIN_SDA    = 21;
const int PIN_SCL    = 22;
const int PIN_LED    = 18;
const int PIN_BUZZER = 19;

// ============================================================
// 2. CALIBRATION BASELINES (Measured with 10kΩ pull-down to GND)
// ============================================================
// Straight finger -> Lower resistance -> Higher voltage / higher ADC
// Bent finger     -> Higher resistance -> Lower voltage / lower ADC
int straightADC[NUM_SENSORS] = { 1050, 1200, 1150, 1150, 1150 };
int bentADC[NUM_SENSORS]     = {  370,  400,  390,  390,  390 };

// ============================================================
// 3. SETTINGS & FILTERING
// ============================================================
const int SAMPLING_INTERVAL_MS = 40; // 25 Hz update rate
const int FILTER_SAMPLES = 4;
int filterBuffers[NUM_SENSORS][FILTER_SAMPLES] = {0};
int filterIndex = 0;
bool filterFilled = false;
int filteredFlex[NUM_SENSORS] = {0};

// Output Mode: 0 = Human-Readable Table (Serial Monitor), 1 = JSON (Python ML Backend)
int outputMode = 0; // Default to Human Table so it looks awesome in Serial Monitor!

// IMU State
bool imuFound = false;
float ax = 0.0f, ay = 0.0f, az = 9.81f;
float gx = 0.0f, gy = 0.0f, gz = 0.0f;
float pitch = 0.0f, roll = 0.0f;

// LED & Buzzer non-blocking timer
bool ledActive = false;
unsigned long ledOffTime = 0;
bool buzzerActive = false;
unsigned long buzzerOffTime = 0;

unsigned long lastSampleTime = 0;
unsigned long printHeaderCounter = 0;

// ============================================================
// 4. BUZZER & LED CONTROL
// ============================================================
void triggerBuzzer(int freq = 2000, unsigned long ms = 80) {
  tone(PIN_BUZZER, freq, ms);
  buzzerActive = true;
  buzzerOffTime = millis() + ms;
}

void triggerLed(unsigned long ms = 150) {
  digitalWrite(PIN_LED, HIGH);
  ledActive = true;
  ledOffTime = millis() + ms;
}

void updateActuators() {
  unsigned long now = millis();
  if (ledActive && now >= ledOffTime) {
    digitalWrite(PIN_LED, LOW);
    ledActive = false;
  }
  if (buzzerActive && now >= buzzerOffTime) {
    noTone(PIN_BUZZER);
    buzzerActive = false;
  }
}

// ============================================================
// 5. GY-87 / MPU6050 DIRECT I2C DRIVER
// ============================================================
bool initMPU6050() {
  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);

  // Probe address 0x68
  Wire.beginTransmission(0x68);
  if (Wire.endTransmission() != 0) return false;

  // Wake up device (clear sleep bit in register 0x6B)
  Wire.beginTransmission(0x68);
  Wire.write(0x6B);
  Wire.write(0x00);
  if (Wire.endTransmission() != 0) return false;

  // Accel ±2g
  Wire.beginTransmission(0x68);
  Wire.write(0x1C);
  Wire.write(0x00);
  Wire.endTransmission();

  // Gyro ±250 deg/s
  Wire.beginTransmission(0x68);
  Wire.write(0x1B);
  Wire.write(0x00);
  Wire.endTransmission();

  return true;
}

bool readMPU6050() {
  if (!imuFound) return false;

  Wire.beginTransmission(0x68);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;

  if (Wire.requestFrom(0x68, 14, 1) != 14) return false;

  int16_t raw_ax = (Wire.read() << 8) | Wire.read();
  int16_t raw_ay = (Wire.read() << 8) | Wire.read();
  int16_t raw_az = (Wire.read() << 8) | Wire.read();
  Wire.read(); Wire.read(); // temp
  int16_t raw_gx = (Wire.read() << 8) | Wire.read();
  int16_t raw_gy = (Wire.read() << 8) | Wire.read();
  int16_t raw_gz = (Wire.read() << 8) | Wire.read();

  ax = (raw_ax / 16384.0f) * 9.80665f;
  ay = (raw_ay / 16384.0f) * 9.80665f;
  az = (raw_az / 16384.0f) * 9.80665f;

  gx = raw_gx / 131.0f;
  gy = raw_gy / 131.0f;
  gz = raw_gz / 131.0f;

  pitch = atan2f(-ax, sqrtf(ay * ay + az * az)) * 180.0f / PI;
  roll  = atan2f(ay, az) * 180.0f / PI;

  return true;
}

// ============================================================
// 6. FLEX SENSOR MATH & FILTERING
// ============================================================
int calculateBendPct(int raw, int straightVal, int bentVal) {
  float range = (float)straightVal - bentVal;
  if (fabsf(range) < 1.0f) return 0;
  float pct = ((float)(straightVal - raw) / range) * 100.0f;
  return (int)constrain(pct, 0.0f, 100.0f);
}

const char* getBendLabel(int pct) {
  if (pct < 25) return "STRAIGHT";
  if (pct < 65) return "HALF-BENT";
  return "BENT";
}

void sampleSensors() {
  for (int i = 0; i < NUM_SENSORS; i++) {
    int raw = analogRead(SENSOR_PINS[i]);
    filterBuffers[i][filterIndex] = raw;

    long sum = 0;
    int count = filterFilled ? FILTER_SAMPLES : (filterIndex + 1);
    for (int k = 0; k < count; k++) {
      sum += filterBuffers[i][k];
    }
    filteredFlex[i] = (int)(sum / count);
  }

  filterIndex++;
  if (filterIndex >= FILTER_SAMPLES) {
    filterIndex = 0;
    filterFilled = true;
  }
}

// ============================================================
// 7. INTERACTIVE CALIBRATION WIZARD
// ============================================================
void runCalibration() {
  Serial.println("\n========================================================");
  Serial.println("  🖐️  5-FINGER INTERACTIVE CALIBRATION WIZARD");
  Serial.println("========================================================");
  Serial.println("STEP 1: Keep ALL 5 fingers completely STRAIGHT and flat.");
  Serial.println("Recording begins in 3 seconds...");

  for (int i = 3; i > 0; i--) {
    Serial.printf("  ⏱️  %d...\n", i);
    triggerLed(100);
    triggerBuzzer(1500, 80);
    delay(1000);
  }

  Serial.println(">>> Recording STRAIGHT positions (30 samples)...");
  long sumStraight[NUM_SENSORS] = {0};
  for (int s = 0; s < 30; s++) {
    for (int i = 0; i < NUM_SENSORS; i++) {
      sumStraight[i] += analogRead(SENSOR_PINS[i]);
    }
    delay(40);
  }
  for (int i = 0; i < NUM_SENSORS; i++) {
    straightADC[i] = (int)(sumStraight[i] / 30);
  }

  Serial.println("\nSTEP 2: Make a TIGHT FIST (BEND all 5 fingers).");
  Serial.println("Recording begins in 3 seconds...");

  for (int i = 3; i > 0; i--) {
    Serial.printf("  ⏱️  %d...\n", i);
    triggerLed(100);
    triggerBuzzer(1500, 80);
    delay(1000);
  }

  Serial.println(">>> Recording BENT positions (30 samples)...");
  long sumBent[NUM_SENSORS] = {0};
  for (int s = 0; s < 30; s++) {
    for (int i = 0; i < NUM_SENSORS; i++) {
      sumBent[i] += analogRead(SENSOR_PINS[i]);
    }
    delay(40);
  }
  for (int i = 0; i < NUM_SENSORS; i++) {
    bentADC[i] = (int)(sumBent[i] / 30);
  }

  // Triumphant double-beep
  triggerBuzzer(2400, 100);
  delay(120);
  triggerBuzzer(3000, 150);

  Serial.println("\n✅ CALIBRATION SAVED SUCCESSFULLY!");
  Serial.println("--------------------------------------------------------");
  Serial.println("Finger  | Pin | Straight ADC | Bent ADC | Delta Range");
  Serial.println("--------+-----+--------------+----------+------------");
  for (int i = 0; i < NUM_SENSORS; i++) {
    int range = abs(straightADC[i] - bentADC[i]);
    Serial.printf("%s | D%02d | %12d | %8d | %11d\n",
      SENSOR_NAMES[i], SENSOR_PINS[i], straightADC[i], bentADC[i], range);
  }
  Serial.println("--------------------------------------------------------\n");
}

// ============================================================
// 8. SERIAL TELEMETRY & COMMANDS
// ============================================================
void printHumanTable() {
  printHeaderCounter++;
  if (printHeaderCounter % 25 == 1) {
    Serial.println();
    Serial.println("Time(ms) | Thumb (D32)  | Index (D33)  | Mid   (D34)  | Ring  (D35)  | Pinky (D36)  | Pitch | Roll  | IMU");
    Serial.println("---------+--------------+--------------+--------------+--------------+--------------+-------+-------+-----");
  }

  int b[NUM_SENSORS];
  for (int i = 0; i < NUM_SENSORS; i++) {
    b[i] = calculateBendPct(filteredFlex[i], straightADC[i], bentADC[i]);
  }

  Serial.printf("%8lu | %4d %3d%% %-2s | %4d %3d%% %-2s | %4d %3d%% %-2s | %4d %3d%% %-2s | %4d %3d%% %-2s | %+5.1f°| %+5.1f°| %s\n",
    millis(),
    filteredFlex[0], b[0], getBendLabel(b[0]),
    filteredFlex[1], b[1], getBendLabel(b[1]),
    filteredFlex[2], b[2], getBendLabel(b[2]),
    filteredFlex[3], b[3], getBendLabel(b[3]),
    filteredFlex[4], b[4], getBendLabel(b[4]),
    pitch, roll,
    imuFound ? "OK" : "NO"
  );
}

void printJsonPacket() {
  Serial.print("{\"timestamp_ms\":");
  Serial.print(millis());
  Serial.print(",\"flex\":[");
  for (int i = 0; i < NUM_SENSORS; i++) {
    Serial.print(filteredFlex[i]);
    if (i < NUM_SENSORS - 1) Serial.print(",");
  }
  Serial.print("],\"accel\":[");
  Serial.print(ax, 2); Serial.print(",");
  Serial.print(ay, 2); Serial.print(",");
  Serial.print(az, 2);
  Serial.print("],\"gyro\":[");
  Serial.print(gx, 2); Serial.print(",");
  Serial.print(gy, 2); Serial.print(",");
  Serial.print(gz, 2);
  Serial.print("],\"imu_valid\":");
  Serial.print(imuFound ? "true" : "false");
  Serial.println("}");
}

void handleSerialCommands() {
  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() == 0) continue;

    if (cmd.equalsIgnoreCase("h")) {
      outputMode = 0;
      Serial.println("\n[MODE] Switched to Human-Readable Monitor Table");
    } else if (cmd.equalsIgnoreCase("j")) {
      outputMode = 1;
    } else if (cmd.equalsIgnoreCase("c")) {
      runCalibration();
    } else if (cmd.equalsIgnoreCase("b")) {
      triggerLed(200);
      triggerBuzzer(2000, 100);
      Serial.println("[TEST] LED blinked & Buzzer beeped!");
    } else if (cmd.equalsIgnoreCase("z")) {
      triggerBuzzer(2400, 150);
      Serial.println("[TEST] Passive Buzzer chirp on GPIO19!");
    } else if (cmd.indexOf("\"led\"") >= 0 || cmd.indexOf("\"buzzer\"") >= 0) {
      // Gesture recognition feedback trigger from Python ML Predictor
      triggerLed(150);
      triggerBuzzer(2200, 80);
    }
  }
}

// ============================================================
// 9. SETUP & LOOP
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  pinMode(PIN_BUZZER, OUTPUT);

  // Play startup confirmation chime
  triggerBuzzer(2000, 70);
  delay(90);
  triggerBuzzer(2600, 90);

  // Configure ADC1
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  for (int i = 0; i < NUM_SENSORS; i++) {
    pinMode(SENSOR_PINS[i], INPUT);
  }

  // Initialize GY-87 / MPU6050
  imuFound = initMPU6050();

  // 3 Startup blinks
  for (int i = 0; i < 3; i++) {
    digitalWrite(PIN_LED, HIGH);
    delay(80);
    digitalWrite(PIN_LED, LOW);
    delay(80);
  }

  Serial.println();
  Serial.println("========================================================");
  Serial.println("  🧤 AI SMART SIGN LANGUAGE GLOVE — COMPLETE FIRMWARE");
  Serial.println("  5 Flex Channels + GY-87 (MPU6050) + Buzzer + LED");
  Serial.println("========================================================");
  Serial.printf("Flex Pins:   D32 (Thumb), D33 (Index), D34 (Mid), D35 (Ring), D36 (Pinky)\n");
  Serial.printf("IMU Sensor:  %s (SDA=21, SCL=22, Addr=0x68)\n", imuFound ? "ONLINE (GY-87 10DOF)" : "NOT DETECTED (Check SDA/SCL)");
  Serial.printf("Buzzer Pin:  GPIO19 (PWM Passive Buzzer)\n");
  Serial.printf("LED Pin:     GPIO18 (Gesture Feedback)\n");
  Serial.println("--------------------------------------------------------");
  Serial.println("COMMANDS: 'c'=Calibrate Wizard | 'h'=Table Mode | 'j'=JSON Mode");
  Serial.println("          'b'=Blink+Beep Test  | 'z'=Buzzer Tone Test");
  Serial.println("========================================================\n");
}

void loop() {
  handleSerialCommands();
  updateActuators();

  unsigned long now = millis();
  if (now - lastSampleTime >= SAMPLING_INTERVAL_MS) {
    lastSampleTime = now;

    sampleSensors();
    if (imuFound) {
      readMPU6050();
    }

    if (outputMode == 0) {
      printHumanTable();
    } else {
      printJsonPacket();
    }
  }
}
