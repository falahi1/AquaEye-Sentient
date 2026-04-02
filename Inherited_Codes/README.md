# Inherited Codes — Previous Project Cycles

This folder preserves the code from the two previous AquaEye project cycles
**exactly as found in the submitted project reports**. Nothing has been modified.

Do not edit these files. They are the reference baseline.
All active development happens in `Necessary_Codes/`.

---

## AquaEye_2023-24_Andia/

**Source:** ME5660 Individual Report — Andia Roumina (2023-24)
**Appendices:** C, D, E

| File | Appendix | Description |
|------|----------|-------------|
| `random_forest_classifier.py` | C | RFC with RandomizedSearchCV — best accuracy 83.02% |
| `gradient_boosting_classifier.py` | D | HistGradientBoosting — 82.39% |
| `knn_classifier.py` | E | kNN with k-sweep — 77.99% |

**Input:** `Species Data.csv` (12 Raven Pro acoustic features, classes: Dd / Sc / Tt)
**Output:** `Species predictions.csv`

---

## AquaSound_2024-25_Victory/

**Source:** ME5660-EE5098 Group Report — AquaSound (2024-25)
           + ME5660 Individual Report — Victory Anyalewechi (1945112)

### python/

| File | Description |
|------|-------------|
| `main_recording.py` | Full system: audio recording, FLAC compression, Google Drive upload, Arduino serial read |

Key parameters as submitted:
- Sample rate: 48,000 Hz
- Channels: 1 (mono)
- Bit depth: 16-bit
- Recording duration: 5 minutes
- Wait between recordings: 1 minute
- Serial port: `/dev/ttyACM0` @ 9600 baud
- Drive folder ID: `11QAYDOyePI-2t7yBnwD4fmWrq0ojsDI7`

### arduino/

| File | Description |
|------|-------------|
| `sensor_hub.ino` | Arduino C++: TDS (A1, median filter) + Turbidity (A0, 100-sample avg) + GPS (D2/D3, TinyGPS++) |

Serial output format:
```
TDS Voltage: X.XX V TDS Value: X.XX ppm Turbidity Voltage: X.XX V
Latitude: X.XXXXXX, Longitude: X.XXXXXX, Altitude: X meters
Date: M/D/YY Time(UTC): HH:MM:SS
```
