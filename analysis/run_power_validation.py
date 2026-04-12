#!/usr/bin/env python3
"""
AquaEye-Sentient Power Validation Runner
=========================================
Fill in measurements from Tests 4.1-4.3 and your D.2 modelled values,
then run:
    python run_power_validation.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from power_budget.validate_power import (
    compare_power_measurements,
    compute_deployment_duration_days,
    format_comparison_table,
)

# ============================================================
# DATA SECTION — update both tables before running
# ============================================================

# Modelled values from D.2 Power System Analysis
# Based on Raspberry Pi 5 datasheet and benchmark figures
MODELLED_mA = {
    'Pi active — FLAC encode (peak)': 1200.0,  # Pi 5 peak CPU load
    'Pi active — SD card pull':        900.0,  # Pi 5 I/O-bound state
    'Pi active — Wi-Fi upload':       1000.0,  # Pi 5 active + Wi-Fi tx
    'Pi RTC sleep':                     30.0,  # Pi 5 halt state
    'Arduino steady-state':             50.0,  # Arduino Uno at 5V
}

# Your measured values from Tests 4.1–4.3
# Test 4.1 → Pi RTC sleep
# Test 4.2 → Pi active states
# Test 4.3 → Arduino steady-state
MEASURED_mA = {
    'Pi active — FLAC encode (peak)': 1102.0,  # peak during mix phases (12:44:08)
    'Pi active — SD card pull':        845.0,  # end of warm-up staging (12:43:14)
    'Pi active — Wi-Fi upload':        None,   # not tested — upload disabled in power test
    'Pi RTC sleep':                    305.0,  # measured after sudo halt
    'Arduino steady-state':             85.0,  # measured standalone via USB meter
}

# Battery capacity from D.3 BOM (update to match your actual battery)
BATTERY_CAPACITY_mAh = 20000.0

# Duty cycle — updated from benchmark results:
# Measured active window: 25.61 s mean (vs 70 s assumed in D.2)
# Original assumption: 70.0 / 600.0
ACTIVE_FRACTION = 25.61 / 600.0

# ============================================================
# END OF DATA SECTION
# ============================================================


def main():
    print("AquaEye-Sentient Power Validation")
    print("=" * 45)

    missing = [k for k, v in MEASURED_mA.items() if v is None]
    if missing:
        print(f"\nNote: skipping unmeasured entries: {missing}")

    measured_available = {k: v for k, v in MEASURED_mA.items() if v is not None}
    modelled_available = {k: v for k, v in MODELLED_mA.items() if k in measured_available}

    rows = compare_power_measurements(modelled_available, measured_available)
    print("\nModelled vs Measured Current Draw:")
    print(format_comparison_table(rows))

    # Deployment duration — use peak active current as conservative estimate
    days_measured = compute_deployment_duration_days(
        active_mA=MEASURED_mA['Pi active — FLAC encode (peak)'],
        sleep_mA=MEASURED_mA['Pi RTC sleep'],
        arduino_mA=MEASURED_mA['Arduino steady-state'],
        active_fraction=ACTIVE_FRACTION,
        battery_mAh=BATTERY_CAPACITY_mAh,
    )
    days_modelled = compute_deployment_duration_days(
        active_mA=MODELLED_mA['Pi active — FLAC encode (peak)'],
        sleep_mA=MODELLED_mA['Pi RTC sleep'],
        arduino_mA=MODELLED_mA['Arduino steady-state'],
        active_fraction=ACTIVE_FRACTION,
        battery_mAh=BATTERY_CAPACITY_mAh,
    )

    print(f"Deployment duration (D.2 modelled):  {days_modelled:.1f} days")
    print(f"Deployment duration (measured):       {days_measured:.1f} days")
    delta = days_measured - days_modelled
    print(f"Difference:                           {delta:+.1f} days")


if __name__ == '__main__':
    main()
