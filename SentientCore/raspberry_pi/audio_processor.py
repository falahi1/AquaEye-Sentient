# =============================================================================
# AquaEye-Sentient — audio_processor.py
# =============================================================================
# Converts HydroMoth .WAV files to .FLAC (lossless compression).
#
# Replaces the audio_recorder.py approach from AquaSound (2024-25), which
# used PyAudio to record from the Pi's microphone. HydroMoth records
# autonomously to its own SD card — we only compress what it produces.
#
# Key function:
#   convert_wav_to_flac(wav_path, flac_path)
#     Reads wav_path, writes flac_path, returns a result dict with timing
#     and file size info — timing fields support power budget validation.
# =============================================================================

import os
import time
import logging
import soundfile as sf

logger = logging.getLogger(__name__)


def convert_wav_to_flac(wav_path: str, flac_path: str) -> dict:
    """
    Convert a WAV file to FLAC (lossless).

    Parameters
    ----------
    wav_path  : path to the source .WAV file (from HydroMoth SD card)
    flac_path : path where the output .FLAC should be written
                (parent directory must exist)

    Returns
    -------
    dict with keys:
        success       (bool)
        duration_sec  (float) — audio duration in seconds
        wav_bytes     (int)   — input file size in bytes
        flac_bytes    (int)   — output file size in bytes
        encode_sec    (float) — wall-clock time for the conversion
        error         (str | None)
    """
    result = {
        "success":      False,
        "duration_sec": None,
        "wav_bytes":    None,
        "flac_bytes":   None,
        "encode_sec":   None,
        "error":        None,
    }

    try:
        wav_bytes = os.path.getsize(wav_path)
        result["wav_bytes"] = wav_bytes

        t0 = time.perf_counter()
        data, samplerate = sf.read(wav_path)
        sf.write(flac_path, data, samplerate, format="FLAC")
        result["encode_sec"] = time.perf_counter() - t0

        result["flac_bytes"]   = os.path.getsize(flac_path)
        result["duration_sec"] = len(data) / samplerate
        result["success"]      = True

        logger.debug(
            f"Encoded {os.path.basename(wav_path)} → FLAC "
            f"({wav_bytes // 1024} KB → {result['flac_bytes'] // 1024} KB) "
            f"in {result['encode_sec']:.2f} s"
        )

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Failed to encode {wav_path}: {e}")

    return result
