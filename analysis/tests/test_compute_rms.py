import numpy as np
import soundfile as sf
import tempfile
import os


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


def test_segment_beyond_file_length_raises():
    from acoustic.compute_rms import compute_rms_segment_dbfs
    t = np.linspace(0, 1, 44100, endpoint=False)
    signal = np.sin(2 * np.pi * 440 * t)
    path = _write_wav(signal)
    raised = False
    try:
        try:
            compute_rms_segment_dbfs(path, 0.0, 5.0)  # file is only 1 s
        except ValueError:
            raised = True
        assert raised, "Expected ValueError to be raised for out-of-bounds segment"
    finally:
        os.unlink(path)
