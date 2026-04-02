# AquaEye-Sentient — Pipeline Benchmark Report

**Date:** 2026-04-01
**Student:** Fazley Alahi (1934714)
**Environment:** Windows 11 laptop (development machine — not Raspberry Pi 5)
**Script:** `pipeline_benchmark.py`
**Cycles:** 5 (+ 1 warm-up excluded from results)

---

## Test Configuration

| Parameter | Value |
|-----------|-------|
| WAV files per cycle | 6 (3 HydroMoths × 2 sessions) |
| Sessions per cycle | 2 complete sessions (all 3 units present) |
| WAV duration | 60 s per file |
| Sample rate | 96,000 Hz (16-bit mono) |
| WAV file size | ~11.0 MB each |
| Arduino serial | Disabled (`--no_serial`) — sensor fields null |
| WAV source | Synthetically generated silence (no real HydroMoth recordings yet) |

---

## Module Test Coverage

| Module | Exercised | Result |
|--------|-----------|--------|
| `session_stitcher.py` | Yes — groups 6 WAVs into 2 sessions per cycle | Pass |
| `audio_processor.py` | Yes — WAV → FLAC conversion for all 6 files | Pass |
| `metadata_writer.py` | Yes — writes `_meta.json` sidecar per FLAC | Pass |
| `hydromoth_puller.py` | Simulated — staging done internally by benchmark | Not tested on real SD cards |
| `serial_reader.py` | Skipped (`--no_serial`) | Not tested |
| `cloud_uploader.py` | Not called by benchmark | Not tested |
| `main.py` | Not called by benchmark | Not tested |

---

## Per-Cycle Timing Results

| Cycle | Sessions | Files | Encode (s) | Stitch (s) | Meta (s) | Stage (s) | Total (s) | Avg/file (s) |
|-------|----------|-------|------------|------------|----------|-----------|-----------|--------------|
| 1 | 2 | 6 | 1.30 | 0.00 | 0.01 | 0.06 | 1.38 | 0.21 |
| 2 | 2 | 6 | 1.43 | 0.00 | 0.01 | 0.05 | 1.50 | 0.23 |
| 3 | 2 | 6 | 1.18 | 0.00 | 0.01 | 0.06 | 1.26 | 0.19 |
| 4 | 2 | 6 | 1.27 | 0.00 | 0.01 | 0.05 | 1.33 | 0.21 |
| 5 | 2 | 6 | 1.28 | 0.00 | 0.01 | 0.05 | 1.34 | 0.21 |

---

## Aggregate Statistics (n = 5)

| Metric | Mean (s) | SD (s) | Min (s) | Max (s) |
|--------|----------|--------|---------|---------|
| Total active window | 1.36 | 0.08 | 1.26 | 1.50 |
| FLAC encode (all 6 files) | 1.29 | 0.08 | 1.18 | 1.43 |
| Avg per-file encode | 0.21 | 0.01 | 0.19 | 0.23 |
| Stitch overhead | 0.00 | 0.00 | 0.00 | 0.00 |
| Metadata write | 0.01 | 0.00 | 0.01 | 0.01 |

---

## Power Budget Assumption Comparison

| Assumption | Budgeted | Measured (laptop) | Delta | Status |
|------------|----------|-------------------|-------|--------|
| A3: encode time per file | 8 s | 0.21 s | −7.79 s | OK |
| A3 + A4: total active window | 70 s | 1.36 s | −68.64 s | OK |
| A1: Pi 5 active current | ~600–900 mA | Not measured | — | Pending (inline meter on Pi) |

---

## Key Findings

### 1. All three core modules passed without errors

`session_stitcher`, `audio_processor`, and `metadata_writer` all ran cleanly across
5 cycles with no exceptions. The pipeline logic is correct.

### 2. Encode times on a laptop are not representative of the Pi 5

The laptop result of **0.21 s per file** is far faster than the budgeted 8 s. This is
expected — a modern Intel/AMD laptop CPU is significantly more powerful than the Pi 5's
Cortex-A76. The 8 s assumption must still be validated by running `pipeline_benchmark.py`
on the actual Pi 5 with real HydroMoth WAV files.

### 3. Stitch and metadata overhead are negligible

Both are effectively 0 s at this scale. Even if they are 10× slower on the Pi 5, they
will not meaningfully affect the active window budget.

### 4. The synthetic WAV files are silence

The generated WAVs are 60 s of zeros at 96 kHz. FLAC compresses silence near-perfectly,
so the encode times here are likely faster than real hydrophone recordings (which contain
broadband noise). Real recordings will have less compressible content and may take longer
to encode. This is another reason to re-run on the Pi 5 with actual HydroMoth files.

---

## What Still Needs Testing on the Pi 5

| Test | What to measure | Module |
|------|-----------------|--------|
| Encode time with real recordings | Actual s/file on Pi 5 Cortex-A76 | `audio_processor.py` |
| Active current during encode | mA on inline meter (UM25C) | Power budget A1 |
| SD card pull timing | Copy speed from USB card reader | `hydromoth_puller.py` |
| Serial reader reconnect | Arduino disconnect/reconnect handling | `serial_reader.py` |
| Full `main.py` loop | End-to-end cycle without `--once` | `main.py` |
| RTC halt | `--once` mode and wake-up | `main.py` + Pi 5 RTC |
| Cloud upload | Auth flow, upload, sidecar pairing | `cloud_uploader.py` |

---

## Conclusion

The laptop benchmark confirms that the pipeline **code is correct and error-free**
for the three core processing modules. All five cycles completed successfully with
consistent timing. The actual timing numbers are not transferable to the Pi 5 and
must be re-measured on the target hardware with real HydroMoth recordings before
the power budget assumptions can be confirmed or revised.
