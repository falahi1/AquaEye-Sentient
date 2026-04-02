// Source: ME5660-EE5098 Group Report — AquaSound (2024-25)
// Author: Victory Anyalewechi (1945112)
// Extracted from: Appendix / code listings in the AquaSound group and individual reports
// Preserved as-is. No modifications.

#include <SoftwareSerial.h>
#include <TinyGPS++.h>

// TDS sensor
int TdsSensorPin = A1;
#define VREF 5.0
#define SCOUNT 30
int analogBuffer[SCOUNT];
int analogBufferTemp[SCOUNT];
int analogBufferIndex = 0;
float averageVoltage = 0, tdsValue = 0, temperature = 25;
bool tdsReady = false;
unsigned long tdsTimer = 0;

// Turbidity sensor
int turbidityInput = A0;
unsigned long turbidityD = 200;
int n = 100;
float turbidityVolt = 0, totalTurbidity = 0;
int turbiditySampleCount = 0;
bool turbidityReady = false;
unsigned long turbidityTimer = 0;

// GPS
SoftwareSerial gpsSerial(2, 3);
TinyGPSPlus gps;
unsigned long wait_time = 1000;


int getMedianNum(int bArray[], int iFilterLen) {
  int bTab[iFilterLen];
  for (byte i = 0; i < iFilterLen; i++) bTab[i] = bArray[i];
  int i, j, bTemp;
  for (j = 0; j < iFilterLen - 1; j++) {
    for (i = 0; i < iFilterLen - j - 1; i++) {
      if (bTab[i] > bTab[i + 1]) {
        bTemp = bTab[i];
        bTab[i] = bTab[i + 1];
        bTab[i + 1] = bTemp;
      }
    }
  }
  if ((iFilterLen & 1) > 0) bTemp = bTab[(iFilterLen - 1) / 2];
  else bTemp = (bTab[iFilterLen / 2] + bTab[iFilterLen / 2 - 1]) / 2;
  return bTemp;
}


void setup() {
  Serial.begin(9600);
  gpsSerial.begin(9600);
  pinMode(turbidityInput, INPUT);
  pinMode(TdsSensorPin, INPUT);
  Serial.println("AquaSound Sensor Hub Starting...");
}


void loop() {
  unsigned long currentMillis = millis();

  // TDS sampling every 40ms
  if (currentMillis - tdsTimer > 40) {
    tdsTimer = currentMillis;
    analogBuffer[analogBufferIndex] = analogRead(TdsSensorPin);
    analogBufferIndex++;
    if (analogBufferIndex == SCOUNT) analogBufferIndex = 0;

    memcpy(analogBufferTemp, analogBuffer, sizeof(analogBuffer));
    averageVoltage = getMedianNum(analogBufferTemp, SCOUNT) * (float)VREF / 1024.0;
    float compensationCoefficient = 1.0 + 0.02 * (temperature - 25.0);
    float compensationVoltage = averageVoltage / compensationCoefficient;
    tdsValue = (133.42 * compensationVoltage * compensationVoltage * compensationVoltage
                - 255.86 * compensationVoltage * compensationVoltage
                + 857.39 * compensationVoltage) * 0.5;
    tdsReady = true;
  }

  // Turbidity sampling every 200ms, average 100 samples
  if (currentMillis - turbidityTimer > turbidityD) {
    turbidityTimer = currentMillis;
    totalTurbidity += analogRead(turbidityInput);
    turbiditySampleCount++;
    if (turbiditySampleCount >= n) {
      turbidityVolt = (totalTurbidity / n) * (5.0 / 1023.0);
      totalTurbidity = 0;
      turbiditySampleCount = 0;
      turbidityReady = true;
    }
  }

  // GPS decode
  unsigned long gpsStart = millis();
  while (gpsSerial.available() && millis() - gpsStart < wait_time) {
    gps.encode(gpsSerial.read());
  }

  // Print when both sensors ready
  if (tdsReady && turbidityReady) {
    tdsReady = false;
    turbidityReady = false;

    Serial.print("TDS Voltage: "); Serial.print(averageVoltage, 2);
    Serial.print(" V TDS Value: "); Serial.print(tdsValue, 2);
    Serial.print(" ppm Turbidity Voltage: "); Serial.print(turbidityVolt, 2); Serial.print(" V");

    if (gps.location.isValid()) {
      Serial.print(" Latitude: "); Serial.print(gps.location.lat(), 6);
      Serial.print(", Longitude: "); Serial.print(gps.location.lng(), 6);
      Serial.print(", Altitude: "); Serial.print(gps.altitude.meters()); Serial.print(" meters");
    }

    if (gps.date.isValid() && gps.time.isValid()) {
      Serial.print(" Date: ");
      Serial.print(gps.date.month()); Serial.print("/");
      Serial.print(gps.date.day()); Serial.print("/");
      Serial.print(gps.date.year() % 100);
      Serial.print(" Time(UTC): ");
      Serial.print(gps.time.hour()); Serial.print(":");
      Serial.print(gps.time.minute()); Serial.print(":");
      Serial.print(gps.time.second());
    }

    Serial.println();
  }
}
