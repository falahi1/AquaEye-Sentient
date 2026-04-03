#!/usr/bin/env python3
"""
AquaEye-Sentient Acoustic Analysis Runner
==========================================
Fill in your measured values in the DATA SECTION below, then run:
    python run_analysis.py

Output figures are saved to analysis/figures/.
Run from the project root or from analysis/.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from acoustic.compute_rms import compute_rms_dbfs
from acoustic.plot_directivity import combine_array_directivity, plot_directivity
from acoustic.plot_frequency_response import plot_frequency_response

# ============================================================
# DATA SECTION — fill in your measured values after testing
# ============================================================

# Test 1.1 — Noise Floor (run compute_rms_dbfs on your silence recordings)
NOISE_FLOOR_BUCKET_DBFS = None   # e.g. -62.3
NOISE_FLOOR_POOL_DBFS   = None   # e.g. -58.1

# Test 1.2 — Frequency Response
# Measure with: compute_rms_dbfs('your_1khz_recording.wav') etc.
# Use the recording from bucket at 0.5 m, HydroMoth facing the source directly.
FREQ_RESPONSE_FREQS_HZ   = [1000, 2000, 5000, 10000, 20000]
FREQ_RESPONSE_LEVELS_DBFS = [None, None, None, None, None]   # one per frequency above

# Test 1.3 — Config A: single HydroMoth, 1 m, 10 kHz, pool
# Keys are angles in degrees (0 = hydrophone face pointing at speaker)
CONFIG_A = {
      0: None,
     45: None,
     90: None,
    135: None,
    180: None,
    225: None,
    270: None,
    315: None,
}

# Test 2.1 — Config B: 2× HydroMoths back-to-back (180°)
# Record both channels simultaneously; enter RMS for each channel at each angle.
CONFIG_B_CH1 = {  0: None,  45: None,  90: None, 135: None,
                180: None, 225: None, 270: None, 315: None }
CONFIG_B_CH2 = {  0: None,  45: None,  90: None, 135: None,
                180: None, 225: None, 270: None, 315: None }

# Test 2.2 — Config C: 3× HydroMoths at 120°
CONFIG_C_CH1 = {  0: None,  45: None,  90: None, 135: None,
                180: None, 225: None, 270: None, 315: None }
CONFIG_C_CH2 = {  0: None,  45: None,  90: None, 135: None,
                180: None, 225: None, 270: None, 315: None }
CONFIG_C_CH3 = {  0: None,  45: None,  90: None, 135: None,
                180: None, 225: None, 270: None, 315: None }

# ============================================================
# END OF DATA SECTION
# ============================================================

FIGURES_DIR = os.path.join(os.path.dirname(__file__), 'figures')
os.makedirs(FIGURES_DIR, exist_ok=True)


def _all_filled(d: dict) -> bool:
    return all(v is not None for v in d.values())


def main():
    print("AquaEye-Sentient Acoustic Analysis")
    print("=" * 40)

    # Noise floor summary
    if NOISE_FLOOR_BUCKET_DBFS is not None and NOISE_FLOOR_POOL_DBFS is not None:
        diff = NOISE_FLOOR_POOL_DBFS - NOISE_FLOOR_BUCKET_DBFS
        print(f"\nTest 1.1 — Noise Floor")
        print(f"  Bucket : {NOISE_FLOOR_BUCKET_DBFS:.1f} dBFS")
        print(f"  Pool   : {NOISE_FLOOR_POOL_DBFS:.1f} dBFS")
        print(f"  Environmental contribution: {diff:+.1f} dB")
    else:
        print("\nTest 1.1 — Noise floor: not filled in yet")

    # Frequency response
    if all(v is not None for v in FREQ_RESPONSE_LEVELS_DBFS):
        out = os.path.join(FIGURES_DIR, 'freq_response.png')
        plot_frequency_response(FREQ_RESPONSE_FREQS_HZ, FREQ_RESPONSE_LEVELS_DBFS, out)
        print(f"\nTest 1.2 — Frequency response saved: {out}")
    else:
        print("\nTest 1.2 — Frequency response: not filled in yet")

    # Directivity comparison
    configs = {}
    if _all_filled(CONFIG_A):
        configs['Config A (single)'] = CONFIG_A

    if _all_filled(CONFIG_B_CH1) and _all_filled(CONFIG_B_CH2):
        configs['Config B (back-to-back)'] = combine_array_directivity([CONFIG_B_CH1, CONFIG_B_CH2])

    if _all_filled(CONFIG_C_CH1) and _all_filled(CONFIG_C_CH2) and _all_filled(CONFIG_C_CH3):
        configs['Config C (120°)'] = combine_array_directivity([CONFIG_C_CH1, CONFIG_C_CH2, CONFIG_C_CH3])

    if configs:
        out = os.path.join(FIGURES_DIR, 'directivity_comparison.png')
        plot_directivity(configs, out)
        print(f"\nTests 1.3/2.1/2.2 — Directivity comparison saved: {out}")
        print(f"  Configs plotted: {', '.join(configs.keys())}")
    else:
        print("\nTests 1.3/2.1/2.2 — Directivity: no config data filled in yet")


if __name__ == '__main__':
    main()
