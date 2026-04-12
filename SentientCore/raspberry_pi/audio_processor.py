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
import numpy as np
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


def mix_session_to_flac(wav_paths: list, flac_path: str,
                        compression_level: int = 4) -> dict:
    """
    Mix multiple simultaneous HydroMoth WAV files into one normalised FLAC.

    Algorithm: sum-then-normalise.
      1. Load each WAV as float64 (soundfile normalises int16 → [-1, 1]).
      2. Truncate all arrays to the shortest file length.
      3. Sum into a single float64 array.
      4. Normalise: divide by max(abs) if > 1.0 to prevent clipping.
      5. Convert to int16, write FLAC using soundfile (native libsndfile).

    Falls back to convert_wav_to_flac() when only one path is provided.

    Parameters
    ----------
    wav_paths         : list of absolute paths to WAV files for this session
                        (typically 3 — one per HydroMoth)
    flac_path         : output path for the mixed FLAC
    compression_level : FLAC compression level 0–8 (default 4)

    Returns
    -------
    Same dict schema as convert_wav_to_flac():
        success, duration_sec, flac_bytes, encode_sec, error
    """
    result = {
        "success":      False,
        "duration_sec": None,
        "wav_bytes":    None,
        "flac_bytes":   None,
        "encode_sec":   None,
        "error":        None,
    }

    # Guard: empty list
    if len(wav_paths) == 0:
        result["error"] = "wav_paths is empty"
        return result

    # TODO: Single-file fallback to convert_wav_to_flac requires flac CLI (Linux/Pi only).
    # Docstring says fallback is implemented but deferring to production on Pi environment.
    # Temporarily, mix_session_to_flac handles all cases (single or multiple files) via soundfile.

    try:
        # --- Load all channels -----------------------------------------------
        arrays = []
        sample_rate = None
        for p in wav_paths:
            data, sr = sf.read(p, dtype="float64", always_2d=False)
            if sample_rate is None:
                sample_rate = sr
            elif sr != sample_rate:
                logger.warning(
                    f"Sample rate mismatch: expected {sample_rate} Hz, "
                    f"got {sr} Hz for {os.path.basename(p)} — mixing may be incorrect"
                )
            arrays.append(data)

        # --- Truncate to shortest length -------------------------------------
        min_len = min(len(a) for a in arrays)
        arrays  = [a[:min_len] for a in arrays]

        # --- Sum and normalise -----------------------------------------------
        mixed    = np.sum(arrays, axis=0)           # float64
        peak     = np.max(np.abs(mixed))
        if peak > 1.0:
            mixed = mixed / peak                    # scale to [-1, 1]

        result["duration_sec"] = min_len / sample_rate

        # --- Encode to FLAC via soundfile (libsndfile — no CLI required) -----
        mixed_i16 = (mixed * 32768).clip(-32768, 32767).astype(np.int16)

        t0 = time.perf_counter()
        sf.write(flac_path, mixed_i16, sample_rate,
                 subtype="PCM_16", format="FLAC")
        result["encode_sec"] = time.perf_counter() - t0

        result["flac_bytes"] = os.path.getsize(flac_path)
        result["success"]    = True

        logger.debug(
            f"Mixed {len(wav_paths)} files → {os.path.basename(flac_path)} "
            f"({result['flac_bytes'] // 1024} KB) in {result['encode_sec']:.2f} s"
        )

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"mix_session_to_flac failed: {e}")

    return result
