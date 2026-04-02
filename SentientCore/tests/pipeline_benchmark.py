#!/usr/bin/env python3
# =============================================================================
# AquaEye-Sentient — pipeline_benchmark.py
# =============================================================================
# Bench test harness for the Pi 5 power budget verification.
#
# PURPOSE
# -------
# Runs the full production pipeline (stage → stitch → compress → metadata)
# repeatedly and measures how long it takes. An external inline power meter
# (e.g. UM25C) connected to the Pi's 5V supply measures current draw during
# the run. Together these validate three key power budget assumptions:
#
#   A1  Pi 5 active current during FLAC compression   (HIGH risk — external meter)
#   A3  FLAC compression time per file                (8 s assumed)
#   A4  Active window overhead                        (20 s assumed)
#
# HOW IT SIMULATES THE REAL PIPELINE
# -----------------------------------
# The real pipeline is:  pull SD card → stitch → compress → metadata
# On the bench (no SD cards), we simulate the pull step by copying your
# test WAV files into the staging folder with proper HydroMoth naming.
# The stitch → compress → metadata steps then run exactly as they would
# on deployment.
#
# INPUT FILE NAMING
# -----------------
# WAV files in --wav_dir must be named in HydroMoth format:
#   YYYYMMDD_HHMMSS.WAV   e.g.  20260401_120000.WAV
#
# The benchmark assigns them to HydroMoths in round-robin order:
#   File 1 → HM_A__20260401_120000.WAV
#   File 2 → HM_B__20260401_120000.WAV   (same timestamp = same session)
#   File 3 → HM_C__20260401_120000.WAV
#   File 4 → HM_A__20260401_121000.WAV   (different timestamp = next session)
#   ...
#
# So for a 3-file bench test you get 1 complete session (all 3 units).
# For a 6-file bench test you get 2 sessions. Aim for 6 files.
#
# HOW TO USE
# ----------
# 1. Record some audio with your HydroMoths, copy the WAV files to the Pi:
#      ~/aquaeye/bench_wav/20260401_120000.WAV
#      ~/aquaeye/bench_wav/20260401_121000.WAV   (etc.)
#    Or generate synthetic WAV files with:
#      python3 pipeline_benchmark.py --generate_wav --wav_dir ~/aquaeye/bench_wav
#
# 2. Run the benchmark:
#      python3 pipeline_benchmark.py --wav_dir ~/aquaeye/bench_wav --cycles 10
#
#    With Arduino connected:
#      python3 pipeline_benchmark.py --wav_dir ~/aquaeye/bench_wav --cycles 10
#
#    Without Arduino:
#      python3 pipeline_benchmark.py --wav_dir ~/aquaeye/bench_wav --cycles 10 --no_serial
#
# 3. Watch the inline power meter during the run.
#    After the run, note the sustained current during encode phases → A1.
# =============================================================================

import argparse
import logging
import os
import shutil
import struct
import sys
import time
import wave

sys.path.insert(0, os.path.dirname(__file__))

