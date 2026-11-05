/*
 * config.h — Hardware Configuration for ESP32 Gesture Recognition Glove
 * 
 * PURPOSE:
 *   All pin assignments and hardware settings live here.
 *   Change this file when switching ESP32 boards or rewiring sensors.
 * 
 * TEAM 2 — Senior Design Project
 */

#ifndef CONFIG_H
#define CONFIG_H

// ============================================================
// BOARD SELECTION
// ============================================================
// Uncomment ONE of the following lines (or set via build_flags):
// #define USE_SPARKFUN_BOARD
// By default, we target the generic ESP32 DevKit V1.

// ============================================================
// SERIAL COMMUNICATION
// ============================================================
#define SERIAL_BAUD_RATE 115200

// ============================================================
// SAMPLING CONFIGURATION
// ============================================================
// Sampling interval in milliseconds.
// 100ms = ~10 Hz (good for monitoring in Serial Monitor)
//  40ms = ~25 Hz (standard for gesture data collection and real-time inference)
//  20ms = ~50 Hz (maximum recommended for serial JSON output)
#define SAMPLING_INTERVAL_MS 100

// ============================================================
// FLEX SENSOR PIN ASSIGNMENTS (ADC1 channels only!)
// ============================================================
// IMPORTANT: ESP32 ADC2 pins CANNOT be used when WiFi is active.
// We use ADC1 pins only (GPIO32-GPIO39) for reliable readings.
//
// Voltage divider wiring for each flex sensor:
//   3.3V → Flex Sensor → Measurement Node → 10kΩ Resistor → GND
//                              ↓
//                         ESP32 ADC Pin
//
// When the finger is STRAIGHT: flex resistance is LOW → voltage is HIGH → ADC reads HIGH
// When the finger is BENT:     flex resistance is HIGH → voltage is LOW  → ADC reads LOW

#ifdef USE_SPARKFUN_BOARD
  // SparkFun IoT RedBoard — verify these pins are exposed on your board!
  #define FLEX_THUMB_PIN   32   // ADC1_CH4
  #define FLEX_INDEX_PIN   33   // ADC1_CH5
  #define FLEX_MIDDLE_PIN  34   // ADC1_CH6 (input-only)
  #define FLEX_RING_PIN    35   // ADC1_CH7 (input-only)
  #define FLEX_LITTLE_PIN  36   // ADC1_CH0 (input-only, also labeled SVP)
#else
  // Generic ESP32 DevKit V1 (30-pin Type-C / CH340 reference)
  #define FLEX_THUMB_PIN   32   // ADC1_CH4 (labeled D32)
  #define FLEX_INDEX_PIN   33   // ADC1_CH5 (labeled D33)
  #define FLEX_MIDDLE_PIN  34   // ADC1_CH6 (input-only, labeled D34)
  #define FLEX_RING_PIN    35   // ADC1_CH7 (input-only, labeled D35)
  #define FLEX_LITTLE_PIN  36   // ADC1_CH0 (input-only, labeled VP on 30-pin boards!)
#endif

// Number of flex sensors
#define NUM_FLEX_SENSORS 5
// Four physical sensors connected; slot 5 is reserved and marked unavailable.
#define ACTIVE_FLEX_SENSORS 4

// Pin array for multi-sensor loops: [Thumb, Index, Middle, Ring, Little]
static const int FLEX_PINS[NUM_FLEX_SENSORS] = {
  FLEX_THUMB_PIN,
  FLEX_INDEX_PIN,
  FLEX_MIDDLE_PIN,
  FLEX_RING_PIN,
  FLEX_LITTLE_PIN
};

// Moving average filter window size to smooth ADC noise
#define FILTER_SAMPLES 4

// ADC Configuration
// ESP32 default ADC resolution: 12-bit (0-4095)
// ESP32 default ADC attenuation: 11dB (reads up to ~3.3V)
#define ADC_RESOLUTION   12
#define ADC_MAX_VALUE    4095
#define ADC_REF_VOLTAGE  3.3

// Stuck-sensor detection: if a sensor reads the same value
// this many times in a row, it may be disconnected or broken.
#define STUCK_SENSOR_THRESHOLD 50

// Minimum and maximum expected ADC readings for a connected sensor.
// Readings outside this range suggest a wiring problem.
#define ADC_MIN_EXPECTED  100
#define ADC_MAX_EXPECTED  3900

// Calibration defaults (raw ADC values for fully straight vs fully bent)
// [Thumb, Index, Middle, Ring, Little]
// Calibration is recorded by the user and stored in nonvolatile memory.

// Operating modes:
#define SENSOR_MODE_MULTI_5CH   0   // Default: All 5 flex channels + IMU
#define SENSOR_MODE_SINGLE_CH   1   // Phase 2 test mode: Thumb sensor (GPIO32) only

// ============================================================
// MPU6050 (IMU) CONFIGURATION
// ============================================================
#define MPU6050_SDA_PIN  21
#define MPU6050_SCL_PIN  22

// Common I2C addresses for MPU6050:
//   0x68 — AD0 pin LOW (default)
//   0x69 — AD0 pin HIGH
#define MPU6050_ADDRESS_PRIMARY   0x68
#define MPU6050_ADDRESS_SECONDARY 0x69
#define MPU6050_ADDRESS           MPU6050_ADDRESS_PRIMARY

// ============================================================
// LED FEEDBACK
// ============================================================
#define LED_PIN          18

// LED blink duration for gesture recognition feedback (ms)
#define LED_BLINK_DURATION_MS 200

// ============================================================
// BUZZER FEEDBACK (PASSIVE BUZZER MODULE)
// ============================================================
// Your hardware has a 3-pin Passive Buzzer Module Board.
// Because it is a module with an onboard switching transistor (e.g. S8550/S8050),
// it is safe to connect directly to an ESP32 GPIO pin.
//
// Passive buzzers require an audio PWM frequency/tone (1-3 kHz) to vibrate.
// Wiring:
//   VCC (+)  → ESP32 3.3V (or VIN)
//   GND (-)  → ESP32 GND
//   I/O / S  → ESP32 GPIO19 (labeled D19)
//
// Enabled for passive buzzer hardware feedback on GPIO19:
#define BUZZER_ENABLED
#define BUZZER_PIN           19     // GPIO19 (D19, adjacent to GPIO18 LED pin)
#define BUZZER_TONE_FREQ     2000   // Audio frequency in Hz (2000 Hz = crisp, pleasant beep)
#define BUZZER_BEEP_MS       80     // Beep duration for gesture recognition (ms)

// ============================================================
// DATA OUTPUT FORMAT
// ============================================================
// Output modes for serial data:
//   0 = Human-readable (for Serial Monitor debugging)
//   1 = JSON (for Python backend communication)
#define OUTPUT_FORMAT_HUMAN  0
#define OUTPUT_FORMAT_JSON   1
#define OUTPUT_FORMAT        OUTPUT_FORMAT_JSON

#endif // CONFIG_H

