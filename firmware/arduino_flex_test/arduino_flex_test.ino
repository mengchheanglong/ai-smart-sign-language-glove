
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <math.h>

#define SDA_PIN 21
#define SCL_PIN 22
#define MPU_ADDR 0x68

Adafruit_MPU6050 mpu;

void setup() {
  Serial.begin(115200);
  delay(1500);

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(50000);

  Serial.println();
  Serial.println("MPU6050 HEALTH TEST");

  if (!mpu.begin(MPU_ADDR, &Wire)) {
    Serial.println("FAILED: MPU6050 not detected");
    while (true) delay(1000);
  }

  mpu.setAccelerometerRange(
    MPU6050_RANGE_8_G
  );

  mpu.setGyroRange(
    MPU6050_RANGE_500_DEG
  );

  mpu.setFilterBandwidth(
    MPU6050_BAND_21_HZ
  );

  Serial.println("Sensor connected.");
  Serial.println("Place sensor still on a table.");
}

void loop() {
  sensors_event_t a, g, temp;

  if (!mpu.getEvent(&a, &g, &temp)) {
    Serial.println("READ FAILED");
    delay(500);
    return;
  }

  float ax = a.acceleration.x / 9.80665f;
  float ay = a.acceleration.y / 9.80665f;
  float az = a.acceleration.z / 9.80665f;

  float total = sqrtf(
    ax * ax + ay * ay + az * az
  );

  float gx = g.gyro.x * RAD_TO_DEG;
  float gy = g.gyro.y * RAD_TO_DEG;
  float gz = g.gyro.z * RAD_TO_DEG;

  Serial.println("----------------------");

  Serial.printf("AX: %.2f g\n", ax);
  Serial.printf("AY: %.2f g\n", ay);
  Serial.printf("AZ: %.2f g\n", az);

  Serial.printf("TOTAL: %.2f g\n", total);

  Serial.printf(
    "GYRO: X=%.2f Y=%.2f Z=%.2f deg/s\n",
    gx, gy, gz
  );

  if (total >= 0.85f && total <= 1.15f) {
    Serial.println("GRAVITY TEST: PASS");
  } else {
    Serial.println("GRAVITY TEST: FAIL");
  }

  delay(500);
}
