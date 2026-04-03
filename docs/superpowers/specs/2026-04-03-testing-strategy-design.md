# AquaEye-Sentient Testing Strategy — Design Spec
**Date:** 2026-04-03
**Author:** Fazley Alahi (1934714)
**Approach:** Bottom-up subsystem isolation

---

## Overview

Five sequential phases, each building on the previous. Phases 3 and 4 (Pi benchmark and power measurement) can run in parallel with Phases 1–2 as they require no HydroMoth recordings.

| Phase | Name | What it tests | Environment |
|-------|------|---------------|-------------|
| 1 | Single HydroMoth Characterisation | Noise floor, frequency response, directivity of one unit | Bucket → pool |
| 2 | Multi-Unit Configuration Comparison | Directivity of Config B (2× 180°) and Config C (3× 120°) vs Phase 1 baseline | Pool |
| 3 | Pi Pipeline Benchmark | FLAC encode timing, cycle time on real Pi 5 hardware | Pi on desk |
| 4 | Power Consumption Measurement | Measured current per operating state vs D.2 model | Pi on desk + multimeter |
| 5 | End-to-End Integration | Full pipeline with real HydroMoth WAV files from Phases 1–2 | Pi + HydroMoths |

**Dependency chain:**
- Phase 1 produces the baseline + real WAV files that Phases 2 and 5 depend on
- Phase 2 completes the acoustic picture before integration
- Phases 3 and 4 are independent — run alongside Phases 1–2 to save time
- Phase 5 closes the loop using everything above

---

## Phase 1: Single HydroMoth Characterisation

**Purpose:** Establish baseline characterisation of a single HydroMoth unit — the instrument itself before any array configuration. Provides the reference polar plot that Phases 2 comparisons are built against.

**Equipment:**
- 1× HydroMoth
- Waterproof speaker (primary sound source) + phone in waterproof bag (backup)
- Tone generator app (on phone)
- Tape measure
- Bucket (Tests 1.1 and 1.2) + swimming pool (Test 1.3)
- Laptop for reviewing recordings

---

### Test 1.1 — Noise Floor

**Environment:** Bucket, then pool
**Procedure:**
1. Submerge HydroMoth at ~0.5 m depth
2. No sound source active
3. Record 60 seconds of silence
4. Run in bucket (minimal ambient noise) and again in pool (ambient pool noise)

**Record:** RMS level of each recording in dBFS
**Output:** Noise floor figure; difference between bucket and pool reveals environmental contribution
**Limitation note:** Self-noise and ambient noise are not separated — report as combined floor

---

### Test 1.2 — Frequency Response

**Environment:** Bucket (0.5 m source distance), then pool (1 m source distance)
**Procedure:**
1. Fix HydroMoth and sound source at known distance, same depth
2. Play single tones via tone generator app at: **1, 2, 5, 10, 20 kHz**
3. Record ~10 seconds per frequency
4. Measure RMS level at each frequency

**Record:** Recorded RMS level (dBFS) at each frequency
**Output:** Relative frequency response curve (normalised to 1 kHz reference)
**Note:** This is a relative response shape, not absolute SPL — sufficient for report purposes. Covers common dolphin whistle range (2–20 kHz) and bottlenose echolocation overlap.

---

### Test 1.3 — Directivity Pattern

**Environment:** Swimming pool
**Procedure:**
1. Fix sound source at **1 m distance**, consistent depth
2. Play continuous tone at **10 kHz** (mid-range for target species)
3. Rotate HydroMoth through **8 angular positions:** 0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°
4. Record ~10 seconds at each position
5. Use tape measure for distance consistency; mark angles by estimation

**Record:** RMS level (dBFS) at each angle
**Output:** Polar plot of directional sensitivity — the Config A baseline
**Limitation note:** Angular resolution of 45° will not capture sharp nulls between positions. Document as methodology limitation. Sufficient to demonstrate the directional character of a single unit.

---

## Phase 2: Multi-Unit Configuration Comparison

**Purpose:** Repeat the directivity test for Config B and Config C to produce comparative polar plots. Frequency response and noise floor are single-unit properties — not repeated here.

**Equipment:**
- 3× HydroMoths
- Rigid mounting frame (PVC pipe or wooden dowel) for angle-fixed assembly
- Same sound source and pool setup as Test 1.3

---

### Test 2.1 — Config B: 2× HydroMoths Back-to-Back (180°)

**Procedure:**
1. Mount 2 HydroMoths facing opposite directions on rigid frame
2. Repeat exact directivity protocol from Test 1.3 (1 m, 10 kHz, 8 positions)
3. Record both channels simultaneously at each angle

**Analysis:** At each angle, take the **maximum** of the two recorded levels as the array's effective sensitivity
**Output:** Config B combined polar plot

---

### Test 2.2 — Config C: 3× HydroMoths at 120°

**Procedure:**
1. Mount 3 HydroMoths at 120° spacing on rigid frame
2. Repeat exact directivity protocol from Test 1.3
3. Record all three channels simultaneously at each angle

**Analysis:** At each angle, take the **maximum** of the three recorded levels
**Output:** Config C combined polar plot

---

### Phase 2 Deliverable

Three polar plots overlaid on the same axes — Config A (single), Config B (back-to-back), Config C (120°). This is the centrepiece figure for the configuration comparison in the report. Directly validates the D.1 recommendation with measured data.

---

## Phase 3: Pi Pipeline Benchmark

