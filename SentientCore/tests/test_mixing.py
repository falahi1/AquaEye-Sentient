import numpy as np
import os
import pytest
import soundfile as sf
import tempfile


SAMPLE_RATE = 96000
DURATION_SEC = 2
N_SAMPLES = SAMPLE_RATE * DURATION_SEC


def _write_wav(path: str, data: np.ndarray, sr: int = SAMPLE_RATE):
    sf.write(path, data.astype(np.int16), sr, subtype="PCM_16")


def test_mix_produces_single_flac(tmp_path):
    from audio_processor import mix_session_to_flac
    wav_paths = []
    for i in range(3):
        data = (np.random.default_rng(i).standard_normal(N_SAMPLES) * 10000).astype(np.int16)
        p = str(tmp_path / f"HM_{i}.WAV")
        _write_wav(p, data)
        wav_paths.append(p)
    flac_path = str(tmp_path / "MIXED__20260401_120000.flac")
    result = mix_session_to_flac(wav_paths, flac_path)
    assert result["success"] is True
    assert os.path.exists(flac_path)


def test_mix_result_has_expected_keys(tmp_path):
    from audio_processor import mix_session_to_flac
    wav_paths = []
    for i in range(3):
        data = (np.random.default_rng(i).standard_normal(N_SAMPLES) * 10000).astype(np.int16)
        p = str(tmp_path / f"HM_{i}.WAV")
        _write_wav(p, data)
        wav_paths.append(p)
    flac_path = str(tmp_path / "MIXED.flac")
    result = mix_session_to_flac(wav_paths, flac_path)
    for key in ("success", "duration_sec", "flac_bytes", "encode_sec", "error"):
        assert key in result


def test_mix_output_duration_matches_input(tmp_path):
    from audio_processor import mix_session_to_flac
    wav_paths = []
    for i in range(3):
        data = (np.random.default_rng(i).standard_normal(N_SAMPLES) * 10000).astype(np.int16)
        p = str(tmp_path / f"HM_{i}.WAV")
        _write_wav(p, data)
        wav_paths.append(p)
    flac_path = str(tmp_path / "MIXED.flac")
    result = mix_session_to_flac(wav_paths, flac_path)
    assert result["success"] is True
    assert abs(result["duration_sec"] - DURATION_SEC) < 0.1


def test_mix_single_file_falls_back_to_convert(tmp_path):
    from audio_processor import mix_session_to_flac
    data = (np.random.default_rng(0).standard_normal(N_SAMPLES) * 10000).astype(np.int16)
    p = str(tmp_path / "HM_A.WAV")
    _write_wav(p, data)
    flac_path = str(tmp_path / "MIXED.flac")
    result = mix_session_to_flac([p], flac_path)
    assert result["success"] is True
    assert os.path.exists(flac_path)


def test_mix_truncates_to_shortest_file(tmp_path):
    from audio_processor import mix_session_to_flac
    wav_paths = []
    lengths = [N_SAMPLES, N_SAMPLES + 1000, N_SAMPLES - 500]
    for i, n in enumerate(lengths):
        data = (np.random.default_rng(i).standard_normal(n) * 10000).astype(np.int16)
        p = str(tmp_path / f"HM_{i}.WAV")
        _write_wav(p, data)
        wav_paths.append(p)
    flac_path = str(tmp_path / "MIXED.flac")
    result = mix_session_to_flac(wav_paths, flac_path)
    assert result["success"] is True
    info = sf.info(flac_path)
    assert info.frames == min(lengths)


def test_mix_normalises_output(tmp_path):
    from audio_processor import mix_session_to_flac
    # Three identical loud signals — sum would clip without normalisation
    wav_paths = []
    data = np.full(N_SAMPLES, 30000, dtype=np.int16)
    for i in range(3):
        p = str(tmp_path / f"HM_{i}.WAV")
        _write_wav(p, data)
        wav_paths.append(p)
    flac_path = str(tmp_path / "MIXED.flac")
    mix_session_to_flac(wav_paths, flac_path)
    mixed, _ = sf.read(flac_path, dtype="float64")
    assert np.max(np.abs(mixed)) <= 1.0 + 1e-6
