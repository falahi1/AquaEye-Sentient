# Phase 4 Test Log — Power Consumption Measurement

**Date:** ___________
**Tester:** Fazley Alahi
**Multimeter model:** _____
**Measurement mode:** DC current (mA range)
**Supply voltage:** 5.0 V
**Setup:** Multimeter in series with positive supply line to Pi

**Method:** Take mean of ~5 readings over 10 seconds per state.

---

## Test 4.1 — Pi RTC Sleep State

| Reading | mA |
|---------|----|
| 1 |  |
| 2 |  |
| 3 |  |
| 4 |  |
| 5 |  |
| **Mean** | |

---

## Test 4.2 — Pi Active Processing States

### FLAC Encode (CPU-intensive — expected peak)

| Reading | mA |
|---------|----|
| 1 |  |
| 2 |  |
| 3 |  |
| 4 |  |
| 5 |  |
| **Mean** | |

### SD Card Pull / File Writes (I/O-bound)

| Reading | mA |
|---------|----|
| 1 |  |
| 2 |  |
| 3 |  |
| 4 |  |
| 5 |  |
| **Mean** | |

### Wi-Fi Transmission (cloud upload)

| Reading | mA |
|---------|----|
| 1 |  |
| 2 |  |
| 3 |  |
| 4 |  |
| 5 |  |
| **Mean** | |

---

## Test 4.3 — Arduino Sensor Hub (steady-state)

| Reading | mA |
|---------|----|
| 1 |  |
| 2 |  |
| 3 |  |
| 4 |  |
| 5 |  |
| **Mean** | |

---

## D.2 Comparison Summary

| State | D.2 Modelled (mA) | Measured mean (mA) | Error (%) |
|-------|------------------|-------------------|-----------|
| Pi active — FLAC encode (peak) |  |  |  |
| Pi active — SD card pull |  |  |  |
| Pi active — Wi-Fi upload |  |  |  |
| Pi RTC sleep |  |  |  |
| Arduino steady-state |  |  |  |

**Corrected deployment duration (from run_power_validation.py):** _____ days
**D.2 modelled deployment duration:** _____ days

---

## Notes / Anomalies
