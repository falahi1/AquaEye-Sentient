# Pipeline Power Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate 9 simulated HydroMoth WAV files on Windows and a calibration frequency table, transfer them to the Pi, then run the full pipeline (stitch → FLAC encode → mock upload) while recording power measurements at each stage.

**Architecture:** A self-contained Python script (`tools/generate_test_audio.py`) generates all audio files and the frequency table on Windows. Files are transferred to the Pi staging folder via SCP. The existing `main.py` pipeline runs unmodified — only `config.py` needs one value changed to disable upload.

**Tech Stack:** Python 3, NumPy, SciPy, soundfile (Windows generation); existing pipeline stack on Pi (flac CLI, pyserial, soundfile).

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `tools/generate_test_audio.py` | Generates 9 WAV files + frequency_table.csv |
| Create | `tools/tests/test_generate_test_audio.py` | Unit tests for generation functions |
| Create | `tools/tests/__init__.py` | Makes tests directory a package |
| Modify | `SentientCore/raspberry_pi/config.py` | Set `GOOGLE_DRIVE_FOLDER_ID = ""` |

---

## Task 1: Bootstrap tools directory and failing tests

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/tests/__init__.py`
- Create: `tools/tests/test_generate_test_audio.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p tools/tests
touch tools/__init__.py tools/tests/__init__.py
```

- [ ] **Step 2: Write all failing tests**

Create `tools/tests/test_generate_test_audio.py`:

```python
import numpy as np
import pytest

SAMPLE_RATE = 96000


def test_silence_section_shape():
    from tools.generate_test_audio import generate_silence_section
    out = generate_silence_section(n_samples=SAMPLE_RATE, sample_rate=SAMPLE_RATE)
    assert out.shape == (SAMPLE_RATE,)


def test_silence_section_is_quiet():
    from tools.generate_test_audio import generate_silence_section
    out = generate_silence_section(n_samples=SAMPLE_RATE, sample_rate=SAMPLE_RATE)
    assert np.max(np.abs(out)) < 0.01


def test_sweep_section_shape():
    from tools.generate_test_audio import generate_sweep_section
    n = SAMPLE_RATE * 5
    out = generate_sweep_section(n_samples=n, sample_rate=SAMPLE_RATE,
                                 f_start=20.0, f_end=48000.0)
    assert out.shape == (n,)


def test_sweep_section_amplitude_in_range():
    from tools.generate_test_audio import generate_sweep_section
    out = generate_sweep_section(n_samples=SAMPLE_RATE * 5, sample_rate=SAMPLE_RATE,
                                 f_start=20.0, f_end=48000.0)
    assert np.max(np.abs(out)) <= 1.0


def test_cetacean_section_shape():
    from tools.generate_test_audio import generate_cetacean_section
    n = SAMPLE_RATE * 4
    out = generate_cetacean_section(n_samples=n, sample_rate=SAMPLE_RATE)
    assert out.shape == (n,)


def test_cetacean_section_not_silent():
    from tools.generate_test_audio import generate_cetacean_section
    out = generate_cetacean_section(n_samples=SAMPLE_RATE * 4, sample_rate=SAMPLE_RATE)
    assert np.max(np.abs(out)) > 0.01


def test_frequency_table_start_and_end():
    from tools.generate_test_audio import generate_frequency_table
    rows = generate_frequency_table(
        sweep_start_sec=60, sweep_end_sec=360,
        f_start=20.0, f_end=48000.0, interval_sec=1.0
    )
    assert rows[0]["time_sec"] == 60.0
    assert rows[0]["freq_hz"] == pytest.approx(20.0, abs=1.0)
    assert rows[-1]["freq_hz"] == pytest.approx(48000.0, abs=100.0)


def test_frequency_table_row_count():
    from tools.generate_test_audio import generate_frequency_table
    rows = generate_frequency_table(
        sweep_start_sec=60, sweep_end_sec=360,
        f_start=20.0, f_end=48000.0, interval_sec=1.0
    )
    # 300 seconds sweep, 1-second interval → 301 rows (inclusive)
    assert len(rows) == 301


