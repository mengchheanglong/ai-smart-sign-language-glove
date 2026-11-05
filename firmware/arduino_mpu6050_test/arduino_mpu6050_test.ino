
#include <Arduino.h>

#define BUZZER_PIN 25

void setup() {
  Serial.begin(115200);

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  Serial.println("BUZZER TEST");
}

void loop() {
  Serial.println("BUZZER ON");
  digitalWrite(BUZZER_PIN, HIGH);
  delay(500);

  Serial.println("BUZZER OFF");
  digitalWrite(BUZZER_PIN, LOW);
  delay(1000);
}
