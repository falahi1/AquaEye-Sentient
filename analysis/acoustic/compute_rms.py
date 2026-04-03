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
    if end > len(data):
        raise ValueError(
            f"Requested segment [{start_s}s, {start_s + duration_s}s] "
            f"exceeds file length ({len(data) / samplerate:.3f}s)."
        )
    segment = data[start:end]
    rms = np.sqrt(np.mean(segment ** 2))
    if rms == 0.0:
        return float('-inf')
    return 20.0 * np.log10(rms)
