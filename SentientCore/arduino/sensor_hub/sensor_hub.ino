// =============================================================================
// AquaEye-Sentient — sensor_hub.ino
// =============================================================================
// Arduino sensor hub for the AquaEye-Sentient buoy system.
//
// Ported from AquaSound (2024-25) — Victory Anyalewechi's sensor_hub.ino.
// Original code verified to match serial_reader.py regex patterns exactly.
//
// Changes from AquaSound version:
//   1. Startup message updated to "AquaEye-Sentient Sensor Hub Starting..."
//   2. IMU/heading stub added in serial output block (commented out until
//      an IMU is fitted to the Arduino — see metadata_writer.py heading_deg)
//   3. File placed in SentientCore/arduino/sensor_hub/ (correct location)
//
// SERIAL OUTPUT FORMAT (one line per reading, 9600 baud):
//   TDS Voltage: X.XX V TDS Value: X.XX ppm Turbidity Voltage: X.XX V
//   [ Latitude: X.XXXXXX, Longitude: X.XXXXXX, Altitude: X meters ]  <- if GPS fix
//   [ Date: M/D/YY Time(UTC): H:MM:SS ]                               <- if GPS time valid
//   [ Heading: X.XX deg ]                                             <- FUTURE (IMU stub)
//
// KNOWN LIMITATIONS (do not change without a proper fix):
//   - TDS temperature is hardcoded at 25°C. Acceptable for lab bench testing.
//     For field deployment in the Aegean Sea (15–25°C range), connect a DS18B20
//     waterproof temperature probe to update the `temperature` variable in real time.
//   - GPS polling uses a blocking while-loop capped at wait_time=1000 ms.
//     This is acceptable given the ~1 s GPS sentence interval, but it means
//     the loop() body can take up to 1 s. Not an issue for the current 200 ms
//     turbidity averaging period.
//
// WIRING:
//   TDS sensor  → A1
//   Turbidity   → A0
//   GPS TX      → D2 (SoftwareSerial RX)
//   GPS RX      → D3 (SoftwareSerial TX)
//   [Future IMU → I2C: SDA=A4, SCL=A5]
// =============================================================================

#include <SoftwareSerial.h>
#include <TinyGPS++.h>

// ---------------------------------------------------------------------------
// TDS sensor
// ---------------------------------------------------------------------------
int TdsSensorPin = A1;
#define VREF 5.0
#define SCOUNT 30
int analogBuffer[SCOUNT];
int analogBufferTemp[SCOUNT];
int analogBufferIndex = 0;
float averageVoltage = 0, tdsValue = 0, temperature = 25;
bool tdsReady = false;
unsigned long tdsTimer = 0;

// ---------------------------------------------------------------------------
// Turbidity sensor
// ---------------------------------------------------------------------------
int turbidityInput = A0;
unsigned long turbidityD = 200;
int n = 100;
float turbidityVolt = 0, totalTurbidity = 0;
int turbiditySampleCount = 0;
bool turbidityReady = false;
unsigned long turbidityTimer = 0;

// ---------------------------------------------------------------------------
// GPS
// ---------------------------------------------------------------------------
SoftwareSerial gpsSerial(2, 3);
TinyGPSPlus gps;
unsigned long wait_time = 1000;


// ---------------------------------------------------------------------------
// Median filter for TDS noise rejection
// ---------------------------------------------------------------------------
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


// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(9600);
  gpsSerial.begin(9600);
  pinMode(turbidityInput, INPUT);
  pinMode(TdsSensorPin, INPUT);
  Serial.println("AquaEye-Sentient Sensor Hub Starting...");
}


// ---------------------------------------------------------------------------
// Main loop — non-blocking millis() based
// ---------------------------------------------------------------------------
void loop() {
  unsigned long currentMillis = millis();

  // TDS sampling every 40 ms — fills 30-sample circular buffer
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

  // Turbidity sampling every 200 ms, averaged over 100 samples
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

  // GPS decode — blocking up to wait_time ms (see KNOWN LIMITATIONS)
  unsigned long gpsStart = millis();
  while (gpsSerial.available() && millis() - gpsStart < wait_time) {
    gps.encode(gpsSerial.read());
  }

  // Print when both TDS and turbidity have a fresh reading
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

    // IMU / HEADING STUB — uncomment when a 9-DOF IMU is fitted (e.g. MPU-9250)
    // The serial_reader.py regex already handles this optional field.
    // Format must be exactly: " Heading: X.XX deg"
    //
    // #include <MPU9250.h>   // add at top of file
    // float headingDeg = imu.getHeading();   // replace with actual IMU call
    // Serial.print(" Heading: "); Serial.print(headingDeg, 2); Serial.print(" deg");

    Serial.println();
  }
}
