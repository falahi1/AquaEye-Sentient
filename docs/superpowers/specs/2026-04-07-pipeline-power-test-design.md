# Design Spec — Pipeline Power Test with Simulated HydroMoth Audio

**Date:** 2026-04-07
**Author:** Fazley Alahi
**Status:** Approved

---

## 1. Goal

Validate the full AquaEye-Sentient processing pipeline (stitch → FLAC encode → mock upload) on the Raspberry Pi 5 using simulated HydroMoth audio files, while measuring real power consumption with a USB inline multimeter. The generated audio files are also designed for future HydroMoth calibration.

---

## 2. Scope

**In scope:**
- Audio file generation on Windows (simulate 3 HydroMoths × 3 sessions)
- File transfer to Pi via SCP
- Full pipeline run: stitch → encode → mock upload
- Power measurement at each pipeline stage
- Frequency table CSV for future HydroMoth calibration

**Out of scope:**
- SD card pull step (bypassed — files placed directly in staging)
- Google Drive upload (mocked — `GOOGLE_DRIVE_FOLDER_ID = ""`)
- HydroMoth hardware (not yet available)

---

## 3. Hardware Setup

| Component | Detail |
|-----------|--------|
| Processing unit | Raspberry Pi 5 |
| Arduino | Arduino Nano via USB (`/dev/ttyUSB0`, ch341-uart converter) |
| Sensors | DS18B20 (D2), GPS (D3/D4), Turbidity (A0), TDS (A1) |
| GPS note | Indoors — no fix expected, `None` values in metadata are normal |
| Power measurement | USB inline multimeter (reads V, A, W) between Pi power supply and Pi |

---

## 4. Audio File Generation (Windows)

### 4.1 Script

`generate_test_audio.py` — runs on Windows, generates all output files.

**Dependencies:** `numpy`, `scipy`, `soundfile`

### 4.2 File Specification

| Parameter | Value |
|-----------|-------|
| Sample rate | 96,000 Hz (HydroMoth spec) |
| Bit depth | 16-bit PCM |
| Channels | Mono |
| Duration | 10 minutes per file |
| Format | WAV |

### 4.3 Audio Content Structure

Each file contains three sections:

| Time | Content | Purpose |
|------|---------|---------|
| 0:00 – 1:00 | Silence + low-level white noise | Ambient noise baseline |
| 1:00 – 6:00 | Linear frequency sweep 20 Hz → 48 kHz | Calibration reference |
| 6:00 – 10:00 | Synthesised cetacean signals | Realism (FM whistles 2–20 kHz + broadband clicks) |

### 4.4 Session and File Layout

3 sessions × 3 HydroMoths = **9 WAV files** total.

Files are named to match the staging format expected by `session_stitcher.py`:

```
HM_A__20260407_100000.WAV   HM_B__20260407_100002.WAV   HM_C__20260407_100003.WAV
HM_A__20260407_101000.WAV   HM_B__20260407_101002.WAV   HM_C__20260407_101003.WAV
HM_A__20260407_102000.WAV   HM_B__20260407_102002.WAV   HM_C__20260407_102003.WAV
```

HM_B and HM_C timestamps are offset +2 s and +3 s from HM_A within each session — within the 5-second `STITCH_TOLERANCE_SEC` so they group correctly.

### 4.5 Per-Unit Variation

Each file within a session has:
- Same frequency content
- ±1 dB amplitude variation to simulate each unit recording from a different angle

### 4.6 Calibration Output

`frequency_table.csv` — generated alongside the WAV files.

| Column | Description |
|--------|-------------|
| `time_sec` | Seconds from start of file |
| `freq_hz` | Frequency present at that moment during the sweep section |

Used later: play audio through waterproof speaker underwater, record with HydroMoth, compare captured spectrogram against this table.

---

## 5. File Transfer to Pi

From Windows (Git Bash):

```bash
# Transfer pipeline code
scp -r SentientCore/raspberry_pi/ pi@<PI_IP>:/home/pi/aquaeye/

# Transfer generated WAV files to staging (bypasses SD card pull)
scp -r test_audio/ pi@<PI_IP>:/home/pi/aquaeye/staging/
```

Files land directly in `/home/pi/aquaeye/staging/` — `hydromoth_puller.py` is not called.

---

## 6. Pi Configuration

One change to `config.py` before running:

```python
GOOGLE_DRIVE_FOLDER_ID = ""   # disables upload step
```

Everything else in `config.py` runs as-is. `hub_controller` will log a warning when no SD cards are found — this is expected and non-fatal.

---

## 7. Power Measurement Procedure

USB multimeter is placed inline between the Pi's USB-C power supply and the Pi. Read the **A** value and multiply by 1000 for mA.

### Stages to measure

| Stage | What's happening | When to read |
|-------|-----------------|--------------|
| Idle + sensors | Pi booted, Arduino streaming, no processing | Before running `main.py` |
| Stitching | Session grouping (CPU light, brief) | Watch terminal for "Stitch" log lines |
| FLAC encode | 9 files encoded sequentially (CPU peak) | Watch terminal for "Encoded" log lines — sustained reading |
| Post-encode idle | Processing done, sleeping until next cycle | After last "Encoded" line |

### Reading method

Take 5 readings per stage, record the mean. Enter results into `phase4_power_log.md` and `run_power_validation.py`.

### Knowing which stage is active

Watch the terminal output from `main.py` — each stage logs clearly:

```
INFO  main: Stitch — 3 session(s) to process         ← stitching
INFO  main: Encoded HM_A__20260407_100000.WAV → ...  ← encoding (watch multimeter)
INFO  main: Sleeping 60 s until next cycle ...        ← idle
```

---

## 8. Expected Pipeline Behaviour

1. `main.py` starts → Arduino connects on `/dev/ttyUSB0`
2. Hub power-on attempted → no SD cards found → warning logged → continues
3. Stitcher groups 9 WAV files into 3 sessions (3 files each, all complete)
4. FLAC encoder processes 9 files sequentially
5. Metadata sidecars written with sensor data (temp, turbidity, TDS; GPS null indoors)
6. Upload step skipped (empty folder ID)
7. Pipeline sleeps 60 seconds, then cycles again (no new files → nothing to process)

---

## 9. D.2 Modelled vs Measured Comparison

After measurements, fill `MEASURED_mA` in `run_power_validation.py` and run:

```bash
python run_power_validation.py
```

Output: modelled vs measured current table + corrected deployment duration.

| State | D.2 Modelled (mA) |
|-------|------------------|
| Pi active — FLAC encode (peak) | 1200 |
| Pi active — SD card pull | 900 |
| Pi active — Wi-Fi upload | 1000 |
| Pi RTC sleep | 30 |
| Arduino steady-state | 50 |

---

## 10. Future Use — HydroMoth Calibration

The generated WAV files serve a second purpose beyond pipeline testing:

1. Play the audio through a waterproof speaker in a tank or pool
2. Record with the HydroMoth at the same depth
3. Compare the HydroMoth's captured spectrogram against `frequency_table.csv`
4. The sweep section (1:00–6:00) shows exactly which frequencies the HydroMoth captured and at what level — direct frequency response characterisation
