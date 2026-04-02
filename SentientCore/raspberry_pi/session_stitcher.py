# =============================================================================
# AquaEye-Sentient — session_stitcher.py
# =============================================================================
# Groups staged WAV files from all three HydroMoths into time-synchronised
# sessions, ready for FLAC compression and metadata tagging.
#
# WHY STITCHING IS NEEDED
# -----------------------
# Each HydroMoth records independently to its own SD card. After pulling,
# the staging folder contains files like:
#
#   HM_A__20250325_120000.WAV   (unit A, started at 12:00:00)
#   HM_B__20250325_120001.WAV   (unit B, started at 12:00:01 — 1 s drift)
#   HM_C__20250325_120000.WAV   (unit C, started at 12:00:00)
#   HM_A__20250325_121000.WAV   (unit A, next recording window)
#   ...
#
# Without stitching, there is no way to know that HM_A/120000, HM_B/120001,
# and HM_C/120000 are all recordings of the SAME 10-minute acoustic window
# from three different angles. Stitching groups them by timestamp proximity
# and assigns them a shared session_id so they can be processed together and
# linked in metadata for future bearing/TDOA analysis.
#
# STITCHING ALGORITHM
# -------------------
# 1. Parse the timestamp from every staged WAV filename.
# 2. Sort all files chronologically.
# 3. Sweep through: each file either joins the current open group (if its
#    timestamp is within STITCH_TOLERANCE_SEC of the group anchor) or starts
#    a new group.
# 4. Each group becomes a session. The session_id is the timestamp of the
#    earliest file in the group, formatted as YYYYMMDD_HHMMSS.
#
# PARTIAL SESSIONS
# ----------------
# If only 1 or 2 HydroMoths contributed to a session (e.g. one SD card was
# not mounted during the pull), the session is flagged complete=False.
# These are still returned and processed — the missing unit simply has no
# FLAC or metadata entry for that window.
#
# KEY FUNCTION
# ------------
#   get_unprocessed_sessions()
#     Returns a list of session dicts, sorted chronologically, excluding
#     any session whose files are all already in PROCESSED_LOG.
# =============================================================================

import os
import logging
from datetime import datetime

from config import HYDROMOTHS, STAGING_FOLDER, PROCESSED_LOG, STITCH_TOLERANCE_SEC
from hydromoth_puller import ID_SEP

logger = logging.getLogger(__name__)

# HydroMoth filename timestamp format: YYYYMMDD_HHMMSS.WAV
_TIMESTAMP_FMT = "%Y%m%d_%H%M%S"

# Build a lookup: hydromoth_id → config dict (for angle_deg, channel)
_HM_BY_ID = {hm["id"]: hm for hm in HYDROMOTHS}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_staged_filename(fname: str) -> tuple | None:
    """
    Parse a staged WAV filename into (hydromoth_id, timestamp, original_name).

    Expected format:  HM_A__20250325_120000.WAV
    Returns None if the filename does not match this format.
    """
    if ID_SEP not in fname:
        return None

    hm_id, original = fname.split(ID_SEP, 1)   # split on first __ only

    stem = os.path.splitext(original)[0]        # strip .WAV

    try:
        ts = datetime.strptime(stem, _TIMESTAMP_FMT)
    except ValueError:
        logger.debug(f"Could not parse timestamp from staged file: {fname}")
        return None

    return hm_id, ts, original


