#include <Arduino.h>
#include <Wire.h>
#include <Preferences.h>
#include "config.h"

// Every application-level output is a telemetry JSON line. Commands are newline
// terminated: straight, bent, clear, buzzer. Calibration takes 100 samples (about 10 seconds).
Preferences prefs;
float filtered[5] = {}, straight[5] = {}, bent[5] = {};
bool calibrated[5] = {}, filterReady = false, imuValid = false;
int states[5] = {}, raw[5] = {};
float accel[3] = {}, gyro[3] = {};
unsigned long lastSample = 0, lastImuProbe = 0, buzzerUntil = 0;
String command;
int capture = 0, captureCount = 0;
float sums[5] = {}, candidateStraight[5] = {};
int captureSpread[5] = {};
float captureRange[5] = {};
int captureResult[5] = {};  // 0 = pending, 1 = passed, 2 = failed
int lows[5], highs[5];
bool straightReady = false, straightStable[5] = {};
const int captureSamples = 100;
const float minRange = 50.0f;
const int maxSpread = 120;
const int fourthSensorMaxSpread = 200;  // Fourth channel has higher observed variation.

bool initImu() {
  // Wake the sensor and explicitly select the ranges used by readImu().
  // A reset of the ESP32 alone does not necessarily reset the MPU6050.
  const uint8_t registers[] = {0x6b, 0x1c, 0x1b};
  for (uint8_t reg : registers) {
    Wire.beginTransmission(MPU6050_ADDRESS_PRIMARY);
    Wire.write(reg); Wire.write(reg == 0x1c ? 0x10 : 0);
    if (Wire.endTransmission() != 0) return false;
  }
  return true;
}
bool readImu() {
  Wire.beginTransmission(MPU6050_ADDRESS_PRIMARY); Wire.write(0x3b);
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom((int)MPU6050_ADDRESS_PRIMARY, 14, (int)true) != 14) return false;
  int16_t values[7];
  for (int i = 0; i < 7; i++) values[i] = (int16_t)((Wire.read() << 8) | Wire.read());
  const float offsetG[3] = {-0.16923984f, -5.58236706f, -0.12171183f};
  // Bias measured with this glove stationary; experimental, device-specific.
  const float gyroBias[3] = {-1.0446f, -8.6418f, -0.3048f};
  for (int i = 0; i < 3; i++) { accel[i] = (values[i] / 4096.0f - offsetG[i]) * 9.80665f; gyro[i] = values[i + 4] / 131.0f - gyroBias[i]; }
  return true;
}
int readImuRegister(uint8_t reg) {
  Wire.beginTransmission(MPU6050_ADDRESS_PRIMARY); Wire.write(reg);
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom((int)MPU6050_ADDRESS_PRIMARY, 1, (int)true) != 1) return -1;
  return Wire.read();
}
void imuDiagnostic() {
  int who = readImuRegister(0x75), power = readImuRegister(0x6b);
  int original = readImuRegister(0x1c), gyroConfig = readImuRegister(0x1b);
  Serial.printf("{\"diagnostic\":\"imu_config\",\"whoami\":%d,\"power\":%d,\"accel_config\":%d,\"gyro_config\":%d}\n", who, power, original, gyroConfig);
  if (original < 0) return;
  for (int range = 0; range < 4; range++) {
    Wire.beginTransmission(MPU6050_ADDRESS_PRIMARY); Wire.write(0x1c); Wire.write((original & ~0x18) | (range << 3));
    if (Wire.endTransmission() != 0) break;
    delay(100);
    Wire.beginTransmission(MPU6050_ADDRESS_PRIMARY); Wire.write(0x3b);
    if (Wire.endTransmission(false) != 0 || Wire.requestFrom((int)MPU6050_ADDRESS_PRIMARY, 6, (int)true) != 6) break;
    int16_t rawAxis[3];
    for (int i=0; i<3; i++) { int hi = Wire.read(); int lo = Wire.read(); rawAxis[i] = (int16_t)((hi << 8) | lo); }
    Serial.printf("{\"diagnostic\":\"imu_range\",\"range_g\":%d,\"config\":%d,\"raw\":[%d,%d,%d]}\n", 2 << range, readImuRegister(0x1c), rawAxis[0], rawAxis[1], rawAxis[2]);
  }
  Wire.beginTransmission(MPU6050_ADDRESS_PRIMARY); Wire.write(0x1c); Wire.write(original); Wire.endTransmission();
}
void imuSample() {
  int original = readImuRegister(0x1c);
  if (original < 0) { Serial.println("{\"diagnostic\":\"sample_error\"}"); return; }
  Wire.beginTransmission(MPU6050_ADDRESS_PRIMARY); Wire.write(0x1c); Wire.write((original & ~0x18) | 0x10);
  if (Wire.endTransmission() != 0) { Serial.println("{\"diagnostic\":\"sample_error\"}"); return; }
  delay(100);
  long sum[3] = {}; int16_t low[3] = {32767,32767,32767}, high[3] = {-32768,-32768,-32768}; int count = 0;
  for (int n=0;n<100;n++) {
    Wire.beginTransmission(MPU6050_ADDRESS_PRIMARY); Wire.write(0x3b);
    if (Wire.endTransmission(false) != 0 || Wire.requestFrom((int)MPU6050_ADDRESS_PRIMARY, 6, (int)true) != 6) break;
    for (int i=0;i<3;i++) { int hi=Wire.read(), lo=Wire.read(); int16_t v=(int16_t)((hi<<8)|lo); sum[i]+=v; low[i]=min(low[i],v); high[i]=max(high[i],v); }
    count++; delay(50);
  }
  Wire.beginTransmission(MPU6050_ADDRESS_PRIMARY); Wire.write(0x1c); Wire.write(original); Wire.endTransmission();
  Serial.printf("{\"diagnostic\":\"imu_sample\",\"count\":%d,\"sum\":[%ld,%ld,%ld],\"low\":[%d,%d,%d],\"high\":[%d,%d,%d]}\n",count,sum[0],sum[1],sum[2],low[0],low[1],low[2],high[0],high[1],high[2]);
}
void saveCalibration(int i) {
  char key[8]; snprintf(key, sizeof(key), "s%d", i); prefs.putFloat(key, straight[i]);
  snprintf(key, sizeof(key), "b%d", i); prefs.putFloat(key, bent[i]);
  snprintf(key, sizeof(key), "v%d", i); prefs.putBool(key, calibrated[i]);
}
void beginCapture(int mode) {
  if (capture || (mode == 2 && !straightReady)) return;
  capture = mode; captureCount = 0;
  for (int i = 0; i < 5; i++) { sums[i] = 0; lows[i] = 4095; highs[i] = 0; captureSpread[i] = 0; captureRange[i] = 0; captureResult[i] = 0; }
}
void processCommand(String cmd) {
  cmd.trim(); cmd.toLowerCase();
  if (cmd == "imu_diag") imuDiagnostic();
  else if (cmd == "imu_sample") imuSample();
  else if (cmd == "straight") beginCapture(1);
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
    captureSpread[i] = highs[i] - lows[i];
    bool stable = captureSpread[i] <= (i == 3 ? fourthSensorMaxSpread : maxSpread) && lows[i] > 20 && highs[i] < 4075;
    float average = sums[i] / captureSamples;
    if (capture == 1) {
      candidateStraight[i] = average;
      straightStable[i] = stable;
      captureResult[i] = stable ? 1 : 2;
    } else {
      captureRange[i] = fabsf(average - candidateStraight[i]);
      bool valid = straightStable[i] && stable && captureRange[i] >= minRange;
      captureResult[i] = valid ? 1 : 2;
      if (valid && i < ACTIVE_FLEX_SENSORS) {
        straight[i] = candidateStraight[i]; bent[i] = average;
        calibrated[i] = true; states[i] = 0; saveCalibration(i);
      }
    }
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
  Serial.print("],\"capture_spread\":[");
  for (int i=0;i<5;i++) { if(i) Serial.print(','); Serial.print(capture && captureCount ? highs[i]-lows[i] : captureSpread[i]); }
  Serial.print("],\"capture_range\":[");
  for (int i=0;i<5;i++) { if(i) Serial.print(','); Serial.print(capture == 2 && captureCount ? fabsf(sums[i]/captureCount-candidateStraight[i]) : captureRange[i],1); }
  Serial.print("],\"capture_result\":[");
  for (int i=0;i<5;i++) { if(i) Serial.print(','); Serial.print(captureResult[i]); }
  Serial.printf("],\"capture\":\"%s\",\"capture_count\":%d,\"capture_total\":100,\"straight_ready\":%s,\"imu_valid\":%s,\"imu_experimental\":true,\"accel\":", capture==1 ? "straight" : capture==2 ? "bent" : "idle",captureCount,straightReady ? "true" : "false",imuValid ? "true" : "false");
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
