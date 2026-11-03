/*
 * test_flex_led.cpp — Standalone Flex Sensor & LED Benchmark Test
 * 
 * AI Smart Sign Language Glove — Team 2
 */

#include <Arduino.h>

// Pin Configuration
#define FLEX_PIN 34   // Change to 32 if plugged into GPIO32 (Thumb)
#define LED_PIN  18   // Feedback LED on GPIO18

// Adjust this threshold after checking Serial Monitor (e.g. midpoint between flat and bent)
int threshold = 2000;

void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // ESP32 ADC: 12-bit resolution (0 - 4095)
  analogReadResolution(12);

  delay(500);
  Serial.println("\n==========================================");
  Serial.println("  Flex Sensor + LED Standalone Test Sketch");
  Serial.printf("  Reading GPIO%d | LED on GPIO%d\n", FLEX_PIN, LED_PIN);
  Serial.printf("  Threshold: %d\n", threshold);
  Serial.println("==========================================");
}

void loop() {
  int flexValue = analogRead(FLEX_PIN);

  Serial.print("Flex Sensor Value: ");
  Serial.print(flexValue);

  if (flexValue > threshold) {
    digitalWrite(LED_PIN, HIGH);
    Serial.println("  ->  [BENT] LED ON");
  } 
  else {
    digitalWrite(LED_PIN, LOW);
    Serial.println("  ->  [STRAIGHT] LED OFF");
  }

  delay(200);
}