def test_staged_filename_format():
    from tools.generate_test_audio import staged_filename
    name = staged_filename("HM_A", "20260407_100000")
    assert name == "HM_A__20260407_100000.WAV"


def test_session_layout_produces_nine_files():
    from tools.generate_test_audio import SESSIONS, HM_IDS
    assert len(SESSIONS) == 3
    assert len(HM_IDS) == 3


def test_amplitude_variations_length():
    from tools.generate_test_audio import AMPLITUDE_VARIATIONS, HM_IDS
    assert len(AMPLITUDE_VARIATIONS) == len(HM_IDS)


def test_amplitude_variations_within_1db():
    from tools.generate_test_audio import AMPLITUDE_VARIATIONS
    # ±1 dB → amplitude ratio between 10^(-1/20) and 10^(1/20)
    low = 10 ** (-1.0 / 20)
    high = 10 ** (1.0 / 20)
    for amp in AMPLITUDE_VARIATIONS:
        assert low <= amp <= high
```

- [ ] **Step 3: Run tests to confirm they all fail**

```bash
cd C:\Users\alahi\Desktop\AquaEye-Sentient
pytest tools/tests/test_generate_test_audio.py -v
```

Expected: All 12 tests fail with `ModuleNotFoundError: No module named 'tools.generate_test_audio'`

- [ ] **Step 4: Commit failing tests**

```bash
git add tools/
git commit -m "test: add failing tests for generate_test_audio"
```

---

## Task 2: Implement generate_test_audio.py — constants and pure functions

**Files:**
- Create: `tools/generate_test_audio.py`

- [ ] **Step 1: Install dependencies on Windows**

```bash
pip install numpy scipy soundfile
```

- [ ] **Step 2: Create the script with constants and pure functions**

Create `tools/generate_test_audio.py`:

```python
# =============================================================================
# AquaEye-Sentient — generate_test_audio.py
# =============================================================================
# Generates 9 simulated HydroMoth WAV files (3 sessions × 3 units) and a
# frequency calibration table for pipeline power testing and future HydroMoth
# characterisation.
#
# Run on Windows:
#   python tools/generate_test_audio.py
#
# Output:
#   tools/test_audio/HM_A__20260407_100000.WAV  (and 8 more WAV files)
#   tools/test_audio/frequency_table.csv
#
# Audio structure per file (10 minutes, 96 kHz, 16-bit mono):
#   0:00 – 1:00   Silence + low-level noise (ambient baseline)
#   1:00 – 6:00   Linear frequency sweep 20 Hz → 48 kHz (calibration)
#   6:00 – 10:00  Synthesised cetacean signals (FM whistles + clicks)
# =============================================================================

import csv
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_RATE    = 96000       # Hz — matches HydroMoth configuration
DURATION_SEC   = 600         # 10 minutes

SILENCE_SEC    = 60          # 0:00 – 1:00
SWEEP_START_SEC = 60         # 1:00
SWEEP_END_SEC   = 360        # 6:00
CETACEAN_START_SEC = 360     # 6:00
CETACEAN_END_SEC   = 600     # 10:00

SWEEP_FREQ_START = 20.0      # Hz
SWEEP_FREQ_END   = 48000.0   # Hz (Nyquist at 96 kHz)

# Session timestamps: (HM_A, HM_B, HM_C)
# HM_B/C are +2/+3 s within the 5 s STITCH_TOLERANCE_SEC
SESSIONS = [
    ("20260407_100000", "20260407_100002", "20260407_100003"),
    ("20260407_101000", "20260407_101002", "20260407_101003"),
    ("20260407_102000", "20260407_102002", "20260407_102003"),
]

HM_IDS = ["HM_A", "HM_B", "HM_C"]

# ±1 dB amplitude variation per unit
# 10^(+1/20) = 1.122,  10^(0/20) = 1.000,  10^(-1/20) = 0.891
AMPLITUDE_VARIATIONS = [1.000, 0.891, 1.122]

OUTPUT_DIR = Path(__file__).parent / "test_audio"


# ---------------------------------------------------------------------------
# Pure audio generation functions
# ---------------------------------------------------------------------------

