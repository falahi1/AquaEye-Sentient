# AquaEye-Sentient Testing Strategy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the 5-phase testing strategy, produce Python analysis scripts for processing acoustic and power data, fill physical test logs, and generate all report figures.

**Architecture:** Two parallel workstreams. (A) Python analysis tooling written test-first — these scripts process data collected during physical tests; run on laptop. (B) Physical and system test execution — procedural checklists for acoustic characterisation and Pi validation; requires hardware access. Workstream A can start immediately. Workstream B for acoustic tests (Tasks 8–10) requires pool/bucket access. Workstream B for system tests (Tasks 11–14) requires the Pi to be SSH-accessible.

**Tech Stack:** Python 3, numpy, soundfile, matplotlib, pytest (analysis tooling); Raspberry Pi 5 + SSH + existing `pipeline_benchmark.py` (Phase 3); multimeter + Pi 5 (Phase 4); HydroMoth hardware, waterproof speaker, pool, tape measure (Phases 1–2).

---

## File Structure

```
analysis/
├── acoustic/
│   ├── __init__.py              empty package marker
│   ├── compute_rms.py           RMS level computation from WAV files
│   ├── plot_directivity.py      directivity normalisation + polar plots
│   └── plot_frequency_response.py  frequency response normalisation + plot
├── power_budget/
│   ├── __init__.py              empty package marker
│   └── validate_power.py        modelled vs measured current comparison
├── tests/
│   ├── conftest.py              sys.path + matplotlib backend setup
│   ├── test_compute_rms.py
│   ├── test_plot_directivity.py
│   ├── test_plot_frequency_response.py
│   └── test_validate_power.py
├── figures/                     output directory — gitignored
├── run_analysis.py              fill in measurements, run to get acoustic figures
├── run_power_validation.py      fill in measurements, run for power table
└── requirements.txt

docs/test_logs/
├── phase1_acoustic_log.md       recording sheet for Tests 1.1, 1.2, 1.3
├── phase2_config_comparison_log.md  recording sheet for Tests 2.1, 2.2
├── phase3_benchmark_log.md      Pi timing results template
├── phase4_power_log.md          current measurement recording sheet
└── phase5_integration_log.md    pass/fail checklist
```

---

## Task 1: Analysis Package Scaffold

**Files:**
- Create: `analysis/acoustic/__init__.py`
- Create: `analysis/power_budget/__init__.py`
- Create: `analysis/requirements.txt`
- Create: `analysis/tests/conftest.py`
- Modify: `.gitignore` (add `analysis/figures/`)

- [ ] **Step 1: Create package markers**

`analysis/acoustic/__init__.py` — empty file.
`analysis/power_budget/__init__.py` — empty file.

- [ ] **Step 2: Create requirements.txt**

`analysis/requirements.txt`:
```
numpy>=1.24
soundfile>=0.12
matplotlib>=3.7
pytest>=7.4
```

- [ ] **Step 3: Create conftest.py**

`analysis/tests/conftest.py`:
```python
import matplotlib
matplotlib.use('Agg')   # non-interactive backend — must be before any pyplot import

import sys
import os
# Add analysis/ to sys.path so 'acoustic' and 'power_budget' are importable as packages
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
```

- [ ] **Step 4: Install dependencies on laptop**

```bash
pip install -r analysis/requirements.txt
```

Expected: packages install without error. `soundfile` may already be installed from SentientCore work.

- [ ] **Step 5: Add figures/ to .gitignore**

