# Phase 3 Test Log — Pi Pipeline Benchmark

**Date:** ___________
**Tester:** Fazley Alahi
**Pi model:** Raspberry Pi 5
**OS:** _____ (e.g. Raspberry Pi OS Bookworm 64-bit)
**Pi hostname / IP:** _____

---

## Test 3.1 — Synthetic WAV Benchmark

**Command used:**
```
cd SentientCore
python3 tests/pipeline_benchmark.py \
  --wav_dir ~/aquaeye/bench_wav \
  --cycles 10 \
  --no_serial \
  --generate_wav
```

**Date run:** _____

**Per-cycle raw data:**

| Cycle | FLAC encode (s) | Stitch (s) | Metadata write (s) | Total active (s) |
|-------|-----------------|------------|-------------------|-----------------|
| 1     |                 |            |                   |                 |
| 2     |                 |            |                   |                 |
| 3     |                 |            |                   |                 |
| 4     |                 |            |                   |                 |
| 5     |                 |            |                   |                 |
| 6     |                 |            |                   |                 |
| 7     |                 |            |                   |                 |
| 8     |                 |            |                   |                 |
| 9     |                 |            |                   |                 |
| 10    |                 |            |                   |                 |

**Aggregate statistics:**

| Metric | Mean (s) | SD (s) | Min (s) | Max (s) |
|--------|----------|--------|---------|---------|
| Total active window |  |  |  |  |
| FLAC encode (all files) |  |  |  |  |
| Avg per-file encode |  |  |  |  |
| Stitch overhead |  |  |  |  |
| Metadata write |  |  |  |  |

**Assumption A3 (encode ≤ 8 s/file):** PASS / REVISE
**Assumption A4 (total ≤ 70 s):** PASS / REVISE

---

## Test 3.2 — Real HydroMoth WAV Benchmark

**HydroMoth recording details:** _____ Hz, _____ s per file
**Command used:**
```
cd SentientCore
python3 tests/pipeline_benchmark.py \
  --wav_dir ~/aquaeye/bench_wav \
  --cycles 10 \
  --no_serial
```

**Date run:** _____

**Per-cycle raw data:**

| Cycle | FLAC encode (s) | Stitch (s) | Metadata write (s) | Total active (s) |
|-------|-----------------|------------|-------------------|-----------------|
| 1     |                 |            |                   |                 |
| 2     |                 |            |                   |                 |
| 3     |                 |            |                   |                 |
| 4     |                 |            |                   |                 |
| 5     |                 |            |                   |                 |
| 6     |                 |            |                   |                 |
| 7     |                 |            |                   |                 |
| 8     |                 |            |                   |                 |
| 9     |                 |            |                   |                 |
| 10    |                 |            |                   |                 |

**Aggregate statistics:**

| Metric | Mean (s) | SD (s) | Min (s) | Max (s) |
|--------|----------|--------|---------|---------|
| Total active window |  |  |  |  |
| FLAC encode (all files) |  |  |  |  |
| Avg per-file encode |  |  |  |  |
| Stitch overhead |  |  |  |  |
| Metadata write |  |  |  |  |

**Assumption A3 (encode ≤ 8 s/file):** PASS / REVISE
**Assumption A4 (total ≤ 70 s):** PASS / REVISE

---

## Timing Assumption Comparison

| Assumption | Budgeted | Synthetic result | Real WAV result | Final status |
|-----------|----------|-----------------|----------------|-------------|
| A3: encode time/file | 8.0 s | | | |
| A4: total active window | 70.0 s | | | |

**If REVISE:** Updated D.2 values: encode = _____ s, total active = _____ s
**Corrected deployment duration (if revised):** _____ days

---

## Notes