import audio_processor
import metadata_writer
import serial_reader
import session_stitcher
from config import (
    HYDROMOTHS, SAMPLE_RATE, STAGING_FOLDER, FLAC_FOLDER,
    PROCESSED_LOG, SERIAL_PORT, SERIAL_BAUD,
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("benchmark")


# ---------------------------------------------------------------------------
# Synthetic WAV generator (for bench testing without real HydroMoth files)
# ---------------------------------------------------------------------------

def generate_test_wavs(wav_dir: str, n_files: int = 6, duration_sec: int = 60):
    """
    Generate n_files synthetic WAV files in wav_dir.
    Each file is `duration_sec` seconds of silence at SAMPLE_RATE / 16-bit mono.
    Named in HydroMoth format: 20260401_120000.WAV, 20260401_121000.WAV, etc.
    """
    os.makedirs(wav_dir, exist_ok=True)
    base_hour = 12
    base_min  = 0

    for i in range(n_files):
        minutes    = base_min + i * 10
        hours      = base_hour + minutes // 60
        mins       = minutes % 60
        fname      = f"20260401_{hours:02d}{mins:02d}00.WAV"
        fpath      = os.path.join(wav_dir, fname)

        if os.path.exists(fpath):
            print(f"  {fname} already exists — skipping")
            continue

        n_frames   = SAMPLE_RATE * duration_sec
        with wave.open(fpath, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)               # 16-bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"\x00\x00" * n_frames)  # silence

        size_mb = os.path.getsize(fpath) / (1024 * 1024)
        print(f"  Generated {fname}  ({size_mb:.1f} MB, {duration_sec}s @ {SAMPLE_RATE} Hz)")

    print()


# ---------------------------------------------------------------------------
# Staging simulation (replaces the real puller for bench testing)
# ---------------------------------------------------------------------------

def stage_test_files(wav_dir: str, n_per_cycle: int) -> list:
    """
    Copy WAV files from wav_dir into STAGING_FOLDER with HydroMoth prefixes,
    simulating what hydromoth_puller.pull_all() does from SD cards.

    Files are grouped into sessions of len(HYDROMOTHS) before assigning names.
    All files in the same session get the same timestamp so the stitcher
    groups them correctly (within STITCH_TOLERANCE_SEC = 5 s).

    Example with 6 files and 3 HydroMoths:
      wav_files[0] → HM_A__20260401_120000.WAV  ┐ session 1
      wav_files[1] → HM_B__20260401_120000.WAV  │
      wav_files[2] → HM_C__20260401_120000.WAV  ┘
      wav_files[3] → HM_A__20260401_121000.WAV  ┐ session 2
      wav_files[4] → HM_B__20260401_121000.WAV  │
      wav_files[5] → HM_C__20260401_121000.WAV  ┘

    Returns list of staged file paths.
    """
    os.makedirs(STAGING_FOLDER, exist_ok=True)

    wav_files = sorted(
        f for f in os.listdir(wav_dir) if f.upper().endswith(".WAV")
    )[:n_per_cycle]

    if not wav_files:
        print(f"ERROR: no .WAV files found in {wav_dir}")
        sys.exit(1)

    n_hm   = len(HYDROMOTHS)
    staged = []

    # Base session timestamps: session 0 = 120000, session 1 = 121000, etc.
    base_hour = 12

    for i, fname in enumerate(wav_files):
        session_num = i // n_hm          # which session this file belongs to
        hm_index    = i % n_hm           # which HydroMoth within that session
        hm_id       = HYDROMOTHS[hm_index]["id"]

        # All files in the same session share the same timestamp
        total_mins  = session_num * 10
        hours       = base_hour + total_mins // 60
        mins        = total_mins % 60
        ts_str      = f"20260401_{hours:02d}{mins:02d}00"

        staged_name = f"{hm_id}__{ts_str}.WAV"
        src         = os.path.join(wav_dir, fname)
        dst         = os.path.join(STAGING_FOLDER, staged_name)

        if not os.path.exists(dst):
            shutil.copy2(src, dst)
        staged.append(dst)

    return staged


def clear_staging_and_log():
    """Remove all staged WAV/FLAC files and reset PROCESSED_LOG between cycles."""
    # Clear staging WAVs
    if os.path.isdir(STAGING_FOLDER):
        for f in os.listdir(STAGING_FOLDER):
            if f.upper().endswith(".WAV"):
                os.remove(os.path.join(STAGING_FOLDER, f))

    # Clear output FLACs and meta JSONs from previous cycle
    if os.path.isdir(FLAC_FOLDER):
        for f in os.listdir(FLAC_FOLDER):
            if f.endswith(".flac") or f.endswith("_meta.json"):
                os.remove(os.path.join(FLAC_FOLDER, f))

    # Reset processed log so stitcher sees files as new next cycle
    if os.path.exists(PROCESSED_LOG):
        os.remove(PROCESSED_LOG)


# ---------------------------------------------------------------------------
# Table formatter
# ---------------------------------------------------------------------------

def format_table(rows: list, headers: list) -> str:
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    def fmt_row(r):
        return "  ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(r))

    sep = "  ".join("-" * w for w in col_widths)
    return "\n".join([fmt_row(headers), sep] + [fmt_row(r) for r in rows])


# ---------------------------------------------------------------------------
# Stats helper
# ---------------------------------------------------------------------------

def stats(values: list) -> tuple:
    n    = len(values)
    mean = sum(values) / n
    sd   = (sum((v - mean) ** 2 for v in values) / n) ** 0.5
    return mean, sd, min(values), max(values)


# ---------------------------------------------------------------------------
# Single benchmark cycle
# ---------------------------------------------------------------------------

def run_cycle(
    wav_dir:    str,
    n_files:    int,
    use_serial: bool,
    cycle_num:  int,
) -> dict:
    """
    Run one full pipeline cycle and return a timing breakdown dict.

    Steps:
      t_stage    — copy test WAVs into staging with HydroMoth prefixes
      t_stitch   — group staged files into sessions
      t_encode   — FLAC compression for all files across all sessions
      t_metadata — JSON sidecar writes
      t_total    — full cycle wall-clock
    """
    os.makedirs(FLAC_FOLDER, exist_ok=True)
    result = {
        "cycle": cycle_num, "n_sessions": 0, "n_files": 0, "n_success": 0,
        "t_stage_s": 0, "t_stitch_s": 0, "t_encode_s": 0,
        "t_metadata_s": 0, "t_total_s": 0, "avg_per_file_s": 0,
    }

    cycle_start = time.perf_counter()

    # -- Serial snapshot ------------------------------------------------------
    sensor_data = serial_reader.get_latest_reading() if use_serial else None

    # -- Stage (simulate pull) ------------------------------------------------
    t0 = time.perf_counter()
    stage_test_files(wav_dir, n_files)
    result["t_stage_s"] = round(time.perf_counter() - t0, 2)

    # -- Stitch ---------------------------------------------------------------
    t0 = time.perf_counter()
    sessions = session_stitcher.get_unprocessed_sessions()
    result["t_stitch_s"]  = round(time.perf_counter() - t0, 2)
    result["n_sessions"]  = len(sessions)

    # -- Encode + Metadata (per session, per file) ----------------------------
    encode_times = []
    t_encode_total   = 0.0
    t_metadata_total = 0.0

    for session in sessions:
        for file_entry in session["files"]:
            wav_path  = file_entry["wav_path"]
            stem      = os.path.splitext(os.path.basename(wav_path))[0]
            flac_path = os.path.join(FLAC_FOLDER, f"{stem}_c{cycle_num:03d}.flac")

            # Encode
            t0     = time.perf_counter()
            enc    = audio_processor.convert_wav_to_flac(wav_path, flac_path)
            t_encode_total += time.perf_counter() - t0

            if enc["success"]:
                encode_times.append(enc["encode_sec"])
                result["n_success"] += 1

                # Metadata
                t0 = time.perf_counter()
                metadata_writer.write_metadata(
                    flac_path    = flac_path,
                    hydromoth_id = file_entry["hydromoth_id"],
                    angle_deg    = file_entry["angle_deg"],
                    channel      = file_entry["channel"],
                    sample_rate  = SAMPLE_RATE,
                    session_id   = session["session_id"],
                    sensor       = sensor_data,
                )
                t_metadata_total += time.perf_counter() - t0

            result["n_files"] += 1

            # Mark processed so stitcher skips it if cycle is re-run
            with open(PROCESSED_LOG, "a") as f:
                f.write(wav_path + "\n")

    result["t_encode_s"]   = round(t_encode_total,   2)
    result["t_metadata_s"] = round(t_metadata_total, 2)
    result["t_total_s"]    = round(time.perf_counter() - cycle_start, 2)
    result["avg_per_file_s"] = round(
        sum(encode_times) / len(encode_times) if encode_times else 0.0, 2
    )

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="AquaEye-Sentient — Pi 5 pipeline benchmark"
    )
    parser.add_argument(
        "--wav_dir", required=True,
        help="Folder containing HydroMoth WAV files (YYYYMMDD_HHMMSS.WAV format)",
    )
    parser.add_argument(
        "--files", type=int, default=6,
        help="WAV files per cycle (default 6 → 2 complete sessions of 3 units each)",
    )
    parser.add_argument(
        "--cycles", type=int, default=10,
        help="Number of cycles to run (default 10)",
    )
    parser.add_argument(
        "--no_serial", action="store_true",
        help="Skip Arduino serial reader (use when Arduino not connected)",
    )
    parser.add_argument(
        "--generate_wav", action="store_true",
        help="Generate synthetic WAV files in --wav_dir and exit",
    )
    args = parser.parse_args()

    # ---- Generate synthetic WAVs and exit -----------------------------------
    if args.generate_wav:
        print(f"Generating {args.files} synthetic WAV file(s) in {args.wav_dir} ...")
        generate_test_wavs(args.wav_dir, n_files=args.files, duration_sec=60)
        print("Done. Run without --generate_wav to start the benchmark.")
        return

    # ---- Validate -----------------------------------------------------------
    if not os.path.isdir(args.wav_dir):
        print(f"ERROR: {args.wav_dir} does not exist")
        sys.exit(1)

    wav_count = len([f for f in os.listdir(args.wav_dir) if f.upper().endswith(".WAV")])
    if wav_count == 0:
        print(f"ERROR: no WAV files in {args.wav_dir}")
        print("  Tip: run with --generate_wav to create synthetic test files")
        sys.exit(1)

    actual_files = min(args.files, wav_count)
    if actual_files < args.files:
        print(f"WARNING: only {wav_count} WAV file(s) available, using {actual_files} per cycle")

    # ---- Start serial reader ------------------------------------------------
    use_serial = not args.no_serial
    if use_serial:
        print(f"Starting Arduino serial reader on {SERIAL_PORT} @ {SERIAL_BAUD} baud ...")
        serial_reader.start()
        time.sleep(2)
    else:
        print("Serial reader disabled (--no_serial). Sensor fields will be null.")

    # ---- Banner -------------------------------------------------------------
    n_hm      = len(HYDROMOTHS)
    sessions_per_cycle = actual_files // n_hm
    print()
    print("=" * 62)
    print("  AquaEye-Sentient — Pi 5 Processing Pipeline Benchmark")
    print("=" * 62)
    print(f"  WAV source       : {args.wav_dir}")
    print(f"  Files per cycle  : {actual_files}  ({n_hm} HydroMoths × {sessions_per_cycle} session(s))")
    print(f"  Cycles           : {args.cycles}")
    print(f"  Staging folder   : {STAGING_FOLDER}")
    print(f"  FLAC output      : {FLAC_FOLDER}")
    print()
    print("  Power budget assumptions being tested:")
    print("    A1 — Pi 5 active current (measured on your inline meter)")
    print("    A3 — FLAC encode time per file (assumed 8 s)")
    print("    A4 — Active window overhead   (assumed 20 s)")
    print()
    print("  >>> Start recording on your inline power meter NOW <<<")
    print()
    input("  Press ENTER when ready ...")
    print()

    # ---- Warm-up ------------------------------------------------------------
    print("  Warm-up cycle (excluded from results) ...", end="", flush=True)
    clear_staging_and_log()
    run_cycle(args.wav_dir, actual_files, use_serial, cycle_num=0)
    print(" done")
    print()

    # ---- Benchmark cycles ---------------------------------------------------
    results = []
    for i in range(1, args.cycles + 1):
        clear_staging_and_log()
        print(f"  Cycle {i:2d}/{args.cycles} ...", end="", flush=True)
        r = run_cycle(args.wav_dir, actual_files, use_serial, cycle_num=i)
        results.append(r)
        print(
            f"  sessions={r['n_sessions']}  "
            f"total={r['t_total_s']:.1f}s  "
            f"encode={r['t_encode_s']:.1f}s  "
            f"stitch={r['t_stitch_s']:.2f}s  "
            f"meta={r['t_metadata_s']:.2f}s"
        )

    # ---- Per-cycle table ----------------------------------------------------
    print()
    print("=" * 62)
    print("  RESULTS — Per-cycle timing")
    print("=" * 62)
    headers = ["Cycle", "Sessions", "Files", "Encode(s)", "Stitch(s)", "Meta(s)", "Stage(s)", "Total(s)", "Avg/file(s)"]
    rows = [[
        r["cycle"], r["n_sessions"], r["n_files"],
        r["t_encode_s"], r["t_stitch_s"], r["t_metadata_s"],
        r["t_stage_s"], r["t_total_s"], r["avg_per_file_s"],
    ] for r in results]
    print(format_table(rows, headers))

    # ---- Aggregate ----------------------------------------------------------
    print()
    print("=" * 62)
    print(f"  RESULTS — Aggregate  (n={args.cycles})")
    print("=" * 62)
    agg_headers = ["Metric", "Mean(s)", "SD(s)", "Min(s)", "Max(s)"]
    agg_rows = []
    for label, key in [
        ("Total active window",    "t_total_s"),
        ("FLAC encode (all files)", "t_encode_s"),
        ("Avg per-file encode",    "avg_per_file_s"),
        ("Stitch overhead",        "t_stitch_s"),
        ("Metadata write",         "t_metadata_s"),
    ]:
        mean, sd, mn, mx = stats([r[key] for r in results])
        agg_rows.append([label, f"{mean:.2f}", f"{sd:.2f}", f"{mn:.2f}", f"{mx:.2f}"])
    print(format_table(agg_rows, agg_headers))

    # ---- Power budget comparison ---------------------------------------------
    mean_total,    _, _, _ = stats([r["t_total_s"]    for r in results])
    mean_per_file, _, _, _ = stats([r["avg_per_file_s"] for r in results])

    assumed_total    = 70
    assumed_per_file =  8

    print()
    print("=" * 62)
    print("  POWER BUDGET ASSUMPTION COMPARISON")
    print("=" * 62)
    comp_headers = ["Assumption", "Budgeted", "Measured", "Delta", "Status"]
    comp_rows = [
        [
            "A3: encode time/file",
            f"{assumed_per_file} s",
            f"{mean_per_file:.2f} s",
            f"{mean_per_file - assumed_per_file:+.2f} s",
            "OK" if mean_per_file <= assumed_per_file * 1.25 else "REVISE",
        ],
        [
            "A3+A4: total active window",
            f"{assumed_total} s",
            f"{mean_total:.2f} s",
            f"{mean_total - assumed_total:+.2f} s",
            "OK" if mean_total <= assumed_total * 1.25 else "REVISE",
        ],
    ]
    print(format_table(comp_rows, comp_headers))

    print()
    print("  NOTE: A1 (Pi 5 active current) is NOT captured by this script.")
    print("  Record the sustained mA reading from your inline meter during")
    print("  the encode phases and log it separately as Assumption A1.")
    print()


if __name__ == "__main__":
    main()