Open `.gitignore` (create it if it doesn't exist at project root). Add:
```
analysis/figures/
```

- [ ] **Step 6: Verify pytest discovers the tests directory**

```bash
pytest analysis/tests/ --collect-only
```

Expected output: `no tests ran` (no test files yet) with zero errors. If `ModuleNotFoundError` appears, verify conftest.py was saved correctly.

- [ ] **Step 7: Commit**

```bash
git add analysis/ .gitignore
git commit -m "feat: scaffold analysis package with pytest config and requirements"
```

---

## Task 2: RMS Computation Module

**Files:**
- Create: `analysis/acoustic/compute_rms.py`
- Create: `analysis/tests/test_compute_rms.py`

- [ ] **Step 1: Write the failing tests**

`analysis/tests/test_compute_rms.py`:
```python
import numpy as np
import soundfile as sf
import tempfile
import os
import math


def _write_wav(data: np.ndarray, samplerate: int = 44100) -> str:
    """Write float64 numpy array to a temp WAV, return path."""
    f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    path = f.name
    f.close()
    sf.write(path, data, samplerate, subtype='FLOAT')
    return path


def test_full_scale_sine_returns_minus_3_dbfs():
    """Full-scale sine: RMS = 1/sqrt(2), so dBFS = 20*log10(1/sqrt(2)) ≈ -3.01."""
    from acoustic.compute_rms import compute_rms_dbfs
    t = np.linspace(0, 1, 44100, endpoint=False)
    signal = np.sin(2 * np.pi * 440 * t)
    path = _write_wav(signal)
    try:
        result = compute_rms_dbfs(path)
        assert abs(result - (-3.01)) < 0.05, f"Expected -3.01 dBFS, got {result:.4f}"
    finally:
        os.unlink(path)


def test_silence_returns_negative_infinity():
    from acoustic.compute_rms import compute_rms_dbfs
    path = _write_wav(np.zeros(44100))
    try:
        result = compute_rms_dbfs(path)
        assert result == float('-inf')
    finally:
        os.unlink(path)


def test_half_amplitude_is_6dB_below_full():
    """Halving amplitude reduces level by 20*log10(0.5) = -6.02 dB."""
    from acoustic.compute_rms import compute_rms_dbfs
    t = np.linspace(0, 1, 44100, endpoint=False)
    full = np.sin(2 * np.pi * 440 * t)
    half = full * 0.5
    path_full = _write_wav(full)
    path_half = _write_wav(half)
    try:
        diff = compute_rms_dbfs(path_full) - compute_rms_dbfs(path_half)
        assert abs(diff - 6.02) < 0.05, f"Expected 6.02 dB difference, got {diff:.4f}"
    finally:
        os.unlink(path_full)
        os.unlink(path_half)


def test_segment_matches_full_when_segment_covers_whole_file():
    from acoustic.compute_rms import compute_rms_dbfs, compute_rms_segment_dbfs
    t = np.linspace(0, 1, 44100, endpoint=False)
    signal = np.sin(2 * np.pi * 440 * t)
    path = _write_wav(signal)
    try:
        assert abs(compute_rms_dbfs(path) - compute_rms_segment_dbfs(path, 0.0, 1.0)) < 0.01
    finally:
        os.unlink(path)


def test_stereo_wav_is_averaged_to_mono():
    """Stereo file with identical channels should give same result as mono."""
    from acoustic.compute_rms import compute_rms_dbfs
    t = np.linspace(0, 1, 44100, endpoint=False)
    mono = np.sin(2 * np.pi * 440 * t)
    stereo = np.column_stack([mono, mono])
    path_mono = _write_wav(mono)
    path_stereo = _write_wav(stereo)
    try:
        assert abs(compute_rms_dbfs(path_mono) - compute_rms_dbfs(path_stereo)) < 0.01
    finally:
        os.unlink(path_mono)
        os.unlink(path_stereo)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest analysis/tests/test_compute_rms.py -v
```

Expected: `ImportError: cannot import name 'compute_rms_dbfs' from 'acoustic.compute_rms'` (module doesn't exist yet).

- [ ] **Step 3: Implement compute_rms.py**

`analysis/acoustic/compute_rms.py`:
```python
import numpy as np
import soundfile as sf


def compute_rms_dbfs(wav_path: str) -> float:
    """
    Compute full-file RMS level in dBFS (decibels relative to full scale).
    soundfile reads float in [-1.0, 1.0], so 0 dBFS = full scale.
    Returns float('-inf') for silence.
    """
    data, _ = sf.read(wav_path, dtype='float64')
    if data.ndim > 1:
        data = data.mean(axis=1)   # mix stereo/multi-channel to mono
    rms = np.sqrt(np.mean(data ** 2))
    if rms == 0.0:
        return float('-inf')
    return 20.0 * np.log10(rms)


def compute_rms_segment_dbfs(wav_path: str, start_s: float, duration_s: float) -> float:
    """
    Compute RMS level in dBFS for a time segment [start_s, start_s + duration_s].
    Returns float('-inf') for silence.
    """
    data, samplerate = sf.read(wav_path, dtype='float64')
    if data.ndim > 1:
        data = data.mean(axis=1)
    start = int(start_s * samplerate)
    end = int((start_s + duration_s) * samplerate)
    segment = data[start:end]
    rms = np.sqrt(np.mean(segment ** 2))
    if rms == 0.0:
        return float('-inf')
    return 20.0 * np.log10(rms)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest analysis/tests/test_compute_rms.py -v
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add analysis/acoustic/compute_rms.py analysis/tests/test_compute_rms.py
git commit -m "feat: add RMS computation module with dBFS conversion"
```

---

## Task 3: Directivity Plot Module

**Files:**
- Create: `analysis/acoustic/plot_directivity.py`
- Create: `analysis/tests/test_plot_directivity.py`

- [ ] **Step 1: Write the failing tests**

`analysis/tests/test_plot_directivity.py`:
```python
import os
import tempfile


def test_normalise_shifts_max_to_zero():
    from acoustic.plot_directivity import normalise_directivity
    data = {0: -20.0, 45: -23.0, 90: -18.0, 135: -25.0}
    result = normalise_directivity(data)
    assert result[90] == 0.0                    # max becomes 0
    assert abs(result[0]  - (-2.0)) < 1e-9
    assert abs(result[45] - (-5.0)) < 1e-9
    assert abs(result[135]- (-7.0)) < 1e-9


def test_normalise_preserves_relative_differences():
    from acoustic.plot_directivity import normalise_directivity
    data = {0: -10.0, 90: -20.0, 180: -15.0}
    result = normalise_directivity(data)
    assert abs((result[0] - result[90])  - 10.0) < 1e-9
    assert abs((result[0] - result[180]) -  5.0) < 1e-9


def test_combine_takes_max_at_each_angle():
    from acoustic.plot_directivity import combine_array_directivity
    ch1 = {0: -20.0, 90: -10.0, 180: -25.0, 270: -15.0}
    ch2 = {0: -15.0, 90: -20.0, 180: -12.0, 270: -18.0}
    result = combine_array_directivity([ch1, ch2])
    assert result[0]   == -15.0   # ch2 louder
    assert result[90]  == -10.0   # ch1 louder
    assert result[180] == -12.0   # ch2 louder
    assert result[270] == -15.0   # ch1 louder


def test_combine_single_channel_returns_same_data():
    from acoustic.plot_directivity import combine_array_directivity
    ch = {0: -20.0, 45: -22.0, 90: -19.0}
    assert combine_array_directivity([ch]) == ch


def test_combine_mismatched_angles_raises_value_error():
    from acoustic.plot_directivity import combine_array_directivity
    ch1 = {0: -20.0, 90: -10.0}
    ch2 = {0: -15.0, 45: -20.0}
    try:
        combine_array_directivity([ch1, ch2])
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_combine_empty_list_raises_value_error():
    from acoustic.plot_directivity import combine_array_directivity
    try:
        combine_array_directivity([])
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_plot_directivity_creates_nonempty_png():
    from acoustic.plot_directivity import plot_directivity
    configs = {
        'Config A': {0: -20.0, 45: -24.0, 90: -18.0, 135: -26.0,
                     180: -22.0, 225: -25.0, 270: -19.0, 315: -23.0}
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'dir.png')
        plot_directivity(configs, path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1024   # at least 1 KB
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest analysis/tests/test_plot_directivity.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement plot_directivity.py**

`analysis/acoustic/plot_directivity.py`:
```python
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict


def normalise_directivity(angle_to_level: Dict[float, float]) -> Dict[float, float]:
    """
    Normalise directivity data to 0 dB at the maximum level.
    Returns a new dict with levels shifted so the highest = 0 dB.
    """
    max_level = max(angle_to_level.values())
    return {angle: level - max_level for angle, level in angle_to_level.items()}


def combine_array_directivity(channels: list) -> Dict[float, float]:
    """
    Combine multiple HydroMoth channels by taking the maximum level at each angle.
    channels: list of dicts, each mapping angle_deg -> level_dbfs.
    All dicts must have identical angle sets.
    Returns {angle_deg: max_level_dbfs}.
    """
    if not channels:
        raise ValueError("channels list is empty")
    angles = sorted(channels[0].keys())
    for ch in channels[1:]:
        if sorted(ch.keys()) != angles:
            raise ValueError("All channels must have identical angle sets")
    return {angle: max(ch[angle] for ch in channels) for angle in angles}


def plot_directivity(configs: Dict[str, Dict[float, float]], output_path: str) -> None:
    """
    Plot overlaid normalised polar directivity for one or more configurations.

    configs: {'Config A': {0: -20.1, 45: -24.3, ...}, 'Config B': {...}, ...}
             angles in degrees (0 = front of hydrophone), levels in dBFS.
    Normalises each configuration independently before plotting.
    Saves PNG to output_path.
    """
    fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(8, 8))

    for label, data in configs.items():
        normalised = normalise_directivity(data)
        angles_deg = sorted(normalised.keys())
        levels = [normalised[a] for a in angles_deg]
        # Close the loop for polar plot
        angles_rad = [np.deg2rad(a) for a in angles_deg] + [np.deg2rad(angles_deg[0])]
        levels_closed = levels + [levels[0]]
        ax.plot(angles_rad, levels_closed, label=label, linewidth=2, marker='o', markersize=5)

    ax.set_theta_zero_location('N')    # 0° at top
    ax.set_theta_direction(-1)         # clockwise
    ax.set_rlim(-30, 0)
    ax.set_rticks([-30, -20, -10, 0])
    ax.set_rlabel_position(45)
    ax.legend(loc='lower right', bbox_to_anchor=(1.35, -0.05))
    ax.set_title(
        'HydroMoth Directivity Comparison\n(normalised, 10 kHz tone, 1 m distance)',
        pad=20
    )
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest analysis/tests/test_plot_directivity.py -v
```

Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add analysis/acoustic/plot_directivity.py analysis/tests/test_plot_directivity.py
git commit -m "feat: add directivity normalisation and polar plot module"
```

---

## Task 4: Frequency Response Plot Module

**Files:**
- Create: `analysis/acoustic/plot_frequency_response.py`
- Create: `analysis/tests/test_plot_frequency_response.py`

- [ ] **Step 1: Write the failing tests**

`analysis/tests/test_plot_frequency_response.py`:
```python
import os
import tempfile


def test_normalise_sets_1khz_to_zero():
    from acoustic.plot_frequency_response import normalise_frequency_response
    freqs  = [1000, 2000, 5000, 10000, 20000]
    levels = [-30.0, -32.0, -35.0, -38.0, -42.0]
    result = normalise_frequency_response(freqs, levels)
    assert result[0] == 0.0


def test_normalise_preserves_relative_differences():
    from acoustic.plot_frequency_response import normalise_frequency_response
    freqs  = [1000, 2000, 5000]
    levels = [-30.0, -34.0, -36.0]
    result = normalise_frequency_response(freqs, levels)
    assert abs(result[1] - (-4.0)) < 1e-9
    assert abs(result[2] - (-6.0)) < 1e-9


def test_normalise_flat_response_returns_all_zeros():
    from acoustic.plot_frequency_response import normalise_frequency_response
    freqs  = [1000, 2000, 5000, 10000, 20000]
    levels = [-25.0, -25.0, -25.0, -25.0, -25.0]
    result = normalise_frequency_response(freqs, levels)
    assert all(abs(v) < 1e-9 for v in result)


def test_normalise_raises_without_1khz():
    from acoustic.plot_frequency_response import normalise_frequency_response
    try:
        normalise_frequency_response([2000, 5000, 10000], [-30.0, -32.0, -35.0])
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_plot_creates_nonempty_png():
    from acoustic.plot_frequency_response import plot_frequency_response
    freqs  = [1000, 2000, 5000, 10000, 20000]
    levels = [-30.0, -32.0, -35.0, -38.0, -42.0]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'freq.png')
        plot_frequency_response(freqs, levels, path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1024
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest analysis/tests/test_plot_frequency_response.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement plot_frequency_response.py**

`analysis/acoustic/plot_frequency_response.py`:
```python
import matplotlib.pyplot as plt
from typing import List


def normalise_frequency_response(
    freqs_hz: List[float],
    levels_dbfs: List[float]
) -> List[float]:
    """
    Normalise frequency response to 0 dB at the 1 kHz reference point.
    Returns list of normalised levels in same order as input.
    Raises ValueError if 1000 Hz is not in freqs_hz.
    """
    if 1000 not in freqs_hz:
        raise ValueError("1 kHz reference (1000 Hz) must be present in freqs_hz")
    ref_level = levels_dbfs[freqs_hz.index(1000)]
    return [level - ref_level for level in levels_dbfs]


def plot_frequency_response(
    freqs_hz: List[float],
    levels_dbfs: List[float],
    output_path: str
) -> None:
    """
    Plot relative frequency response normalised to 1 kHz.
    freqs_hz    : [1000, 2000, 5000, 10000, 20000]
    levels_dbfs : measured RMS dBFS at each frequency (same order)
    Saves PNG to output_path.
    """
    normalised = normalise_frequency_response(freqs_hz, levels_dbfs)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.semilogx(freqs_hz, normalised, marker='o', linewidth=2, color='steelblue')
    ax.axhline(0, color='gray', linestyle='--', linewidth=0.8, label='0 dB ref (1 kHz)')
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Relative Level (dB re 1 kHz)')
    ax.set_title('HydroMoth Relative Frequency Response\n(single unit, 0.5 m, bucket)')
    ax.grid(True, which='both', alpha=0.3)
    ax.set_xticks(freqs_hz)
    ax.set_xticklabels([f'{int(f // 1000)}k' for f in freqs_hz])
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest analysis/tests/test_plot_frequency_response.py -v
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add analysis/acoustic/plot_frequency_response.py analysis/tests/test_plot_frequency_response.py
git commit -m "feat: add frequency response normalisation and plot module"
```

---

## Task 5: Power Validation Module

**Files:**
- Create: `analysis/power_budget/validate_power.py`
- Create: `analysis/tests/test_validate_power.py`

- [ ] **Step 1: Write the failing tests**

`analysis/tests/test_validate_power.py`:
```python
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
    try:
        compare_power_measurements({'Pi active': 800.0}, {'Pi sleep': 10.0})
        assert False, "Expected ValueError"
    except ValueError:
        pass


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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest analysis/tests/test_validate_power.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement validate_power.py**

`analysis/power_budget/validate_power.py`:
```python
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

    active_fraction: fraction of time in active state, e.g. 70/600 = 0.1167
    Arduino is assumed to run continuously.
    Returns float (days).
    """
    sleep_fraction = 1.0 - active_fraction
    avg_pi_mA = active_mA * active_fraction + sleep_mA * sleep_fraction
    total_avg_mA = avg_pi_mA + arduino_mA
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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest analysis/tests/test_validate_power.py -v
```

Expected: `6 passed`.

- [ ] **Step 5: Run the full test suite**

```bash
pytest analysis/tests/ -v
```

Expected: all tests pass (`test_compute_rms`: 5, `test_plot_directivity`: 7, `test_plot_frequency_response`: 5, `test_validate_power`: 6 — 23 total).

- [ ] **Step 6: Commit**

```bash
git add analysis/power_budget/validate_power.py analysis/tests/test_validate_power.py
git commit -m "feat: add power validation module — compare modelled vs measured current"
```

---

## Task 6: Analysis Runner Scripts

**Files:**
- Create: `analysis/run_analysis.py`
- Create: `analysis/run_power_validation.py`

These scripts have a `DATA SECTION` the user fills in after completing physical tests. They are not unit-tested — the underlying modules are.

- [ ] **Step 1: Create run_analysis.py**

`analysis/run_analysis.py`:
```python
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
```

- [ ] **Step 2: Create run_power_validation.py**

`analysis/run_power_validation.py`:
```python
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
```

- [ ] **Step 3: Verify runner scripts execute without error (no data filled in yet)**

```bash
python analysis/run_analysis.py
```

Expected output (all `None` placeholders):
```
AquaEye-Sentient Acoustic Analysis
========================================
Test 1.1 — Noise floor: not filled in yet
Test 1.2 — Frequency response: not filled in yet
Tests 1.3/2.1/2.2 — Directivity: no config data filled in yet
```

```bash
python analysis/run_power_validation.py
```

Expected: `Not ready — fill in MEASURED_mA for: [...]`

- [ ] **Step 4: Commit**

```bash
git add analysis/run_analysis.py analysis/run_power_validation.py
git commit -m "feat: add analysis runner scripts with data section placeholders"
```

---

## Task 7: Test Log Templates

**Files:**
- Create: `docs/test_logs/phase1_acoustic_log.md`
- Create: `docs/test_logs/phase2_config_comparison_log.md`
- Create: `docs/test_logs/phase3_benchmark_log.md`
- Create: `docs/test_logs/phase4_power_log.md`
- Create: `docs/test_logs/phase5_integration_log.md`

- [ ] **Step 1: Create phase1_acoustic_log.md**

`docs/test_logs/phase1_acoustic_log.md`:
```markdown
# Phase 1 Acoustic Test Log — Single HydroMoth Characterisation

**Date:** ___________
**Tester:** Fazley Alahi
**HydroMoth unit used:** _____ (A / B / C)
**Sound source:** _____ (waterproof speaker / phone in bag)
**Water temperature:** _____ °C

---

## Test 1.1 — Noise Floor

**Depth:** ~0.5 m
**Duration:** 60 s

| Environment | Recording filename | RMS (dBFS) | Notes |
|-------------|-------------------|------------|-------|
| Bucket      |                   |            |       |
| Pool        |                   |            |       |

Environmental contribution (pool − bucket): _____ dB

---

## Test 1.2 — Frequency Response

**Environment:** Bucket (0.5 m), then pool (1 m)
**HydroMoth facing directly at source (0°)**

### Bucket (0.5 m)

| Frequency (Hz) | Recording filename | RMS (dBFS) | Relative (dB re 1 kHz) |
|---------------|-------------------|------------|------------------------|
| 1,000         |                   |            | 0.0 (reference)        |
| 2,000         |                   |            |                        |
| 5,000         |                   |            |                        |
| 10,000        |                   |            |                        |
| 20,000        |                   |            |                        |

### Pool (1 m)

| Frequency (Hz) | Recording filename | RMS (dBFS) | Relative (dB re 1 kHz) |
|---------------|-------------------|------------|------------------------|
| 1,000         |                   |            | 0.0 (reference)        |
| 2,000         |                   |            |                        |
| 5,000         |                   |            |                        |
| 10,000        |                   |            |                        |
| 20,000        |                   |            |                        |

---

## Test 1.3 — Directivity Pattern (Config A)

**Environment:** Swimming pool
**Distance:** 1.0 m (tape measure)
**Tone frequency:** 10 kHz
**Recording duration per angle:** ~10 s

| Angle (°) | Recording filename | RMS (dBFS) | Normalised (dB) |
|----------|-------------------|------------|-----------------|
| 0        |                   |            |                 |
| 45       |                   |            |                 |
| 90       |                   |            |                 |
| 135      |                   |            |                 |
| 180      |                   |            |                 |
| 225      |                   |            |                 |
| 270      |                   |            |                 |
| 315      |                   |            |                 |

**Max level angle:** _____°
**Min level angle:** _____°
**Dynamic range (max − min):** _____ dB

---

## Observations / Anomalies

_Write any unexpected behaviour, equipment issues, or conditions that differ from the protocol here._
```

- [ ] **Step 2: Create phase2_config_comparison_log.md**

`docs/test_logs/phase2_config_comparison_log.md`:
```markdown
# Phase 2 Test Log — Multi-Unit Configuration Comparison

**Date:** ___________
**Tester:** Fazley Alahi
**Environment:** Swimming pool
**Distance:** 1.0 m
**Tone frequency:** 10 kHz
**Mounting frame material:** _____

---

## Test 2.1 — Config B: 2× HydroMoths Back-to-Back (180°)

**Units used:** HM-_____ (facing front) and HM-_____ (facing rear)

| Angle (°) | CH1 filename | CH1 RMS (dBFS) | CH2 filename | CH2 RMS (dBFS) | Combined max (dBFS) |
|----------|-------------|----------------|-------------|----------------|---------------------|
| 0        |             |                |             |                |                     |
| 45       |             |                |             |                |                     |
| 90       |             |                |             |                |                     |
| 135      |             |                |             |                |                     |
| 180      |             |                |             |                |                     |
| 225      |             |                |             |                |                     |
| 270      |             |                |             |                |                     |
| 315      |             |                |             |                |                     |

**Observed dynamic range (max − min combined):** _____ dB

---

## Test 2.2 — Config C: 3× HydroMoths at 120°

**Units used:** HM-_____ (0°), HM-_____ (120°), HM-_____ (240°)

| Angle (°) | CH1 RMS (dBFS) | CH2 RMS (dBFS) | CH3 RMS (dBFS) | Combined max (dBFS) |
|----------|----------------|----------------|----------------|---------------------|
| 0        |                |                |                |                     |
| 45       |                |                |                |                     |
| 90       |                |                |                |                     |
| 135      |                |                |                |                     |
| 180      |                |                |                |                     |
| 225      |                |                |                |                     |
| 270      |                |                |                |                     |
| 315      |                |                |                |                     |

**Observed dynamic range (max − min combined):** _____ dB

---

## Config Comparison Summary

| Configuration | Dynamic range (dB) | Max null depth (dB) | Omnidirectional? |
|--------------|-------------------|---------------------|-----------------|
| Config A (single) | (from Phase 1) | | |
| Config B (back-to-back) | | | |
| Config C (120°) | | | |

---

## Observations / Anomalies
```

- [ ] **Step 3: Create phase3_benchmark_log.md**

`docs/test_logs/phase3_benchmark_log.md`:
```markdown
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
cd SentientCore && python3 tests/pipeline_benchmark.py \
  --wav_dir ~/aquaeye/bench_wav \
  --cycles 10 \
  --no_serial \
  --generate_wav
```

**Date run:** _____

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
cd SentientCore && python3 tests/pipeline_benchmark.py \
  --wav_dir ~/aquaeye/bench_wav \
  --cycles 10 \
  --no_serial
```

**Date run:** _____

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

## D.2 Assumption Comparison

| Assumption | Budgeted | Synthetic result | Real WAV result | Final status |
|-----------|----------|-----------------|----------------|-------------|
| A3: encode time/file | 8.0 s | | | |
| A4: total active window | 70.0 s | | | |

**If REVISE:** Updated D.2 values: encode = _____ s, total active = _____ s
**Corrected deployment duration (if revised):** _____ days

---

## Notes
```

- [ ] **Step 4: Create phase4_power_log.md**

`docs/test_logs/phase4_power_log.md`:
```markdown
# Phase 4 Test Log — Power Consumption Measurement

**Date:** ___________
**Tester:** Fazley Alahi
**Multimeter model:** _____
**Measurement mode:** DC current (mA range)
**Supply voltage:** 5.0 V
**Setup:** Multimeter in series with positive supply line to Pi

**Method:** Take mean of ~5 readings over 10 seconds per state.

---

## Test 4.1 — Pi RTC Sleep State

| Reading | mA |
|---------|----|
| 1 |  |
| 2 |  |
| 3 |  |
| 4 |  |
| 5 |  |
| **Mean** | |

---

## Test 4.2 — Pi Active Processing States

### FLAC Encode (CPU-intensive — expected peak)

| Reading | mA |
|---------|----|
| 1 |  |
| 2 |  |
| 3 |  |
| 4 |  |
| 5 |  |
| **Mean** | |

### SD Card Pull / File Writes (I/O-bound)

| Reading | mA |
|---------|----|
| 1 |  |
| 2 |  |
| 3 |  |
| 4 |  |
| 5 |  |
| **Mean** | |

### Wi-Fi Transmission (cloud upload)

| Reading | mA |
|---------|----|
| 1 |  |
| 2 |  |
| 3 |  |
| 4 |  |
| 5 |  |
| **Mean** | |

---

## Test 4.3 — Arduino Sensor Hub (steady-state)

| Reading | mA |
|---------|----|
| 1 |  |
| 2 |  |
| 3 |  |
| 4 |  |
| 5 |  |
| **Mean** | |

---

## D.2 Comparison Summary

| State | D.2 Modelled (mA) | Measured mean (mA) | Error (%) |
|-------|------------------|-------------------|-----------|
| Pi active — FLAC encode |  |  |  |
| Pi active — SD card pull |  |  |  |
| Pi active — Wi-Fi upload |  |  |  |
| Pi RTC sleep |  |  |  |
| Arduino steady-state |  |  |  |

**Corrected deployment duration (from run_power_validation.py):** _____ days
**D.2 modelled deployment duration:** _____ days

---

## Notes / Anomalies
```

- [ ] **Step 5: Create phase5_integration_log.md**

`docs/test_logs/phase5_integration_log.md`:
```markdown
# Phase 5 Test Log — End-to-End Integration Test

**Date:** ___________
**Tester:** Fazley Alahi
**Pi hostname / IP:** _____
**Arduino connected:** Yes / No
**Wi-Fi hotspot:** Yes / No
**SD cards:** 3× HydroMoth (Phase 2 recordings loaded)

---

## Test 5.1 — SD Card Pull to FLAC

| Check | Pass | Notes |
|-------|------|-------|
| All 3 HydroMoth SD cards pulled without error | | |
| Session stitcher grouped all 3 units into same session | | |
| FLAC file produced for each of the 3 channels | | |
| JSON sidecar written for each FLAC | | |
| JSON contains correct `hydromoth_id` field | | |
| JSON contains correct `sample_rate` field | | |
| JSON contains valid `session_id` (shared across 3 files) | | |

**Overall: PASS / FAIL**

---

## Test 5.2 — Serial Integration (Arduino)

| Check | Pass | Notes |
|-------|------|-------|
| Serial reader daemon starts without error | | |
| GPS reading present in JSON sidecar | | |
| TDS reading present in JSON sidecar | | |
| Turbidity reading present in JSON sidecar | | |

**Overall: PASS / FAIL**

---

## Test 5.3 — Cloud Upload (Google Drive)

| Check | Pass | Notes |
|-------|------|-------|
| Wi-Fi detected before upload attempt | | |
| FLAC files appear in Google Drive folder | | |
| JSON sidecar files appear alongside FLAC files | | |
| No orphaned FLAC files without a matching JSON | | |

**Overall: PASS / FAIL**

---

## Test 5.4 — Resilience Check

| Failure injected | Expected behaviour | Actual behaviour | Pass |
|-----------------|-------------------|-----------------|------|
| One SD card removed mid-pull | Other 2 cards process normally; error logged for missing card | | |
| Arduino disconnected mid-cycle | Pipeline continues; sensor fields null in JSON | | |
| Wi-Fi disabled before upload | Upload step skipped gracefully; FLAC/JSON retained locally | | |

**Overall: PASS / FAIL**

---

## Known Failures / Limitations

_List any tests that failed and the suspected cause._

---

## Notes
```

- [ ] **Step 6: Commit**

```bash
git add docs/test_logs/
git commit -m "docs: add test log templates for all 5 test phases"
```

---

## Task 8: Phase 1 Execution — Bucket Tests (Noise Floor + Frequency Response)

**Equipment needed:** 1× HydroMoth, bucket, waterproof speaker or phone in bag, tone generator app, tape measure, laptop.

These steps are physical procedure — no code to write.

- [ ] **Step 1: Prepare the recording environment**

Fill bucket with tap water (ideally let it settle for 5 minutes to reduce surface turbulence from filling). Set up on a stable surface away from loud HVAC or foot traffic. HydroMoth should be connected to SD card (freshly formatted).

- [ ] **Step 2: Test 1.1 — Noise floor, bucket**

- Configure HydroMoth for continuous recording (or 1-minute scheduled recording)
- Submerge HydroMoth to ~0.5 m depth (use a string to hold it at depth)
- Record 60 seconds of silence — no active sound source, minimal vibration
- Remove SD card, copy WAV file to laptop
- Run: `python -c "from analysis.acoustic.compute_rms import compute_rms_dbfs; print(compute_rms_dbfs('your_file.wav'))"`
- Record RMS dBFS result in `docs/test_logs/phase1_acoustic_log.md` → Test 1.1

- [ ] **Step 3: Test 1.2 — Frequency response, bucket**

- Keep HydroMoth at 0.5 m, facing directly at where you will place the speaker
- Place sound source at 0.5 m horizontal distance from HydroMoth face, same depth
- For each frequency (1, 2, 5, 10, 20 kHz): play tone from tone generator app, record ~10 seconds
- Keep source volume consistent across all frequencies (same app volume setting)
- Between frequencies: stop recording, change frequency, resume recording (or record all as one file and use `compute_rms_segment_dbfs` with appropriate timestamps)
- Copy recordings to laptop. Run `compute_rms_dbfs` on each file (or segment)
- Fill in the Bucket table in Test 1.2 of the log

- [ ] **Step 4: Test 1.2 — Frequency response, pool (1 m)**

- Repeat Step 3 in the swimming pool at 1 m source distance
- Fill in the Pool table in Test 1.2 of the log

- [ ] **Step 5: Compute and record relative response**

For each environment: note the RMS at 1 kHz as the reference. Subtract it from each other frequency's RMS to get the relative response in dB. Fill the "Relative" column.

Alternatively run:
```bash
python analysis/run_analysis.py
```
after filling in `FREQ_RESPONSE_LEVELS_DBFS` in `run_analysis.py`.

- [ ] **Step 6: Commit the filled-in log**

```bash
git add docs/test_logs/phase1_acoustic_log.md
git commit -m "data: phase 1 noise floor and frequency response results"
```

---

## Task 9: Phase 1 Execution — Pool Directivity (Single HydroMoth)

**Equipment needed:** 1× HydroMoth, swimming pool, waterproof speaker, tape measure, string/rope for marking distances.

- [ ] **Step 1: Mark the test geometry**

Choose a clear section of pool. Place the sound source at a fixed point. Using the tape measure, mark eight positions at 1.0 m radius from the source, at 45° increments. Chalk or tape on the pool edge can mark angles; physically move the HydroMoth to each position.

Angle 0° = HydroMoth face directly toward the speaker.

- [ ] **Step 2: Run Test 1.3 — 8 positions**

For each angle (0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°):
1. Position HydroMoth at the correct distance and angle
2. Ensure consistent depth (~0.5 m)
3. Play continuous 10 kHz tone from the speaker
4. Record ~10 seconds
5. Stop recording before moving to the next angle
6. Label each recording with the angle (e.g. `config_a_000deg.wav`)

- [ ] **Step 3: Process recordings on laptop**

For each recording:
```python
from analysis.acoustic.compute_rms import compute_rms_dbfs
print(compute_rms_dbfs('config_a_000deg.wav'))   # repeat for each angle
```

Fill in the RMS dBFS column in Test 1.3 of the log.

- [ ] **Step 4: Compute normalised values**

Identify the maximum RMS across all 8 angles. Subtract this from each angle's value to normalise (max = 0 dB). Fill the "Normalised" column.

- [ ] **Step 5: Generate Config A polar plot**

In `run_analysis.py`, fill in `CONFIG_A` with the 8 measured RMS values, then:
```bash
python analysis/run_analysis.py
```

Check `analysis/figures/directivity_comparison.png` — should show Config A polar plot.

- [ ] **Step 6: Commit**

```bash
git add docs/test_logs/phase1_acoustic_log.md analysis/run_analysis.py
git commit -m "data: phase 1 directivity — Config A single HydroMoth results"
```

---

## Task 10: Phase 2 Execution — Config B and C Directivity

**Equipment needed:** 3× HydroMoths, rigid mounting frame (PVC pipe or wooden dowel), swimming pool, waterproof speaker, tape measure.

- [ ] **Step 1: Build Config B mount**

Mount 2 HydroMoths facing exactly opposite directions (180° apart) on the rigid frame. Use cable ties or tape to hold them firmly. Label which is CH1 (faces 0°) and CH2 (faces 180°). Both must be submerged at the same depth during testing.

- [ ] **Step 2: Run Test 2.1 — Config B directivity**

Repeat the exact same protocol as Test 1.3 (1 m, 10 kHz, 8 positions × 45°), but record both HydroMoths simultaneously at each angle. Label recordings: `config_b_000deg_ch1.wav`, `config_b_000deg_ch2.wav`, etc.

- [ ] **Step 3: Process Config B recordings**

For each angle, run `compute_rms_dbfs` on both channel recordings. Fill the CH1 RMS and CH2 RMS columns in phase2_config_comparison_log.md. Compute the combined max (the higher of CH1 or CH2 at each angle).

- [ ] **Step 4: Rebuild mount for Config C**

Remount all 3 HydroMoths at 120° spacing. Label CH1 (0°), CH2 (120°), CH3 (240°). Check that all three are secured and will maintain their angles underwater.

- [ ] **Step 5: Run Test 2.2 — Config C directivity**

Repeat the protocol again for all 8 positions, recording all 3 channels simultaneously.

- [ ] **Step 6: Process Config C recordings and fill log**

Compute `compute_rms_dbfs` for all 3 channels at each angle. Fill the log table. Compute the combined max (highest of 3 channels per angle).

- [ ] **Step 7: Generate three-way comparison figure**

Fill in `CONFIG_B_CH1`, `CONFIG_B_CH2`, `CONFIG_C_CH1`, `CONFIG_C_CH2`, `CONFIG_C_CH3` in `analysis/run_analysis.py`, then:
```bash
python analysis/run_analysis.py
```

Check `analysis/figures/directivity_comparison.png` — should show all three configs overlaid.

- [ ] **Step 8: Commit**

```bash
git add docs/test_logs/phase2_config_comparison_log.md analysis/run_analysis.py
git commit -m "data: phase 2 directivity — Config B and C results with three-way comparison"
```

---

## Task 11: Phase 3 — Pi Benchmark (Synthetic WAVs)

**Equipment needed:** Raspberry Pi 5 with SSH access, laptop on same Wi-Fi hotspot.

- [ ] **Step 1: SSH into Pi and verify code is up to date**

```bash
ssh pi@<PI_IP_ADDRESS>
cd ~/AquaEye-Sentient    # or wherever the repo is cloned on the Pi
git pull
```

- [ ] **Step 2: Install Pi dependencies if not already done**

```bash
cd SentientCore/raspberry_pi
pip3 install soundfile pyserial requests google-api-python-client google-auth-oauthlib
```

Also verify the `flac` CLI is installed:
```bash
flac --version
```

If missing: `sudo apt install flac`

- [ ] **Step 3: Create bench_wav directory and generate synthetic WAVs**

```bash
mkdir -p ~/aquaeye/bench_wav
cd ~/AquaEye-Sentient/SentientCore/raspberry_pi
python3 ../tests/pipeline_benchmark.py \
  --generate_wav \
  --wav_dir ~/aquaeye/bench_wav \
  --files 6
```

Expected: 6 WAV files created, each ~11 MB (60 s × 96 kHz × 16-bit mono).

- [ ] **Step 4: Run Test 3.1 — synthetic benchmark, 10 cycles**

```bash
python3 ../tests/pipeline_benchmark.py \
  --wav_dir ~/aquaeye/bench_wav \
  --cycles 10 \
  --no_serial
```

Press ENTER when prompted. Let it complete all 10 cycles.

**If you get `ModuleNotFoundError: No module named 'audio_processor'`:** the benchmark imports pipeline modules from `raspberry_pi/`. Run from there instead:
```bash
cd ~/AquaEye-Sentient/SentientCore && python3 tests/pipeline_benchmark.py \
  --wav_dir ~/aquaeye/bench_wav --cycles 10 --no_serial
```

- [ ] **Step 5: Record results in phase3_benchmark_log.md**

Copy the aggregate table output into `docs/test_logs/phase3_benchmark_log.md` → Test 3.1. Note A3 and A4 status (OK / REVISE).

- [ ] **Step 6: Commit**

```bash
git add docs/test_logs/phase3_benchmark_log.md
git commit -m "data: phase 3 synthetic benchmark results on Pi 5"
```

---

## Task 12: Phase 3 — Pi Benchmark (Real HydroMoth WAVs)

**Prerequisite:** Phase 1 acoustic tests completed; real HydroMoth WAV files available.

- [ ] **Step 1: Transfer real HydroMoth WAV files to Pi**

From laptop, copy Phase 1 recordings (the single-HydroMoth directivity recordings work well — they are real 96 kHz audio):
```bash
scp /path/to/hydromoth_recordings/*.WAV pi@<PI_IP_ADDRESS>:~/aquaeye/bench_wav/
```

Ensure at least 6 files, named in HydroMoth format (`YYYYMMDD_HHMMSS.WAV`). Rename if needed.

- [ ] **Step 2: Run Test 3.2 — real WAV benchmark, 10 cycles**

```bash
ssh pi@<PI_IP_ADDRESS>
cd ~/AquaEye-Sentient/SentientCore/raspberry_pi
python3 ../tests/pipeline_benchmark.py \
  --wav_dir ~/aquaeye/bench_wav \
  --cycles 10 \
  --no_serial
```

- [ ] **Step 3: Record results in log**

Fill in the Test 3.2 table in `phase3_benchmark_log.md`. Fill in the D.2 assumption comparison table.

If A3 or A4 show REVISE: note the corrected values. These feed into `run_power_validation.py` (update `ACTIVE_FRACTION` if the active window changed materially).

- [ ] **Step 4: Commit**

```bash
git add docs/test_logs/phase3_benchmark_log.md
git commit -m "data: phase 3 real WAV benchmark results — A3/A4 validation complete"
```

---

## Task 13: Phase 4 — Power Measurements

**Equipment needed:** Multimeter in DC mA mode, Pi 5, Arduino with sensor_hub.ino loaded, 5V USB supply, a way to break the positive 5V supply line (e.g. a USB cable with the positive wire exposed, or a USB breakout board).

- [ ] **Step 1: Set up multimeter in series**

Put the multimeter in DC current mode (mA range — typically 200 mA or 2 A range). Wire it in series with the positive 5V supply to the Pi: supply+ → multimeter COM → multimeter mA → Pi 5V pin. Negative supply connects directly to Pi GND.

**Safety:** Double-check polarity before powering on. Incorrect polarity or wrong multimeter range can blow the multimeter fuse.

- [ ] **Step 2: Test 4.1 — RTC sleep current**

Boot Pi. SSH in and run the RTC halt command (from `main.py` logic):
```bash
sudo rtcwake -m off -s 600    # halt for 600 s (wake not needed — measure sleep current)
```

Once Pi halts, take 5 multimeter readings over ~10 seconds. Record all 5 in `phase4_power_log.md` → Test 4.1. Calculate mean.

**Note:** If the Pi does not have an RTC module yet, measure the current with the Pi powered off (just the 5V rail energised) as an approximation. Document this substitution.

- [ ] **Step 3: Test 4.2 — Active processing states**

Boot Pi. SSH in. Run the pipeline benchmark (this provides a controlled active workload):
```bash
cd ~/AquaEye-Sentient/SentientCore/raspberry_pi
python3 ../tests/pipeline_benchmark.py --wav_dir ~/aquaeye/bench_wav --cycles 3 --no_serial
```

While it runs:
- During FLAC encode phase (benchmark prints `encode=...`): take 5 readings → record as "FLAC encode (peak)"
- During stitch/metadata (fast, ~1–2 s): take readings as quickly as possible → "SD card pull" (staging I/O is similar)
- Then trigger a cloud upload cycle by running `main.py --once` with Wi-Fi active: take readings during upload → "Wi-Fi upload"

Record all in `phase4_power_log.md` → Test 4.2. Calculate means.

- [ ] **Step 4: Test 4.3 — Arduino steady-state**

Disconnect the Pi (or power it down). Power the Arduino from the 5V supply through the multimeter. Let `sensor_hub.ino` run with all sensors active for 30 seconds to stabilise. Take 5 readings. Record in `phase4_power_log.md` → Test 4.3.

- [ ] **Step 5: Fill in run_power_validation.py and run it**

In `analysis/run_power_validation.py`:
1. Update `MODELLED_mA` dict to match your actual D.2 figures (open D.2 document and copy the values)
2. Fill in `MEASURED_mA` with your 5 mean readings from Tests 4.1–4.3
3. Update `BATTERY_CAPACITY_mAh` from your BOM (D.3 document)

Then run:
```bash
python analysis/run_power_validation.py
```

Copy the output markdown table into `phase4_power_log.md` → D.2 Comparison Summary.

- [ ] **Step 6: Commit**

```bash
git add docs/test_logs/phase4_power_log.md analysis/run_power_validation.py
git commit -m "data: phase 4 power measurements — modelled vs measured comparison complete"
```

---

## Task 14: Phase 5 — End-to-End Integration Test

**Equipment needed:** Pi 5, 3× HydroMoths with SD cards containing Phase 2 recordings, Arduino with sensor_hub.ino, Wi-Fi hotspot, Google Drive credentials on Pi.

- [ ] **Step 1: Verify Pi dependencies and Google Drive credentials**

SSH into Pi:
```bash
cd ~/AquaEye-Sentient/SentientCore/raspberry_pi
python3 -c "import soundfile, serial, requests, googleapiclient; print('OK')"
```

Verify `credentials.json` and `token.json` are present in the working directory (or wherever `cloud_uploader.py` expects them). If not: complete the Google Drive OAuth flow first (run `python3 cloud_uploader.py` and follow the auth URL).

- [ ] **Step 2: Test 5.1 — SD card pull to FLAC**

Insert the 3 HydroMoth SD cards (from Phase 2 recordings) into Pi USB SD card readers. Run one full pipeline cycle:
```bash
cd ~/AquaEye-Sentient/SentientCore/raspberry_pi
python3 main.py --once
```

Check pass criteria (tick each in `phase5_integration_log.md`):
- All 3 units' files appear in `STAGING_FOLDER`
- FLAC output folder contains 3 `.flac` files
- FLAC output folder contains 3 `_meta.json` sidecars
- Open one JSON: verify `hydromoth_id`, `sample_rate`, `session_id` are populated

- [ ] **Step 3: Test 5.2 — Serial integration**

Connect Arduino (USB to Pi). Verify sensor_hub.ino is running (green LED blinks or check `dmesg | grep tty`). Run `main.py --once` again with the Arduino connected. Open a JSON sidecar:
```bash
cat ~/aquaeye/flac/HM_A__<timestamp>.json
```

Check `gps_lat`, `tds_ppm`, and `turbidity_ntu` fields are not null. Tick the serial checks in the integration log.

- [ ] **Step 4: Test 5.3 — Cloud upload**

Ensure Wi-Fi hotspot is active and Pi is connected. Run `main.py --once`. Check Google Drive for FLAC + JSON pairs. Verify no orphaned FLACs (every `.flac` has a matching `.json` in Drive). Tick the upload checks.

- [ ] **Step 5: Test 5.4 — Resilience check**

Run three separate `main.py --once` cycles, each with one deliberate failure:

**Failure 1 — missing SD card:**
- Remove one of the 3 SD card readers before running
- Expected: pipeline logs an error for the missing card, processes the other 2, does not crash
- Check: 2 FLAC + 2 JSON files produced (not 3)

**Failure 2 — Arduino disconnect:**
- Unplug Arduino USB mid-cycle (after it starts but before metadata write)
- Expected: serial reader logs a reconnect attempt, `sensor` fields in JSON are null, pipeline completes
- Check: FLAC and JSON still written with null sensor fields

**Failure 3 — Wi-Fi off:**
- Disable hotspot before running upload phase
- Expected: uploader logs "Wi-Fi not available", exits cleanly, FLAC + JSON remain in local folder
- Check: local FLAC/JSON present; no partial upload artifacts in Drive

Tick or mark FAIL for each in `phase5_integration_log.md`. Note any unexpected behaviour.

- [ ] **Step 6: Commit**

```bash
git add docs/test_logs/phase5_integration_log.md
git commit -m "data: phase 5 end-to-end integration test results"
```

---

## Task 15: Generate Final Figures and Close Out

- [ ] **Step 1: Verify run_analysis.py data section is fully filled in**

Open `analysis/run_analysis.py`. Check that `CONFIG_A`, `CONFIG_B_CH1`, `CONFIG_B_CH2`, `CONFIG_C_CH1/2/3`, `FREQ_RESPONSE_LEVELS_DBFS`, `NOISE_FLOOR_BUCKET_DBFS`, and `NOISE_FLOOR_POOL_DBFS` are all filled in (no `None` values remain).

- [ ] **Step 2: Generate all acoustic figures**

```bash
python analysis/run_analysis.py
```

Expected output:
```
Test 1.1 — Noise Floor
  Bucket : -XX.X dBFS
  Pool   : -XX.X dBFS
  Environmental contribution: +X.X dB

Test 1.2 — Frequency response saved: analysis/figures/freq_response.png

Tests 1.3/2.1/2.2 — Directivity comparison saved: analysis/figures/directivity_comparison.png
  Configs plotted: Config A (single), Config B (back-to-back), Config C (120°)
```

- [ ] **Step 3: Generate power validation output**

```bash
python analysis/run_power_validation.py
```

Copy the markdown table output to `docs/test_logs/phase4_power_log.md` if not already done.

- [ ] **Step 4: Run full test suite one final time**

```bash
pytest analysis/tests/ -v
```

Expected: 23 passed.

- [ ] **Step 5: Final commit**

```bash
git add analysis/run_analysis.py analysis/run_power_validation.py
git commit -m "data: final acoustic analysis figures and power validation complete"
```

---

## Summary

| Task | Type | Dependency |
|------|------|------------|
| 1 — Package scaffold | Software setup | None |
| 2 — RMS module | Software (TDD) | Task 1 |
| 3 — Directivity module | Software (TDD) | Task 1 |
| 4 — Frequency response module | Software (TDD) | Task 1 |
| 5 — Power validation module | Software (TDD) | Task 1 |
| 6 — Runner scripts | Software | Tasks 2–5 |
| 7 — Test log templates | Documentation | None |
| 8 — Phase 1 bucket tests | Physical | Tasks 2, 6, 7 |
| 9 — Phase 1 pool directivity | Physical | Tasks 2, 6, 7 |
| 10 — Phase 2 config B + C | Physical | Tasks 3, 6, 7, 9 |
| 11 — Phase 3 synthetic benchmark | System (Pi) | Pi SSH access |
| 12 — Phase 3 real WAV benchmark | System (Pi) | Tasks 8–9, 11 |
| 13 — Phase 4 power measurements | Physical (multimeter) | Tasks 5, 6, 7 |
| 14 — Phase 5 integration | System (full) | Tasks 8–13 |
| 15 — Final figures + close out | Analysis | Tasks 8–14 |

**Tasks 1–7 and 11 can start in parallel with each other.**
**Tasks 8–10 (acoustic, pool) and 11 (Pi benchmark) can run concurrently.**
