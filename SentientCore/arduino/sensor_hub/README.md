# AquaEye-Sentient — Arduino Sensor Hub

**Student:** Fazley Alahi (1934714)
**Cycle:** AquaEye-Sentient (2025-26)
**Target hardware:** Arduino Nano or Uno

This sketch runs on the Arduino inside the buoy and reads three environmental
sensors (TDS, turbidity, GPS). It prints a single line of data to serial every
~200 ms, which the Raspberry Pi's `serial_reader.py` ingests and forwards to
`metadata_writer.py` for inclusion in each recording's `_meta.json` sidecar.

---

## File

```
arduino/sensor_hub/
└── sensor_hub.ino      ← this sketch
```

---

## Wiring

| Sensor / Module | Arduino pin |
|-----------------|-------------|
| TDS sensor (signal) | A1 |
| Turbidity sensor (signal) | A0 |
| GPS TX (module → Arduino) | D2 (SoftwareSerial RX) |
| GPS RX (Arduino → module) | D3 (SoftwareSerial TX) |
| Future IMU (SDA) | A4 (I2C) |
| Future IMU (SCL) | A5 (I2C) |

All sensors run on 5 V. The GPS module used is the NEO-6M (9600 baud).

---

## Arduino IDE Setup

1. Open `sensor_hub.ino` in the Arduino IDE.
2. Install the required libraries via **Sketch → Include Library → Manage Libraries**:
   - `TinyGPS++` by Mikal Hart
   - `SoftwareSerial` (bundled with the IDE — no install needed)
3. Select your board: **Tools → Board → Arduino Nano** (or Uno).
4. Select the correct COM port under **Tools → Port**.
5. Upload.

---

## Serial Output Format

One line per reading at **9600 baud**, ~200 ms interval:

```
TDS Voltage: X.XX V TDS Value: X.XX ppm Turbidity Voltage: X.XX V[ Latitude: X.XXXXXX, Longitude: X.XXXXXX, Altitude: X meters][ Date: M/D/YY Time(UTC): H:MM:SS]
```

- GPS fields only appear when the module has a valid fix.
- A future `Heading: X.XX deg` field will appear once an IMU is fitted (stub already in code).
- The `serial_reader.py` regex patterns on the Raspberry Pi are written to match this format exactly — **do not change the output format without updating those regexes**.

---

## Known Limitations

| Limitation | Impact | Fix (if deployed in the field) |
|------------|--------|-------------------------------|
| TDS temperature hardcoded at 25 °C | ~2% error per °C deviation | Connect a DS18B20 waterproof probe and feed its reading into the `temperature` variable |
| GPS polling is blocking (up to 1 s) | `loop()` can take up to 1 s | Acceptable for current use; refactor to fully non-blocking if faster sensor rates are needed |

---

## Provenance

Ported from **AquaSound (2024-25)** — Victory Anyalewechi's `sensor_hub.ino`.
The serial output format and regex contract with `serial_reader.py` are inherited
unchanged. Only the startup message and section comments were updated for this cycle.
