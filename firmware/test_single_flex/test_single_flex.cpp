/*
 * ESP32 Gesture Recognition Glove
 * Lesson 1: ESP32 Flex Sensor Diagnostic Benchmark
 *
 * Checks GPIO32 (with mV conversion) AND monitors all ADC1 channels
 * (GPIO32, 33, 34, 35, 36) to pinpoint any pin mapping or wiring discrepancy.
 */

#include <Arduino.h>

const int PINS[5] = {32, 33, 34, 35, 36};
const char* NAMES[5] = {"GPIO32", "GPIO33", "GPIO34", "GPIO35", "GPIO36(VP)"};

void setup() {
  Serial.begin(115200);

  // Proper ADC configuration for ESP32 Arduino Core 3.x
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db); // Full 0 - 3.3V range

  for (int i = 0; i < 5; i++) {
    pinMode(PINS[i], INPUT);
  }

  delay(1000);
  Serial.println("\n=======================================================");
  Serial.println("  ESP32 ADC Multi-Pin Diagnostic Monitor");
  Serial.println("=======================================================");
  Serial.println("TEST TIP: Touch the signal wire to 3.3V -> value jumps to ~4095");
  Serial.println("-------------------------------------------------------\n");
}

void loop() {
  int raw32 = analogRead(32);
  int mv32  = analogReadMilliVolts(32);

  Serial.printf("--> GPIO32: %4d (%4d mV) | All ADC1: [32]=%d, [33]=%d, [34]=%d, [35]=%d, [36]=%d\n",
    raw32, mv32, raw32, analogRead(33), analogRead(34), analogRead(35), analogRead(36));

  delay(40); // 25 Hz update rate for responsive real-time UI feedback
}
