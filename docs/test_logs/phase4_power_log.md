# Phase 4 Test Log — Power Consumption Measurement

**Date:** 2026-04-12
**Tester:** Fazley Alahi
**Multimeter model:** Inline USB power meter
**Measurement mode:** DC current (A, converted to mA below)
**Supply voltage:** 5.0 V
**Setup:** Inline USB power meter in series with Pi 5 power supply

**Method:** Readings taken from video recording of meter display at known
timestamps correlated with pipeline_benchmark.py log output.

---

## Test 4.1 — Pi RTC Sleep State

Command used: `sudo halt`

| Reading | mA |
|---------|----|
| 1 | 305 |
| **Mean** | **305** |

> **Note:** Pi 5 draws significantly more than expected in halted state.
> The RTC coin cell battery is fitted — this powers only the RTC chip
> separately and does not affect the main supply reading above.
> The 305 mA represents the Pi 5 main supply draw after `sudo halt`,
> with USB regulators and other subsystems partially live.
> This is ~10× the modelled value of 30 mA.

---

## Test 4.2 — Pi Active Processing States

### Mix Phase — CPU + file I/O (peak during FLAC encode)

Readings taken from video at timestamps during benchmark Mix START/END windows:

| Timestamp | mA |
|-----------|----|
| 12:43:19 (Cycle 1 mixing) | 1090 |
| 12:43:45 (Cycle 2 mixing) | 1030 |
| 12:43:56 (Cycle 2 mixing) | 1080 |
| 12:44:07 (Cycle 3 mixing) | 1045 |
| 12:44:08 (Cycle 3 mixing) | 1102 |
| 12:44:09 (Cycle 3 mixing) | 914 |
| 12:44:21 (Cycle 3 mixing) | 977 |
| 12:44:30 (Cycle 3 ending) | 1006 |
| **Mean** | **1031** |
| **Peak** | **1102** |

### SD Card Pull / Staging (I/O-bound)

| Timestamp | mA |
|-----------|----|
| 12:43:14 (end of warm-up staging) | 845 |
| **Mean** | **845** |

### Wi-Fi Transmission (cloud upload)

> **Not tested** — upload disabled in config.py for power test
> (`GOOGLE_DRIVE_FOLDER_ID = ""`). To be measured in a future session
> when Wi-Fi upload is re-enabled.

---

## Test 4.3 — Arduino Sensor Hub (steady-state)

Arduino Nano measured standalone via inline USB meter, disconnected from Pi.

| Reading | mA |
|---------|----|
| 1 | 85 |
| **Mean** | **85** |

---

## D.2 Comparison Summary

| State | D.2 Modelled (mA) | Measured (mA) | Error (%) |
|-------|------------------|---------------|-----------|
| Pi active — FLAC encode (peak) | 1200 | 1102 | -8.2% ✓ |
| Pi active — SD card pull | 900 | 845 | -6.1% ✓ |
| Pi active — Wi-Fi upload | 1000 | — | not tested |
| Pi RTC sleep | 30 | 305 | +916.7% ✗ |
| Arduino steady-state | 50 | 85 | +70.0% ✗ |

**D.2 modelled deployment duration:** 6.4 days (20,000 mAh battery)
**Corrected deployment duration (measured):** 2.0 days (20,000 mAh battery)

> Active window also corrected: 25.61 s measured vs 70 s modelled in D.2.

---

## Notes / Anomalies

### Critical finding: Pi 5 halt current

The Pi 5 draws 305 mA after `sudo halt` — approximately 10× the modelled
30 mA. This is a known characteristic of the Pi 5: unlike older Pi models,
the Pi 5 does not cut power to USB regulators and other subsystems on halt.
This single discrepancy reduces projected deployment duration from 6.4 days
to 2.0 days on a 20,000 mAh battery.

### Recommended mitigation: Relay/timer true-off circuit

To eliminate sleep current from the Pi entirely, a hardware power-cut
circuit should be interposed between the battery and the Pi 5:

```
Battery → RTC/Timer module → Relay/MOSFET → Pi 5
              ↓
         Arduino (always-on, 85 mA)
```

**Operation:**
- Arduino (or dedicated RTC module, e.g. DS3231) remains powered
  continuously at 85 mA
- At the scheduled wake interval (e.g. every 10 minutes), the
  Arduino/RTC pulses a relay or MOSFET gate
- Relay closes → Pi powers on, runs one full processing cycle (~26 s),
  then signals Arduino to cut power
- Relay opens → Pi is fully off (0 mA from main battery)

**Revised power budget with true-off circuit:**

| State | Current | Time fraction (600 s cycle) | Contribution |
|-------|---------|----------------------------|--------------|
| Pi active | 1102 mA | 25.6 / 600 = 4.3% | 47.4 mA |
| Pi off | 0 mA | 95.7% | 0 mA |
| Arduino always-on | 85 mA | 100% | 85 mA |
| **Average system** | | | **132 mA** |

**Projected deployment durations with true-off:**

| Battery | Duration |
|---------|----------|
| 20,000 mAh | ~6.3 days |
| 40,000 mAh | ~12.6 days |
| 60,000 mAh | ~18.9 days |

**Suitable components (all under £5):**
- Pololu pushbutton power switch (latching, GPIO-controllable)
- Texas Instruments TPL5110 timer IC (no MCU needed, hardware timer)
- DS3231 RTC module + N-channel MOSFET (most flexible, software-scheduled)

---

## Report section cross-references

This log directly supports the following sections of the final report:

| This log | Report section |
|----------|----------------|
| Tests 4.1–4.3 raw readings | **Section 4 (Results)** — Table: Measured vs modelled current draw |
| D.2 Comparison Summary | **Section 4 (Results)** — Power budget validation subsection |
| Critical finding: Pi 5 halt | **Section 5 (Discussion)** — Limitations: sleep current discrepancy |
| Relay/timer recommendation | **Section 5 (Discussion)** — Recommendations: power management improvement |
| Deployment duration table | **Section 5 (Discussion)** — Extended deployment feasibility |

The `run_power_validation.py` script (`analysis/run_power_validation.py`)
reproduces all calculated values in this log programmatically and can be
re-run if battery capacity or duty cycle assumptions change.
