# =============================================================================
# AquaEye-Sentient — config.py
# =============================================================================
# Central configuration file. All tunable parameters live here.
# No other module should contain hardcoded paths, ports, or rates.
# Edit this file first whenever deploying to a new device or changing hardware.
#
# Inherited from: AquaSound (2024-25) had no config.py — all values were
# hardcoded inside main_recording.py. This file replaces that approach.
# =============================================================================

import os

# -----------------------------------------------------------------------------
# HYDROMOTH UNITS
# -----------------------------------------------------------------------------
# Three HydroMoths mounted at 120° spacing around the buoy (Config C).
# Each entry describes one physical unit.
#
#   id         : human-readable label, used in filenames and metadata
#   sd_mount   : path where that unit's SD card is mounted on the Pi
#                (via USB card reader — mount one card reader per unit)
#   angle_deg  : physical mounting angle relative to the buoy structure (fixed
#                at deployment). 0° is an arbitrary reference mark on the buoy.
#                This is NOT absolute bearing — no IMU fitted in this iteration.
#   channel    : integer index (0, 1, 2) used internally for ordering

HYDROMOTHS = [
    {
        "id":        "HM_A",
        "sd_mount":  "/media/pi/HYDROMOTH_A",
        "angle_deg": 0,
        "channel":   0,
    },
    {
        "id":        "HM_B",
        "sd_mount":  "/media/pi/HYDROMOTH_B",
        "angle_deg": 120,
        "channel":   1,
    },
    {
        "id":        "HM_C",
        "sd_mount":  "/media/pi/HYDROMOTH_C",
        "angle_deg": 240,
        "channel":   2,
    },
]

# -----------------------------------------------------------------------------
# AUDIO PARAMETERS
# -----------------------------------------------------------------------------
# SAMPLE_RATE must match the rate configured on each HydroMoth device using
# the HydroMoth / AudioMoth configuration app before deployment.
# 96000 Hz covers dolphin whistles (2–20 kHz) with headroom.
# Raise to 192000 or 384000 if targeting echolocation clicks (up to 130 kHz).
#
# STITCH_TOLERANCE_SEC: maximum difference in recording start times (derived
# from WAV filenames) for two files to be considered simultaneous and grouped
# into the same session. HydroMoth clocks drift slightly — 5 seconds is a
# safe tolerance for files intended to start at the same scheduled time.

SAMPLE_RATE          = 96000
STITCH_TOLERANCE_SEC = 5

# -----------------------------------------------------------------------------
# LOCAL STORAGE PATHS
# -----------------------------------------------------------------------------
# WAV files are pulled from each HydroMoth SD card into STAGING_FOLDER first,
# renamed with the HydroMoth ID prefix (e.g. HM_A__20250325_120000.WAV).
# The original is deleted from the SD card only after the copy is verified.
# Converted FLAC files and their _meta.json sidecars are stored in FLAC_FOLDER.
# After successful upload, files are moved to UPLOADED_FOLDER.
# PROCESSED_LOG tracks staged WAV files that have already been compressed so
# the stitcher does not reprocess them across cycles.

BASE_DIR        = "/home/pi/aquaeye"
STAGING_FOLDER  = os.path.join(BASE_DIR, "staging")
FLAC_FOLDER     = os.path.join(BASE_DIR, "flac_files")
UPLOADED_FOLDER = os.path.join(BASE_DIR, "flac_files", "uploaded")
PROCESSED_LOG   = os.path.join(BASE_DIR, "processed_files.log")
SENSOR_LOG      = os.path.join(BASE_DIR, "arduino_readings.txt")

# -----------------------------------------------------------------------------
# USB HUB POWER CONTROL
# -----------------------------------------------------------------------------
# The Pi cuts and restores power to the USB port the HydroMoth hub is plugged
# into using uhubctl — no relay or extra hardware needed.
#
# HOW TO FIND YOUR VALUES:
#   sudo apt install uhubctl
#   uhubctl                  # lists all hubs and ports
#
# Look for the port where your hub is connected. Example output:
#   Current status for hub 1-1 [VIA Labs 2.0 hub, USB 2.0, 4 ports]
#     Port 1: 0503 power highspeed enable connect   ← hub plugged in here
#
# → set HUB_LOCATION = "1-1", HUB_PORT = 1
#
# HUB_MOUNT_TIMEOUT_SEC: seconds to wait for all three SD cards to auto-mount
# after the hub powers on. 20 s is generous; typically takes 3–8 s.

HUB_LOCATION          = "1-1"  # update after running: uhubctl
HUB_PORT              = 1      # update after running: uhubctl
HUB_MOUNT_TIMEOUT_SEC = 20

# -----------------------------------------------------------------------------
# ARDUINO / SERIAL
# -----------------------------------------------------------------------------
# Must match the baud rate set in sensor_hub.ino (9600 by default).
# Port is typically /dev/ttyACM0 on Pi when Arduino is connected over USB.
# Change to /dev/ttyUSB0 if using a USB-to-serial adapter instead.

SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_BAUD = 9600

# -----------------------------------------------------------------------------
# CLOUD UPLOAD — GOOGLE DRIVE
# -----------------------------------------------------------------------------
# GOOGLE_DRIVE_FOLDER_ID: the ID of the Drive folder to upload into.
# Found in the folder's URL: drive.google.com/drive/folders/<ID>
# CREDENTIALS_FILE: OAuth2 client secrets downloaded from Google Cloud Console.
# TOKEN_FILE: cached OAuth2 token (created automatically on first run).

GOOGLE_DRIVE_FOLDER_ID = "11QAYDOyePI-2t7yBnwD4fmWrq0ojsDI7"
CREDENTIALS_FILE       = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE             = os.path.join(BASE_DIR, "token.json")

# -----------------------------------------------------------------------------
# MAIN LOOP TIMING
# -----------------------------------------------------------------------------
# POLL_INTERVAL_SEC: how often the main loop wakes up to check for new files
# on the HydroMoth SD cards. Set this to be shorter than the HydroMoth's
# recording segment length so files are collected promptly.
# Example: if HydroMoth records 5-minute files, polling every 60 seconds is fine.

POLL_INTERVAL_SEC = 60
