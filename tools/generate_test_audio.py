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
# 10^(0/20) = 1.000,  10^(-1/20) ≈ 0.8913,  10^(+1/20) ≈ 1.1220
AMPLITUDE_VARIATIONS = [1.000, 10 ** (-1.0 / 20), 10 ** (1.0 / 20)]

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
    print(f"  scp -r {OUTPUT_DIR}/* alf0081@172.20.10.2:/home/alf0081/aquaeye/staging/")


if __name__ == "__main__":
    main()