def generate_silence_section(n_samples: int, sample_rate: int) -> np.ndarray:
    """Return silence with low-level white noise (amplitude < 0.001)."""
    return np.random.default_rng(seed=42).standard_normal(n_samples) * 0.001


def generate_sweep_section(n_samples: int, sample_rate: int,
                            f_start: float, f_end: float) -> np.ndarray:
    """
    Return a linear frequency chirp from f_start to f_end.
    Amplitude is 0.5 to leave headroom for mixing.
    """
    T = n_samples / sample_rate
    t = np.linspace(0, T, n_samples, endpoint=False)
    k = (f_end - f_start) / T
    phase = 2 * np.pi * (f_start * t + 0.5 * k * t ** 2)
    return np.sin(phase) * 0.5


def generate_cetacean_section(n_samples: int, sample_rate: int) -> np.ndarray:
    """
    Return synthesised cetacean signals:
    - 10 FM whistles (2–20 kHz, 0.5–2 s duration, Hanning-windowed)
    - 30 broadband clicks (2 ms, Hanning-windowed)
    """
    rng = np.random.default_rng(seed=7)
    audio = np.zeros(n_samples, dtype=np.float64)
    t_total = n_samples / sample_rate

    # FM whistles
    for _ in range(10):
        start_t  = rng.uniform(0, t_total - 2.0)
        dur      = rng.uniform(0.5, 2.0)
        f0       = rng.uniform(2000, 10000)
        f1       = rng.uniform(5000, 20000)
        n        = int(dur * sample_rate)
        t        = np.linspace(0, dur, n, endpoint=False)
        k        = (f1 - f0) / dur
        phase    = 2 * np.pi * (f0 * t + 0.5 * k * t ** 2)
        whistle  = np.sin(phase) * 0.3 * np.hanning(n)
        idx      = int(start_t * sample_rate)
        end_idx  = min(idx + n, n_samples)
        audio[idx:end_idx] += whistle[:end_idx - idx]

    # Broadband clicks
    for _ in range(30):
        start_t  = rng.uniform(0, t_total - 0.01)
        n        = int(0.002 * sample_rate)   # 2 ms
        click    = rng.standard_normal(n) * 0.4 * np.hanning(n)
        idx      = int(start_t * sample_rate)
        end_idx  = min(idx + n, n_samples)
        audio[idx:end_idx] += click[:end_idx - idx]

    return np.clip(audio, -1.0, 1.0)


def generate_frequency_table(sweep_start_sec: float, sweep_end_sec: float,
                              f_start: float, f_end: float,
                              interval_sec: float = 1.0) -> list[dict]:
    """
    Return a list of dicts mapping file timestamps (seconds) to instantaneous
    frequency during the sweep section, sampled every interval_sec.

    Keys: time_sec, freq_hz
    """
    T = sweep_end_sec - sweep_start_sec
    rows = []
    t = 0.0
    while t <= T + 1e-9:
        freq = f_start + (f_end - f_start) * (t / T)
        rows.append({
            "time_sec": round(sweep_start_sec + t, 1),
            "freq_hz":  round(freq, 1),
        })
        t += interval_sec
    return rows


def staged_filename(hm_id: str, timestamp: str) -> str:
    """Return the staging filename for a HydroMoth unit and timestamp."""
    return f"{hm_id}__{timestamp}.WAV"
```

- [ ] **Step 3: Run tests — pure functions should now pass**

```bash
pytest tools/tests/test_generate_test_audio.py -v
```

Expected: All 12 tests pass.

- [ ] **Step 4: Commit**

```bash
git add tools/generate_test_audio.py
git commit -m "feat: implement generate_test_audio pure functions; all tests pass"
```

---

## Task 3: Implement file generation and main entry point

**Files:**
- Modify: `tools/generate_test_audio.py` (append below the pure functions)

- [ ] **Step 1: Append the file writer and main block to generate_test_audio.py**

Add the following to the bottom of `tools/generate_test_audio.py`:

```python
# ---------------------------------------------------------------------------
# File writer
# ---------------------------------------------------------------------------