def _load_processed_set() -> set:
    """Return the set of already-processed staged WAV paths from PROCESSED_LOG."""
    if not os.path.exists(PROCESSED_LOG):
        return set()
    with open(PROCESSED_LOG, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


# ---------------------------------------------------------------------------
# Core stitching logic
# ---------------------------------------------------------------------------

def _stitch(file_records: list) -> list:
    """
    Group file_records into sessions by timestamp proximity.

    Parameters
    ----------
    file_records : list of dicts, each with keys:
        wav_path, hydromoth_id, angle_deg, channel, timestamp

    Returns
    -------
    List of session dicts (see get_unprocessed_sessions for schema).
    """
    if not file_records:
        return []

    # Sort by timestamp so we can sweep linearly
    sorted_records = sorted(file_records, key=lambda r: r["timestamp"])

    sessions = []
    current_group = [sorted_records[0]]
    current_ids   = {sorted_records[0]["hydromoth_id"]}
    anchor_ts     = sorted_records[0]["timestamp"]

    for record in sorted_records[1:]:
        # abs() not needed — sorted guarantees record["timestamp"] >= anchor_ts
        delta = (record["timestamp"] - anchor_ts).total_seconds()
        hm_id = record["hydromoth_id"]

        if delta <= STITCH_TOLERANCE_SEC and hm_id not in current_ids:
            # Within tolerance AND device not already in this session
            current_group.append(record)
            current_ids.add(hm_id)
        else:
            # Outside tolerance OR duplicate device (e.g. HydroMoth crash/restart
            # within the tolerance window) — close session, start a new one
            sessions.append(_make_session(current_group))
            current_group = [record]
            current_ids   = {hm_id}
            anchor_ts     = record["timestamp"]

    # Close the final group
    sessions.append(_make_session(current_group))

    return sessions


def _make_session(group: list) -> dict:
    """
    Build a session dict from a group of file records.

    session_id  : timestamp of the earliest file, formatted YYYYMMDD_HHMMSS
    files       : list of file dicts (one per HydroMoth that contributed)
    timestamp   : datetime of session anchor (earliest file)
    n_units     : how many HydroMoths contributed (1, 2, or 3)
    complete    : True only if all three HydroMoths contributed a file
    """
    anchor_ts  = min(r["timestamp"] for r in group)
    session_id = anchor_ts.strftime(_TIMESTAMP_FMT)

    files = [
        {
            "wav_path":     r["wav_path"],
            "hydromoth_id": r["hydromoth_id"],
            "angle_deg":    r["angle_deg"],
            "channel":      r["channel"],
        }
        for r in group
    ]

    n_expected = len(HYDROMOTHS)   # 3 for Config C

    return {
        "session_id": session_id,
        "timestamp":  anchor_ts,
        "files":      files,
        "n_units":    len(files),
        "complete":   len(files) == n_expected,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_unprocessed_sessions() -> list:
    """
    Scan STAGING_FOLDER, stitch files into sessions, and return only those
    sessions that have at least one file not yet in PROCESSED_LOG.

    Sessions are returned sorted chronologically (oldest first).

    Returns
    -------
    List of session dicts, each with:
        session_id  (str)      — e.g. "20250325_120000"
        timestamp   (datetime) — anchor datetime of the session
        files       (list)     — list of file dicts:
                                    wav_path, hydromoth_id, angle_deg, channel
        n_units     (int)      — number of HydroMoths that contributed (1–3)
        complete    (bool)     — True if all 3 units present

    Each session's files are sorted by channel index for consistent ordering.
    """
    if not os.path.isdir(STAGING_FOLDER):
        logger.warning(f"Staging folder does not exist: {STAGING_FOLDER}")
        return []

    processed = _load_processed_set()

    # Parse every staged WAV file
    file_records = []
    for fname in os.listdir(STAGING_FOLDER):
        if not fname.upper().endswith(".WAV"):
            continue

        wav_path = os.path.join(STAGING_FOLDER, fname)

        # Skip if already processed
        if wav_path in processed:
            continue

        parsed = _parse_staged_filename(fname)
        if parsed is None:
            logger.warning(f"Ignoring unrecognised file in staging: {fname}")
            continue

        hm_id, ts, _ = parsed

        hm_config = _HM_BY_ID.get(hm_id)
        if hm_config is None:
            logger.warning(f"Staging file {fname} has unknown HydroMoth ID '{hm_id}' — ignoring")
            continue

        file_records.append({
            "wav_path":     wav_path,
            "hydromoth_id": hm_id,
            "angle_deg":    hm_config["angle_deg"],
            "channel":      hm_config["channel"],
            "timestamp":    ts,
        })

    if not file_records:
        logger.debug("No unprocessed WAV files found in staging")
        return []

    sessions = _stitch(file_records)

    # Sort files within each session by channel index
    for s in sessions:
        s["files"].sort(key=lambda f: f["channel"])

    # Log a warning for any incomplete sessions
    for s in sessions:
        if not s["complete"]:
            ids = [f["hydromoth_id"] for f in s["files"]]
            logger.warning(
                f"Session {s['session_id']} is incomplete — "
                f"only {s['n_units']}/{len(HYDROMOTHS)} units present: {ids}"
            )

    logger.info(
        f"Stitcher found {len(sessions)} session(s) "
        f"({sum(1 for s in sessions if s['complete'])} complete, "
        f"{sum(1 for s in sessions if not s['complete'])} partial)"
    )

    return sessions
