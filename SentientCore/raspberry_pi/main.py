#!/usr/bin/env python3
# =============================================================================
# AquaEye-Sentient — main.py
# =============================================================================
# Top-level orchestration script. Runs the full processing pipeline on the
# Raspberry Pi 5 buoy system.
#
# PIPELINE PER CYCLE
# ------------------
#   1. Pull  — copy new WAV files from each HydroMoth SD card to staging,
#              delete originals from SD after verified copy
#   2. Stitch — group staged files by timestamp into sessions
#   3. Encode — convert each session's WAVs to FLAC
#   4. Tag   — write _meta.json sidecar for each FLAC
#   5. Upload — send completed FLACs + sidecars to Google Drive (if Wi-Fi)
#
# TWO OPERATING MODES
# -------------------
# Loop mode (default — for bench testing and development):
#   python3 main.py
#   Runs cycles continuously, sleeping POLL_INTERVAL_SEC between them.
#   Does NOT halt the Pi. Use this mode when you want the system to keep
#   running without power management.
#
# Once mode (for deployment with RTC power management):
#   python3 main.py --once
#   Runs exactly one cycle, then halts the Pi using rtcwake so the system
#   sleeps until the next scheduled wake. RTC halt mode:
#   ~70 s active, ~530 s halted per 10-minute cycle.
#   The Pi must be configured for RTC wake (sudo rtcwake) for this to work.
#
# STARTING ON BOOT
# ----------------
# For deployment, configure this as a systemd service or add to /etc/rc.local:
#   python3 /home/pi/aquaeye/main.py --once
# The RTC will wake the Pi every POLL_INTERVAL_SEC seconds automatically.
#
# LOGGING
# -------
# Logs are written to LOG_FILE (config.py) and also printed to the terminal.
# Set LOG_LEVEL to DEBUG for detailed per-file output.
# =============================================================================

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

