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
