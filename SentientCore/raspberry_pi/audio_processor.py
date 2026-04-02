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
import subprocess
import time
import logging
import soundfile as sf  # used only for duration metadata — does not load audio data

logger = logging.getLogger(__name__)


def convert_wav_to_flac(wav_path: str, flac_path: str, compression_level: int = 4) -> dict:
    """
    Convert a WAV file to FLAC (lossless) using the native flac CLI binary.

    Replaces the previous soundfile-based approach, which decoded the entire
    WAV into a float64 NumPy array in RAM before re-encoding. The native CLI
    streams disk-to-disk without loading audio data into Python memory, which
    is meaningfully faster and lower-power on the Pi 5.

    Requires: sudo apt install flac

    Parameters
    ----------
    wav_path          : path to the source .WAV file (from HydroMoth SD card)
    flac_path         : path where the output .FLAC should be written
                        (parent directory must exist)
    compression_level : FLAC compression level 0–8 (default 4).
                        Level 4 vs default 5 cuts CPU time with ~1–2% larger files.

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
        result["wav_bytes"] = os.path.getsize(wav_path)

        # Read duration from WAV header only — no audio data loaded into RAM
        info = sf.info(wav_path)
        result["duration_sec"] = info.frames / info.samplerate

        # Native FLAC CLI: -f = force overwrite, --silent = suppress stdout
        cmd = [
            "flac",
            f"-{compression_level}",
            "-f",
            "--silent",
            wav_path,
            "-o", flac_path,
        ]

        t0 = time.perf_counter()
        subprocess.run(cmd, check=True)
        result["encode_sec"] = time.perf_counter() - t0

        result["flac_bytes"] = os.path.getsize(flac_path)
        result["success"]    = True

        logger.debug(
            f"Encoded {os.path.basename(wav_path)} → FLAC "
            f"(Level {compression_level}, "
            f"{result['wav_bytes'] // 1024} KB → {result['flac_bytes'] // 1024} KB) "
            f"in {result['encode_sec']:.2f} s"
        )

    except subprocess.CalledProcessError as e:
        result["error"] = f"flac CLI failed: {e}"
        logger.error(result["error"])
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Failed to encode {wav_path}: {e}")

    return result