import audio_processor
import hydromoth_puller
import metadata_writer
import serial_reader
import session_stitcher
from config import (
    BASE_DIR, STAGING_FOLDER, FLAC_FOLDER, UPLOADED_FOLDER,
    PROCESSED_LOG, SENSOR_LOG, SAMPLE_RATE, POLL_INTERVAL_SEC,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

LOG_FILE  = os.path.join(BASE_DIR, "aquaeye.log")
LOG_LEVEL = logging.INFO


def _setup_logging():
    os.makedirs(BASE_DIR, exist_ok=True)
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s: %(message)s"
    logging.basicConfig(
        level=LOG_LEVEL,
        format=fmt,
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


logger = logging.getLogger("main")


# ---------------------------------------------------------------------------
# Directory initialisation
# ---------------------------------------------------------------------------

def _init_dirs():
    """Create all working directories if they don't exist."""
    for d in [BASE_DIR, STAGING_FOLDER, FLAC_FOLDER, UPLOADED_FOLDER]:
        os.makedirs(d, exist_ok=True)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

import cloud_uploader

def _upload_pending():
    """Upload completed FLACs and _meta.json sidecars to Google Drive."""
    result = cloud_uploader.upload_pending()
    logger.info(
        f"Upload — uploaded: {result['uploaded']}, "
        f"skipped: {result['skipped']}, failed: {result['failed']}"
    )


# ---------------------------------------------------------------------------
# RTC halt (once mode)
# ---------------------------------------------------------------------------

def _rtc_halt(interval_sec: int):
    """
    Schedule a wake-up in interval_sec seconds using the Pi 5's built-in RTC,
    then halt the system.

    Uses: sudo rtcwake -m halt -s <seconds>

    RTC halt mode: Pi halts after each cycle and the RTC wakes it for the
    next one. The halt state draws ~20 mA vs ~600-900 mA active.

    Requires: the script must be run with sudo, or the user must have
    passwordless sudo for rtcwake configured in /etc/sudoers.
    """
    logger.info(f"Scheduling RTC wake in {interval_sec} s, then halting ...")
    try:
        subprocess.run(
            ["sudo", "rtcwake", "-m", "halt", "-s", str(interval_sec)],
            check=True,
        )
        # If rtcwake returns (it shouldn't on halt), log and exit cleanly
        logger.info("rtcwake returned — system did not halt as expected")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        logger.error(f"rtcwake failed: {e}. System will NOT halt.")
    except FileNotFoundError:
        logger.error("rtcwake not found. Is this running on a Raspberry Pi?")


# ---------------------------------------------------------------------------
# One processing cycle
# ---------------------------------------------------------------------------

def run_cycle(cycle_num: int) -> dict:
    """
    Execute one full pipeline cycle.

    Returns a summary dict with counts and any error messages.
    A cycle that encounters errors logs them and continues — it does not
    raise exceptions, so a single bad file cannot crash the whole system.
    """
    summary = {
        "cycle":         cycle_num,
        "pulled":        0,
        "sessions":      0,
        "encoded":       0,
        "encode_errors": 0,
        "uploaded":      0,
        "errors":        [],
    }

    cycle_start = time.perf_counter()
    logger.info(f"--- Cycle {cycle_num} started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    # ------------------------------------------------------------------
    # Step 1: Pull from SD cards
    # ------------------------------------------------------------------
    try:
        pull_result = hydromoth_puller.pull_all()
        summary["pulled"] = pull_result["pulled"]

        if pull_result["failed"] > 0:
            for err in pull_result["errors"]:
                logger.warning(f"Pull error: {err}")
                summary["errors"].append(err)

        logger.info(
            f"Pull — pulled: {pull_result['pulled']}, "
            f"skipped: {pull_result['skipped']}, "
            f"failed: {pull_result['failed']}"
        )
    except Exception as e:
        msg = f"Pull step failed unexpectedly: {e}"
        logger.error(msg)
        summary["errors"].append(msg)
        # Cannot continue without files — return early
        return summary

    # ------------------------------------------------------------------
    # Step 2: Stitch into sessions
    # ------------------------------------------------------------------
    try:
        sessions = session_stitcher.get_unprocessed_sessions()
        summary["sessions"] = len(sessions)
        logger.info(f"Stitch — {len(sessions)} session(s) to process")
    except Exception as e:
        msg = f"Stitch step failed: {e}"
        logger.error(msg)
        summary["errors"].append(msg)
        return summary

    if not sessions:
        logger.info("No new sessions — nothing to process this cycle")
        return summary

    # ------------------------------------------------------------------
    # Step 3 + 4: Encode + Metadata (per session, per file)
    # ------------------------------------------------------------------
    sensor_data = serial_reader.get_latest_reading()

    for session in sessions:
        session_id = session["session_id"]

        if not session["complete"]:
            logger.warning(
                f"Session {session_id} is partial "
                f"({session['n_units']}/{len(session['files'])} units) — processing anyway"
            )

        for file_entry in session["files"]:
            wav_path     = file_entry["wav_path"]
            hydromoth_id = file_entry["hydromoth_id"]
            wav_name     = os.path.basename(wav_path)

            # Build output FLAC path
            stem      = os.path.splitext(wav_name)[0]
            flac_path = os.path.join(FLAC_FOLDER, f"{stem}.flac")

            # Encode
            enc = audio_processor.convert_wav_to_flac(wav_path, flac_path)

            if not enc["success"]:
                msg = f"Encode failed for {wav_name}: {enc['error']}"
                logger.error(msg)
                summary["errors"].append(msg)
                summary["encode_errors"] += 1
                continue

            logger.info(
                f"Encoded {wav_name} → {os.path.basename(flac_path)} "
                f"({enc['wav_bytes'] // 1024} KB → {enc['flac_bytes'] // 1024} KB, "
                f"{enc['encode_sec']:.1f} s)"
            )

            # Metadata
            try:
                metadata_writer.write_metadata(
                    flac_path    = flac_path,
                    hydromoth_id = hydromoth_id,
                    angle_deg    = file_entry["angle_deg"],
                    channel      = file_entry["channel"],
                    sample_rate  = SAMPLE_RATE,
                    session_id   = session_id,
                    sensor       = sensor_data,
                )
            except Exception as e:
                logger.warning(f"Metadata write failed for {wav_name}: {e}")
                # Not fatal — FLAC is still good

            # Mark as processed
            try:
                with open(PROCESSED_LOG, "a", encoding="utf-8") as f:
                    f.write(wav_path + "\n")
            except OSError as e:
                logger.warning(f"Could not update processed log: {e}")

            summary["encoded"] += 1

    # ------------------------------------------------------------------
    # Step 5: Upload (stub)
    # ------------------------------------------------------------------
    try:
        _upload_pending()
    except Exception as e:
        logger.warning(f"Upload step error: {e}")

    elapsed = time.perf_counter() - cycle_start
    logger.info(
        f"--- Cycle {cycle_num} complete in {elapsed:.1f} s — "
        f"encoded: {summary['encoded']}, errors: {summary['encode_errors']} ---"
    )

    return summary


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="AquaEye-Sentient — buoy processing pipeline"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Run one cycle then halt via RTC. "
            "Use for deployment with RTC power management. "
            "Without this flag, runs continuously (loop mode for bench/dev)."
        ),
    )
    args = parser.parse_args()

    _setup_logging()
    _init_dirs()

    logger.info("=" * 60)
    logger.info("AquaEye-Sentient starting up")
    logger.info(f"Mode: {'once (RTC halt after cycle)' if args.once else 'loop'}")
    logger.info("=" * 60)

    # Start Arduino serial reader
    logger.info("Starting Arduino serial reader ...")
    serial_reader.start()
    time.sleep(2)   # allow first reading to arrive

    # ------------------------------------------------------------------
    # Once mode — one cycle then RTC halt
    # ------------------------------------------------------------------
    if args.once:
        run_cycle(cycle_num=1)
        _rtc_halt(POLL_INTERVAL_SEC)
        return

    # ------------------------------------------------------------------
    # Loop mode — continuous cycles with sleep between
    # ------------------------------------------------------------------
    cycle_num = 0
    logger.info(f"Loop mode — cycling every {POLL_INTERVAL_SEC} s. Press Ctrl+C to stop.")

    try:
        while True:
            cycle_num += 1
            run_cycle(cycle_num)

            logger.info(f"Sleeping {POLL_INTERVAL_SEC} s until next cycle ...")
            time.sleep(POLL_INTERVAL_SEC)

    except KeyboardInterrupt:
        logger.info("Interrupted by user — shutting down cleanly")
        sys.exit(0)


if __name__ == "__main__":
    main()