def generate_wav_file(output_dir: Path, hm_id: str,
                      timestamp: str, amplitude: float) -> Path:
    """
    Assemble and write one 10-minute WAV file for a single HydroMoth unit.

    Returns the path of the written file.
    """
    silence  = generate_silence_section(SILENCE_SEC * SAMPLE_RATE, SAMPLE_RATE)
    sweep    = generate_sweep_section(
        (SWEEP_END_SEC - SWEEP_START_SEC) * SAMPLE_RATE,
        SAMPLE_RATE, SWEEP_FREQ_START, SWEEP_FREQ_END,
    )
    cetacean = generate_cetacean_section(
        (CETACEAN_END_SEC - CETACEAN_START_SEC) * SAMPLE_RATE,
        SAMPLE_RATE,
    )

    audio     = np.concatenate([silence, sweep, cetacean]) * amplitude
    audio     = np.clip(audio, -1.0, 1.0)
    audio_i16 = (audio * 32767).astype(np.int16)

    fname = staged_filename(hm_id, timestamp)
    fpath = output_dir / fname
    sf.write(str(fpath), audio_i16, SAMPLE_RATE, subtype="PCM_16")
    return fpath


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = len(SESSIONS) * len(HM_IDS)
    done  = 0

    for session_timestamps in SESSIONS:
        for hm_id, timestamp, amplitude in zip(HM_IDS, session_timestamps,
                                               AMPLITUDE_VARIATIONS):
            done += 1
            print(f"[{done}/{total}] Generating {staged_filename(hm_id, timestamp)} ...")
            generate_wav_file(OUTPUT_DIR, hm_id, timestamp, amplitude)

    print(f"\nAll {total} WAV files written to {OUTPUT_DIR}/")

    # Write frequency table
    table_path = OUTPUT_DIR / "frequency_table.csv"
    rows = generate_frequency_table(
        SWEEP_START_SEC, SWEEP_END_SEC,
        SWEEP_FREQ_START, SWEEP_FREQ_END,
        interval_sec=1.0,
    )
    with open(table_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["time_sec", "freq_hz"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Frequency table written to {table_path}")
    print(f"\nTransfer to Pi staging folder:")
    print(f"  scp -r {OUTPUT_DIR}/* pi@<PI_IP>:/home/pi/aquaeye/staging/")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script — expect 9 WAV files and frequency_table.csv**

```bash
cd C:\Users\alahi\Desktop\AquaEye-Sentient
python tools/generate_test_audio.py
```

Expected output:
```
[1/9] Generating HM_A__20260407_100000.WAV ...
[2/9] Generating HM_B__20260407_100002.WAV ...
...
[9/9] Generating HM_C__20260407_102003.WAV ...

All 9 WAV files written to tools/test_audio/
Frequency table written to tools/test_audio/frequency_table.csv
```

- [ ] **Step 3: Verify file properties**

```bash
python -c "
import soundfile as sf
from pathlib import Path
f = Path('tools/test_audio/HM_A__20260407_100000.WAV')
info = sf.info(str(f))
print('Duration:', info.duration, 's (expected 600)')
print('Sample rate:', info.samplerate, '(expected 96000)')
print('Channels:', info.channels, '(expected 1)')
print('Size MB:', f.stat().st_size // (1024*1024))
"
```

Expected:
```
Duration: 600.0 s (expected 600)
Sample rate: 96000 (expected 96000)
Channels: 1 (expected 1)
Size MB: 109  (approx — 96000 × 600 × 2 bytes = ~110 MB)
```

- [ ] **Step 4: Add test_audio/ to .gitignore (files are too large to commit)**

```bash
echo "tools/test_audio/" >> .gitignore
```

- [ ] **Step 5: Commit**

```bash
git add tools/generate_test_audio.py .gitignore
git commit -m "feat: add main entry point to generate_test_audio; generates 9 WAV files + CSV"
```

---

## Task 4: Disable upload in config and verify pipeline config

**Files:**
- Modify: `SentientCore/raspberry_pi/config.py`

- [ ] **Step 1: Disable Google Drive upload**

In `SentientCore/raspberry_pi/config.py`, change:

```python
GOOGLE_DRIVE_FOLDER_ID = "11QAYDOyePI-2t7yBnwD4fmWrq0ojsDI7"
```

to:

```python
GOOGLE_DRIVE_FOLDER_ID = ""   # disabled for power test — no credentials on Pi
```

- [ ] **Step 2: Verify SERIAL_PORT is correct**

Confirm this line in `config.py`:

```python
SERIAL_PORT = "/dev/ttyUSB0"
```

- [ ] **Step 3: Commit**

```bash
git add SentientCore/raspberry_pi/config.py
git commit -m "config: disable Google Drive upload for bench power test"
```

---

## Task 5: Transfer files to Pi and run pipeline

> This task is performed manually over SSH. No code changes.

- [ ] **Step 1: Push updated code to Pi via SCP**

From Windows Git Bash (run from project root):

```bash
scp -r SentientCore/raspberry_pi/ pi@<PI_IP>:/home/pi/aquaeye/
```

- [ ] **Step 2: Transfer WAV files to Pi staging folder**

```bash
scp tools/test_audio/*.WAV pi@<PI_IP>:/home/pi/aquaeye/staging/
```

- [ ] **Step 3: SSH into Pi and verify files arrived**

```bash
ssh pi@<PI_IP>
ls /home/pi/aquaeye/staging/
```

Expected: 9 `.WAV` files listed.

- [ ] **Step 4: Install Python dependencies on Pi**

```bash
pip3 install pyserial soundfile google-auth google-auth-oauthlib google-api-python-client
```

- [ ] **Step 5: Run the pipeline**

```bash
python3 /home/pi/aquaeye/main.py
```

Watch terminal for stage markers:

```
INFO  serial_reader: Arduino connected              ← Arduino OK
INFO  main: Stitch — 3 session(s) to process       ← start reading multimeter
INFO  main: Encoded HM_A__... → ...                ← PEAK power stage
INFO  main: Sleeping 60 s until next cycle ...     ← idle, record baseline
```

---

## Task 6: Record power measurements and fill in results

> Manual measurement task — no code changes.

- [ ] **Step 1: Record idle + sensor baseline**

Before running `main.py`, note the A reading from the multimeter (Pi on, Arduino streaming). Multiply by 1000 → mA.

- [ ] **Step 2: Record stitching current**

When terminal shows `Stitch — 3 session(s)`, read A value. Stitching is fast (<1 s) — read quickly.

- [ ] **Step 3: Record FLAC encode current (peak)**

When terminal shows repeated `Encoded ...` lines, take 5 readings. This is the longest stage (~2–3 min for 9 files at 96 kHz). Record mean.

- [ ] **Step 4: Record post-encode idle**

When terminal shows `Sleeping 60 s`, read A value. This is the RTC-equivalent sleep baseline (loop mode, not true halt).

- [ ] **Step 5: Fill measurements into phase4_power_log.md**

Open `docs/test_logs/phase4_power_log.md` and fill in the D.2 Comparison Summary table.

- [ ] **Step 6: Fill measurements into run_power_validation.py**

Open `analysis/run_power_validation.py` and update `MEASURED_mA`:

```python
MEASURED_mA = {
    'Pi active — FLAC encode (peak)': <your reading>,
    'Pi active — SD card pull':       None,   # not tested this session
    'Pi active — Wi-Fi upload':       None,   # not tested this session
    'Pi RTC sleep':                   <your post-encode idle reading>,
    'Arduino steady-state':           <baseline reading>,
}
```

- [ ] **Step 7: Run the validation script**

```bash
python analysis/run_power_validation.py
```

Expected output (example):
```
AquaEye-Sentient Power Validation
=============================================
Modelled vs Measured Current Draw:
...
Deployment duration (D.2 modelled):  X.X days
Deployment duration (measured):       X.X days
Difference:                           +X.X days
```

- [ ] **Step 8: Commit filled results**

```bash
git add docs/test_logs/phase4_power_log.md analysis/run_power_validation.py
git commit -m "data: record phase 4 power measurements from bench test"
```
