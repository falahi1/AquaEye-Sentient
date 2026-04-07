# =============================================================================
# AquaEye-Sentient — metadata_writer.py
# =============================================================================
# Writes a _meta.json sidecar file alongside each compressed FLAC.
#
# The sidecar captures everything known at the moment of compression:
# which HydroMoth recorded the file, the GPS fix, water quality readings,
# and the buoy heading (null until an IMU is fitted to the Arduino).
#
# Design decisions:
#   - One JSON file per FLAC, named <flac_stem>_meta.json
#   - Missing sensor fields are written as null (not omitted) so the schema
#     is consistent for every file — easier to parse in post-processing
#   - No dependency on Arduino being connected: if serial_reader has not yet
#     received a reading, all sensor fields are null
# =============================================================================

import json
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def write_metadata(
    flac_path:    str,
    hydromoth_id: str,
    angle_deg:    int,
    channel:      int,
    sample_rate:  int,
    session_id:   str  = None,
    sensor:       dict | None = None,
) -> str:
    """
    Write a _meta.json sidecar alongside flac_path.

    Parameters
    ----------
    flac_path    : absolute path to the .flac file just written
    hydromoth_id : e.g. "HM_A"
    angle_deg    : physical mounting angle on the buoy (degrees)
    channel      : channel index (0, 1, 2)
    sample_rate  : Hz — as configured on the HydroMoth device
    session_id   : shared ID linking all files from the same recording window
                   across all three HydroMoths (e.g. "20250325_120000").
                   Set by session_stitcher. None during bench tests.
    sensor       : dict from serial_reader.get_latest_reading(), or None

    Returns
    -------
    Path to the written _meta.json file.
    """
    s = sensor or {}

    meta = {
        "schema_version": "1.0",
        "written_utc":    datetime.now(timezone.utc).isoformat(),
        "session_id":     session_id,
        "audio": {
            "flac_file":    os.path.basename(flac_path),
            "hydromoth_id": hydromoth_id,
            "channel":      channel,
            "angle_deg":    angle_deg,
            "sample_rate":  sample_rate,
        },
        "gps": {
            "lat":      s.get("gps_lat"),
            "lon":      s.get("gps_lon"),
            "alt_m":    s.get("gps_alt_m"),
            "date":     s.get("gps_date"),
            "time_utc": s.get("gps_time_utc"),
        },
        "water_quality": {
            "tds_ppm":       s.get("tds_ppm"),
            "tds_voltage":   s.get("tds_voltage"),
            "turbidity_v":   s.get("turbidity_v"),
            "temp_c":        s.get("temp_c"),
        },
        "orientation": {
            "heading_deg": s.get("heading_deg"),   # null until IMU fitted
        },
    }

    stem      = os.path.splitext(flac_path)[0]
    meta_path = stem + "_meta.json"
    temp_path = meta_path + ".tmp"

    try:
        # Write to a temp file first, then atomically rename.
        # Protects against a half-written JSON if the Pi loses power mid-write.
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
            f.flush()            # clear Python's write buffer
            os.fsync(f.fileno()) # force OS to flush to SD card

        os.replace(temp_path, meta_path)  # atomic on Linux

    except Exception as e:
        logger.error(f"Failed to write metadata for {flac_path}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)

    logger.debug(f"Metadata written → {os.path.basename(meta_path)}")
    return meta_path
