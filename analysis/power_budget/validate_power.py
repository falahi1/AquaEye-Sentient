from typing import Dict


def compare_power_measurements(
    modelled: Dict[str, float],
    measured: Dict[str, float]
) -> list:
    """
    Compare modelled vs measured current draw per operating state.

    modelled / measured: {'state name': current_mA, ...}
    Returns list of dicts: {state, modelled_mA, measured_mA, error_pct}
    error_pct > 0 means measured exceeded model.
    Raises ValueError if key sets do not match.
    """
    if set(modelled.keys()) != set(measured.keys()):
        raise ValueError(
            f"Key mismatch — modelled: {set(modelled.keys())}, "
            f"measured: {set(measured.keys())}"
        )
    rows = []
    for state in sorted(modelled.keys()):
        m = modelled[state]
        r = measured[state]
        error_pct = ((r - m) / m * 100.0) if m != 0 else float('inf')
        rows.append({
            'state': state,
            'modelled_mA': m,
            'measured_mA': r,
            'error_pct': round(error_pct, 1),
        })
    return rows


def compute_deployment_duration_days(
    active_mA: float,
    sleep_mA: float,
    arduino_mA: float,
    active_fraction: float,
    battery_mAh: float,
) -> float:
    """
    Estimate deployment duration in days from measured current values.

    active_fraction: fraction of time in active state, e.g. 70/600 = 0.1167 (must be in [0, 1])
    Arduino is assumed to run continuously.
    Returns float (days).
    Raises ValueError for invalid inputs (active_fraction out of range, non-positive battery/currents).
    """
    if not (0.0 <= active_fraction <= 1.0):
        raise ValueError(
            f"active_fraction must be in [0, 1], got {active_fraction}. "
            f"Did you pass minutes (e.g. 70) instead of a fraction (70/600)?"
        )
    if battery_mAh <= 0:
        raise ValueError(f"battery_mAh must be positive, got {battery_mAh}")
    if active_mA < 0 or sleep_mA < 0 or arduino_mA < 0:
        raise ValueError("Current values (active_mA, sleep_mA, arduino_mA) must be non-negative")
    sleep_fraction = 1.0 - active_fraction
    avg_pi_mA = active_mA * active_fraction + sleep_mA * sleep_fraction
    total_avg_mA = avg_pi_mA + arduino_mA
    if total_avg_mA == 0.0:
        raise ValueError("Total average current is zero — check that not all current values are zero")
    duration_hours = battery_mAh / total_avg_mA
    return duration_hours / 24.0


def format_comparison_table(rows: list) -> str:
    """
    Format comparison rows as a markdown table string.
    rows: output of compare_power_measurements().
    """
    header = "| State | Modelled (mA) | Measured (mA) | Error (%) |\n"
    sep    = "|-------|---------------|---------------|-----------|\n"
    lines  = [header, sep]
    for row in rows:
        lines.append(
            f"| {row['state']} | {row['modelled_mA']:.1f} | "
            f"{row['measured_mA']:.1f} | {row['error_pct']:+.1f} |\n"
        )
    return ''.join(lines)
