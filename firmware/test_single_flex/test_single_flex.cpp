/*
 * AI Smart Sign Language Glove
 * Lesson 1: ESP32 + One Flex Sensor
 *
 * Wiring:
 * 3.3V -> Flex Sensor -> GPIO32
 * GPIO32 -> 10k resistor -> GND
 */

#include <Arduino.h>

const int flexPin = 32;

void setup() {
  Serial.begin(115200);

  // ESP32 uses 12-bit ADC readings
  analogReadResolution(12);

  delay(1000);

  Serial.println("ESP32 Flex Sensor Test");
  Serial.println("--------------------");
}

void loop() {

  // Read flex sensor value
  int flexValue = analogRead(flexPin);

  // Display value
  Serial.print("Flex Sensor Value: ");
  Serial.println(flexValue);

  delay(200);
}