**Purpose:** Validate timing assumptions A3 and A4 from D.2 on real Pi 5 hardware. The existing benchmark script (`SentientCore/tests/pipeline_benchmark.py`) is used — this phase is about running it properly.

**Equipment:** Raspberry Pi 5, laptop (SSH), real HydroMoth WAV files from Phase 1

**Key assumptions under test:**
- **A3:** FLAC encode time ~8 s per file at 96 kHz (flagged HIGH RISK — never measured on Pi 5)
- **A4:** Total active window ~70 s per cycle

---

### Test 3.1 — Synthetic WAV Benchmark

**Procedure:**
1. Run `pipeline_benchmark.py` on Pi 5 with synthetic silence WAVs (`--no_serial` flag)
2. Run **10 cycles**

**Record:** Per-cycle encode time (mean, SD, min, max), total active window time
**Output:** Baseline Pi 5 processing performance without real audio complexity

---

### Test 3.2 — Real WAV Benchmark

**Procedure:**
1. Transfer real HydroMoth WAV files from Phase 1 to Pi
2. Repeat benchmark with real files, 10 cycles

**Record:** Same metrics as Test 3.1
**Output:** Honest validation — real audio compresses differently than silence

**If A3 or A4 fail:** Update D.2 power budget with real measured values. A failed assumption caught by testing is a stronger result for the report than an untested pass.

---

### Phase 3 Deliverable

Table: modelled timing (from D.2) vs measured timing (mean ± SD) vs pass/fail for A3 and A4.

---

## Phase 4: Power Consumption Measurement

**Purpose:** Validate current draw figures from D.2 using a multimeter in series with the Pi's positive supply line.

**Equipment:** Multimeter, Raspberry Pi 5, Arduino, 5 V supply

**Measurement method:** Multimeter in series with positive supply. Fluctuating readings during active processing — take mean of ~5 readings over 10 seconds per state.

---

### Test 4.1 — RTC Sleep State

**Procedure:** Measure current when Pi is halted in RTC sleep mode
**Record:** Current draw (mA)
**Importance:** Highest impact on deployment duration — system spends ~88% of duty cycle here

---

### Test 4.2 — Active Processing State

**Procedure:** Trigger a full pipeline cycle, measure current at three sub-states:
- During FLAC encode (CPU-intensive — expected peak)
- During SD card pull / file writes (I/O-bound)
- During Wi-Fi transmission (cloud upload)

**Record:** Current draw (mA) at each sub-state

---

### Test 4.3 — Arduino Sensor Hub

**Procedure:** Power Arduino separately, measure its current draw in steady-state operation
**Record:** Current draw (mA)
**Importance:** Arduino runs continuously — constant contribution to total power budget

---

### Phase 4 Deliverable

Table: component × state → modelled current (D.2) vs measured current vs % error. Calculate corrected deployment duration if figures differ materially.

---

## Phase 5: End-to-End Integration Test

**Purpose:** Prove the full system works as a complete assembly with real HydroMoth recordings. Uses SD cards from Phase 2 (3-unit array recordings).

**Equipment:** Pi 5, 3× HydroMoths with SD cards from Phase 2, Arduino running sensor_hub.ino, Wi-Fi hotspot

---

### Test 5.1 — SD Card Pull to FLAC

**Procedure:** Insert SD cards from all 3 HydroMoths, run full pull → stitch → encode → metadata cycle
**Pass criteria:**
- All 3 units' files pulled correctly
- Session stitcher groups files from all 3 units into same session (±5 s window)
- FLAC files produced for all 3 channels
- JSON sidecars written with correct metadata fields

---

### Test 5.2 — Serial Integration

**Procedure:** Connect Arduino running sensor_hub.ino, run one full pipeline cycle
**Pass criteria:**
- Serial reader daemon picks up GPS, TDS, and turbidity readings
- Sensor values appear correctly in JSON sidecars

---

### Test 5.3 — Cloud Upload

**Procedure:** With Wi-Fi hotspot active, run cloud uploader
**Pass criteria:**
- FLAC + JSON pairs appear in Google Drive
- Paired upload logic holds — both files uploaded or neither (no orphaned FLACs)

---

### Test 5.4 — Resilience Check

**Procedure:** Deliberately trigger one failure condition per module:
- Remove one SD card mid-pull
- Disconnect Arduino mid-cycle
- Disable Wi-Fi before upload attempt

**Pass criteria:** Pipeline handles each failure gracefully without corrupting outputs from other steps. Validates per-step error handling in `main.py`.

---

### Phase 5 Deliverable

Pass/fail checklist for each sub-test. Failures documented as known limitations — expected and acceptable at prototype stage.

---

## Summary Checklist Structure

Each phase produces a checklist. The full testing log serves as Appendix B material in the final report.

| Phase | Key output for report |
|-------|----------------------|
| 1 | Noise floor figure, relative frequency response curve, Config A polar plot |
| 2 | Config B and C polar plots; three-way comparison figure |
| 3 | Timing validation table (modelled vs measured); A3/A4 pass/fail |
| 4 | Power consumption table (modelled vs measured); corrected deployment duration |
| 5 | Integration pass/fail checklist; known limitations list |

---

## Limitations Acknowledged

- Directivity angular resolution: 45° steps — sharp nulls between positions may be missed
- Absolute SPL not measured (no calibrated reference hydrophone) — all levels are relative
- Frequency response is relative, not absolute
- Distance control is approximate (tape measure, not rail/jig)
- Power measurements are mean spot readings, not continuous logging
