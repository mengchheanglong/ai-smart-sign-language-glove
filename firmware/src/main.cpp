#include <Arduino.h>
#include <Wire.h>
#include <Preferences.h>
#include "config.h"

// Every application-level output is a telemetry JSON line. Commands are newline
// terminated: straight, bent, clear, buzzer. Calibration takes 50 samples.
Preferences prefs;
float filtered[5] = {}, straight[5] = {}, bent[5] = {};
bool calibrated[5] = {}, filterReady = false, imuValid = false;
int states[5] = {}, raw[5] = {};
float accel[3] = {}, gyro[3] = {};
unsigned long lastSample = 0, lastImuProbe = 0, buzzerUntil = 0;
String command;
int capture = 0, captureCount = 0;
float sums[5] = {};
int lows[5], highs[5];
bool straightReady = false, straightStable[5] = {};
const int captureSamples = 50;
const float minRange = 50.0f;
const int maxSpread = 120;

bool initImu() {
  // Wake the sensor and explicitly select the ranges used by readImu().
  // A reset of the ESP32 alone does not necessarily reset the MPU6050.
  const uint8_t registers[] = {0x6b, 0x1c, 0x1b};
  for (uint8_t reg : registers) {
    Wire.beginTransmission(MPU6050_ADDRESS_PRIMARY);
    Wire.write(reg); Wire.write(0);
    if (Wire.endTransmission() != 0) return false;
  }
  return true;
}
bool readImu() {
  Wire.beginTransmission(MPU6050_ADDRESS_PRIMARY); Wire.write(0x3b);
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom((int)MPU6050_ADDRESS_PRIMARY, 14, (int)true) != 14) return false;
  int16_t values[7];
  for (int i = 0; i < 7; i++) values[i] = (int16_t)((Wire.read() << 8) | Wire.read());
  for (int i = 0; i < 3; i++) { accel[i] = values[i] * (9.80665f / 16384.0f); gyro[i] = values[i + 4] / 131.0f; }
  return true;
}
void saveCalibration(int i) {
  char key[8]; snprintf(key, sizeof(key), "s%d", i); prefs.putFloat(key, straight[i]);
  snprintf(key, sizeof(key), "b%d", i); prefs.putFloat(key, bent[i]);
  snprintf(key, sizeof(key), "v%d", i); prefs.putBool(key, calibrated[i]);
}
void beginCapture(int mode) {
  if (capture || (mode == 2 && !straightReady)) return;
  capture = mode; captureCount = 0;
  for (int i = 0; i < 5; i++) { sums[i] = 0; lows[i] = 4095; highs[i] = 0; }
}
void processCommand(String cmd) {
  cmd.trim(); cmd.toLowerCase();
  if (cmd == "straight") beginCapture(1);
  else if (cmd == "bent") beginCapture(2);
  else if (cmd == "clear") {
    capture = 0; straightReady = false;
    for (int i = 0; i < 5; i++) { calibrated[i] = false; straight[i] = bent[i] = 0; saveCalibration(i); }
  } else if (cmd == "buzzer" || cmd == "z" || cmd.indexOf("\"buzzer\"") >= 0) {
    tone(BUZZER_PIN, BUZZER_TONE_FREQ); buzzerUntil = millis() + BUZZER_BEEP_MS;
  }
}
void captureSample() {
  if (!capture) return;
  for (int i = 0; i < 5; i++) { sums[i] += raw[i]; lows[i] = min(lows[i], raw[i]); highs[i] = max(highs[i], raw[i]); }
  if (++captureCount < captureSamples) return;
  for (int i = 0; i < 5; i++) {
    bool stable = highs[i] - lows[i] <= maxSpread && lows[i] > 20 && highs[i] < 4075;
    if (capture == 1) { straight[i] = sums[i] / captureSamples; straightStable[i] = stable; calibrated[i] = false; saveCalibration(i); }
    else { bent[i] = sums[i] / captureSamples; calibrated[i] = straightStable[i] && stable && fabsf(bent[i] - straight[i]) >= minRange; saveCalibration(i); states[i] = 0; }
  }
  if (capture == 1) straightReady = true;
  capture = 0;
}
void outputPacket() {
  Serial.printf("{\"timestamp_ms\":%lu,\"flex\":[", millis());
  for (int i=0;i<5;i++) { if(i) Serial.print(','); Serial.print((int)filtered[i]); }
  Serial.print("],\"enabled\":[true,true,true,true,false],\"calibrated\":[");
  for (int i=0;i<5;i++) { if(i) Serial.print(','); Serial.print(i < ACTIVE_FLEX_SENSORS && calibrated[i] ? "true" : "false"); }
  Serial.print("],\"straight\":[");
  for (int i=0;i<5;i++) { if(i) Serial.print(','); Serial.print(straight[i],1); }
  Serial.print("],\"bent\":[");
  for (int i=0;i<5;i++) { if(i) Serial.print(','); Serial.print(bent[i],1); }
  Serial.print("],\"bend_pct\":[");
  for (int i=0;i<5;i++) {
    if(i) Serial.print(',');
    if (i >= ACTIVE_FLEX_SENSORS || !calibrated[i]) { Serial.print("null"); continue; }
    float pct = constrain((filtered[i]-straight[i])/(bent[i]-straight[i])*100.0f,0.0f,100.0f);
    if (states[i]==0 && pct>=30) states[i]=pct>=70 ? 2 : 1;
    else if (states[i]==1 && pct<=20) states[i]=0;
    else if (states[i]==1 && pct>=70) states[i]=2;
    else if (states[i]==2 && pct<=60) states[i]=pct<=20 ? 0 : 1;
    Serial.print(pct,1);
  }
  Serial.print("],\"bend_state\":[");
  for (int i=0;i<5;i++) { if(i) Serial.print(','); Serial.printf("\"%s\"", i >= ACTIVE_FLEX_SENSORS ? "DISCONNECTED" : !calibrated[i] ? "UNCALIBRATED" : states[i]==0 ? "STRAIGHT" : states[i]==1 ? "HALF-BENT" : "BENT"); }
  Serial.printf("],\"capture\":\"%s\",\"capture_count\":%d,\"straight_ready\":%s,\"imu_valid\":%s,\"accel\":", capture==1 ? "straight" : capture==2 ? "bent" : "idle",captureCount,straightReady ? "true" : "false",imuValid ? "true" : "false");
  if (!imuValid) Serial.print("null,\"gyro\":null}");
  else Serial.printf("[%.3f,%.3f,%.3f],\"gyro\":[%.3f,%.3f,%.3f]}",accel[0],accel[1],accel[2],gyro[0],gyro[1],gyro[2]);
  Serial.println();
}
void setup() {
  Serial.begin(SERIAL_BAUD_RATE); analogReadResolution(12);
  for (int i=0;i<ACTIVE_FLEX_SENSORS;i++) { pinMode(FLEX_PINS[i], INPUT); analogSetPinAttenuation(FLEX_PINS[i], ADC_11db); }
  pinMode(BUZZER_PIN, OUTPUT); Wire.begin(MPU6050_SDA_PIN, MPU6050_SCL_PIN); Wire.setTimeOut(25);
  prefs.begin("glove", false);
  for (int i=0;i<5;i++) { char key[8]; snprintf(key,sizeof(key),"s%d",i); straight[i]=prefs.getFloat(key,0); snprintf(key,sizeof(key),"b%d",i); bent[i]=prefs.getFloat(key,0); snprintf(key,sizeof(key),"v%d",i); calibrated[i]=prefs.getBool(key,false) && fabsf(bent[i]-straight[i])>=minRange; }
  imuValid=initImu();
}
void loop() {
  while (Serial.available()) { char c=Serial.read(); if(c=='\n') { processCommand(command); command=""; } else if(c!='\r' && command.length()<80) command+=c; }
  unsigned long now=millis();
  if (buzzerUntil && (long)(now-buzzerUntil)>=0) { noTone(BUZZER_PIN); buzzerUntil=0; }
  if (now-lastSample < SAMPLING_INTERVAL_MS) return;
  lastSample=now;
  for (int i=0;i<ACTIVE_FLEX_SENSORS;i++) { raw[i]=analogRead(FLEX_PINS[i]); filtered[i]=filterReady ? .35f*raw[i]+.65f*filtered[i] : raw[i]; }
  filterReady=true; captureSample();
  if (imuValid) imuValid=readImu();
  else if (now-lastImuProbe>=2000) { lastImuProbe=now; imuValid=initImu() && readImu(); }
  outputPacket();
}
