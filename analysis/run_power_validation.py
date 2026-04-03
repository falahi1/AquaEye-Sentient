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
# Update these to match your actual D.2 figures
MODELLED_mA = {
    'Pi active — FLAC encode (peak)': 800.0,   # update from D.2
    'Pi active — SD card pull':       700.0,   # update from D.2
    'Pi active — Wi-Fi upload':       750.0,   # update from D.2
    'Pi RTC sleep':                    10.0,   # update from D.2
    'Arduino steady-state':            30.0,   # update from D.2
}

# Your measured values from Tests 4.1–4.3
# Test 4.1 → Pi RTC sleep
# Test 4.2 → Pi active states
# Test 4.3 → Arduino steady-state
MEASURED_mA = {
    'Pi active — FLAC encode (peak)': None,   # fill in
    'Pi active — SD card pull':       None,   # fill in
    'Pi active — Wi-Fi upload':       None,   # fill in
    'Pi RTC sleep':                   None,   # fill in
    'Arduino steady-state':           None,   # fill in
}

# Battery capacity from D.3 BOM (update to match your actual battery)
BATTERY_CAPACITY_mAh = 20000.0

# Duty cycle from D.2 (70 s active per 600 s cycle)
ACTIVE_FRACTION = 70.0 / 600.0

# ============================================================
# END OF DATA SECTION
# ============================================================


def main():
    print("AquaEye-Sentient Power Validation")
    print("=" * 45)

    if any(v is None for v in MEASURED_mA.values()):
        missing = [k for k, v in MEASURED_mA.items() if v is None]
        print(f"\nNot ready — fill in MEASURED_mA for: {missing}")
        return

    rows = compare_power_measurements(MODELLED_mA, MEASURED_mA)
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
