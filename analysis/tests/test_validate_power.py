def test_compare_exact_match_gives_zero_error():
    from power_budget.validate_power import compare_power_measurements
    modelled = {'Pi active': 800.0, 'Pi sleep': 10.0}
    measured = {'Pi active': 800.0, 'Pi sleep': 10.0}
    rows = compare_power_measurements(modelled, measured)
    for row in rows:
        assert row['error_pct'] == 0.0


def test_compare_10_percent_over_gives_plus_10():
    from power_budget.validate_power import compare_power_measurements
    rows = compare_power_measurements({'Pi active': 800.0}, {'Pi active': 880.0})
    assert abs(rows[0]['error_pct'] - 10.0) < 0.05


def test_compare_mismatched_keys_raises():
    from power_budget.validate_power import compare_power_measurements
    raised = False
    try:
        compare_power_measurements({'Pi active': 800.0}, {'Pi sleep': 10.0})
    except ValueError:
        raised = True
    assert raised, "Expected ValueError for mismatched keys"


def test_deployment_duration_in_plausible_range():
    """800 mA active, 10 mA sleep, 30 mA Arduino, 70/600 duty, 20 Ah → ~1-60 days."""
    from power_budget.validate_power import compute_deployment_duration_days
    days = compute_deployment_duration_days(
        active_mA=800.0, sleep_mA=10.0, arduino_mA=30.0,
        active_fraction=70.0 / 600.0, battery_mAh=20000.0
    )
    assert 1.0 < days < 60.0, f"Unexpected duration: {days:.1f} days"


def test_higher_sleep_current_reduces_duration():
    from power_budget.validate_power import compute_deployment_duration_days
    kwargs = dict(active_mA=800.0, arduino_mA=30.0,
                  active_fraction=70.0 / 600.0, battery_mAh=20000.0)
    days_low  = compute_deployment_duration_days(sleep_mA=5.0,  **kwargs)
    days_high = compute_deployment_duration_days(sleep_mA=100.0, **kwargs)
    assert days_low > days_high


def test_format_table_contains_expected_headers():
    from power_budget.validate_power import format_comparison_table
    rows = [{'state': 'Pi active', 'modelled_mA': 800.0,
             'measured_mA': 820.0, 'error_pct': 2.5}]
    table = format_comparison_table(rows)
    assert 'State' in table
    assert 'Modelled' in table
    assert 'Measured' in table
    assert 'Error' in table
    assert 'Pi active' in table


def test_deployment_duration_raises_on_invalid_active_fraction():
    from power_budget.validate_power import compute_deployment_duration_days
    raised = False
    try:
        compute_deployment_duration_days(
            active_mA=800.0, sleep_mA=10.0, arduino_mA=30.0,
            active_fraction=70.0,   # wrong: minutes passed instead of fraction
            battery_mAh=20000.0
        )
    except ValueError:
        raised = True
    assert raised, "Expected ValueError for active_fraction > 1"


def test_deployment_duration_raises_on_zero_battery():
    from power_budget.validate_power import compute_deployment_duration_days
    raised = False
    try:
        compute_deployment_duration_days(
            active_mA=800.0, sleep_mA=10.0, arduino_mA=30.0,
            active_fraction=70.0 / 600.0, battery_mAh=0.0
        )
    except ValueError:
        raised = True
    assert raised, "Expected ValueError for zero battery capacity"


def test_deployment_duration_raises_on_negative_current():
    from power_budget.validate_power import compute_deployment_duration_days
    raised = False
    try:
        compute_deployment_duration_days(
            active_mA=-100.0, sleep_mA=10.0, arduino_mA=30.0,
            active_fraction=70.0 / 600.0, battery_mAh=20000.0
        )
    except ValueError:
        raised = True
    assert raised, "Expected ValueError for negative current"
