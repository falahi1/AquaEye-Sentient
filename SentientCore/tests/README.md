# AquaEye-Sentient — Tests

This folder contains the pipeline benchmark harness and its output reports.
These files are **not deployed to the buoy** — they are for testing and validation only.

---

## Files

| File | Purpose |
|------|---------|
| `pipeline_benchmark.py` | Runs the full pipeline repeatedly and measures timing |

---

## What the Benchmark Tests

`pipeline_benchmark.py` exercises the three core processing modules
(`session_stitcher`, `audio_processor`, `metadata_writer`) end to end,
measuring how long each step takes. This validates the power budget assumptions
before committing to the hardware design.

It simulates the pull step internally — no SD cards or HydroMoths are needed.

**What it does NOT test:** `hydromoth_puller`, `serial_reader`, `cloud_uploader`,
or `main.py`. Those require real hardware (SD cards, Arduino, Google credentials).

---

## Dependencies

The benchmark imports from the pipeline modules in `../raspberry_pi/`. Make sure
all pipeline dependencies are installed before running:

```bash
pip3 install soundfile pyserial requests google-api-python-client google-auth-oauthlib
```

---

## How to Run

### Step 1 — Prepare WAV files

**Option A — Use real HydroMoth recordings (preferred on Pi):**

Copy WAV files from your HydroMoth SD cards into a working directory.
Files must follow HydroMoth naming format: `YYYYMMDD_HHMMSS.WAV`

```
~/aquaeye/bench_wav/20260401_120000.WAV
~/aquaeye/bench_wav/20260401_121000.WAV
~/aquaeye/bench_wav/20260401_122000.WAV
...
```

Aim for at least 6 files (3 HydroMoths × 2 sessions) for a meaningful test.

**Option B — Generate synthetic WAV files (for code testing only):**

```bash
python3 pipeline_benchmark.py --generate_wav --wav_dir ~/aquaeye/bench_wav
```

This creates 6 files of 60 s silence at 96 kHz. Useful for verifying the code
runs correctly, but timing results will not reflect real recordings.

### Step 2 — Connect inline power meter (Pi only)

Connect a USB inline power meter (e.g. UM25C) between the Pi's 5V supply and
the Pi itself. Start recording current on the meter before running the benchmark.
This captures Assumption A1 (active current during FLAC compression).

### Step 3 — Run the benchmark

**With Arduino connected:**
```bash
python3 tests/pipeline_benchmark.py --wav_dir ~/aquaeye/bench_wav --cycles 10
```

**Without Arduino (--no_serial):**
```bash
python3 tests/pipeline_benchmark.py --wav_dir ~/aquaeye/bench_wav --cycles 10 --no_serial
```

Run from the `SentientCore/` directory so the benchmark can find the pipeline modules.

---

## Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--wav_dir PATH` | Directory containing input WAV files | Required |
| `--cycles N` | Number of benchmark cycles to run | 5 |
| `--no_serial` | Skip Arduino serial reader | Off |
| `--generate_wav` | Generate synthetic WAV files into `--wav_dir` then exit | Off |

---

## Understanding the Output

The benchmark prints three tables after all cycles complete:

**Per-cycle timing** — encode time, stitch time, metadata time, and total per cycle.

**Aggregate statistics** — mean, standard deviation, min, and max across all cycles.

**Assumption comparison:**

| Assumption | What it checks |
|------------|---------------|
| A3: encode time/file | Is per-file FLAC encode within the budgeted 8 s? |
| A3+A4: total active window | Is the full cycle within the budgeted 70 s? |
| A1: active current | Read from your inline meter — not captured by the script |

Status is **OK** if measured ≤ 125% of the budgeted value, **REVISE** if over.

---

## Laptop vs Pi Results

Results on a laptop are not meaningful for the power budget. A laptop CPU is
far more powerful than the Pi 5's ARM Cortex-A76. Synthetic WAV files (silence)
also compress faster than real hydrophone recordings.

**The benchmark must be re-run on the Pi 5 with real HydroMoth WAV files**
before the power budget assumptions can be confirmed or revised.

---

