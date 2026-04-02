# =============================================================================
# AquaEye-Sentient — serial_reader.py
# =============================================================================
# Reads sensor data from the Arduino (sensor_hub.ino) over UART in a
# background daemon thread. Parses each line into structured fields and
# makes the latest reading available thread-safely to other modules.
#
# Inherited from: AquaSound (2024-25) had no serial_reader.py. The serial
# logic was a single bare function (read_serial) inside main_recording.py
# that only dumped raw lines to a .txt file with no parsing and no way for
# other modules to access the data. This module replaces that approach.
#
# Why this is needed:
#   metadata_writer.py needs structured sensor values (GPS, TDS, turbidity)
#   at the moment each audio file is processed — not a growing text file to
#   parse later. This module keeps the latest reading in memory, thread-safe,
#   so any module can call get_latest_reading() at any point.
# =============================================================================

import threading
import serial
import time
import re
import logging

from config import SERIAL_PORT, SERIAL_BAUD, SENSOR_LOG

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Shared state — protected by a lock so main thread can read safely
# -----------------------------------------------------------------------------
_lock   = threading.Lock()
_latest = {
    "tds_voltage":   None,
    "tds_ppm":       None,
    "turbidity_v":   None,
    "gps_lat":       None,
    "gps_lon":       None,
    "gps_alt_m":     None,
    "gps_date":      None,
    "gps_time_utc":  None,
    "heading_deg":   None,   # null until IMU is fitted to Arduino
    "raw_line":      None,
}


def get_latest_reading():
    """
    Return a snapshot of the most recent parsed sensor reading.
    Thread-safe — safe to call from main.py or metadata_writer.py at any time.
    Returns a dict. Any field not yet received from Arduino will be None.
    """
    with _lock:
        return dict(_latest)


# -----------------------------------------------------------------------------
# Parsing
# -----------------------------------------------------------------------------

def parse_serial_line(line):
    """
    Parse one line from sensor_hub.ino into a structured dict.

    Expected format from Arduino (single line, all on one row):
      TDS Voltage: 2.34 V TDS Value: 456.78 ppm Turbidity Voltage: 1.23 V
      Latitude: 37.123456, Longitude: 26.654321, Altitude: 5 meters
      Date: 3/25/25 Time(UTC): 12:30:45
      [Heading: 273.4 deg]   <- optional, only when IMU fitted

    Returns a dict with parsed fields, or None if the line is not a valid
    data line (e.g. the startup message "AquaSound Sensor Hub Starting...").
    """
    if "TDS Voltage" not in line:
        return None

    result = {}

    # TDS voltage
    m = re.search(r"TDS Voltage:\s*([\d.]+)\s*V", line)
    result["tds_voltage"] = float(m.group(1)) if m else None

    # TDS ppm
    m = re.search(r"TDS Value:\s*([\d.]+)\s*ppm", line)
    result["tds_ppm"] = float(m.group(1)) if m else None

    # Turbidity voltage
    m = re.search(r"Turbidity Voltage:\s*([\d.]+)\s*V", line)
    result["turbidity_v"] = float(m.group(1)) if m else None

    # GPS latitude
    m = re.search(r"Latitude:\s*([-\d.]+)", line)
    result["gps_lat"] = float(m.group(1)) if m else None

    # GPS longitude
    m = re.search(r"Longitude:\s*([-\d.]+)", line)
    result["gps_lon"] = float(m.group(1)) if m else None

    # GPS altitude
    m = re.search(r"Altitude:\s*([\d.]+)\s*meters", line)
    result["gps_alt_m"] = float(m.group(1)) if m else None

    # GPS date
    m = re.search(r"Date:\s*(\S+)", line)
    result["gps_date"] = m.group(1) if m else None

    # GPS time UTC
    m = re.search(r"Time\(UTC\):\s*(\S+)", line)
    result["gps_time_utc"] = m.group(1) if m else None

    # Heading (optional — only present when IMU is fitted to Arduino)
    m = re.search(r"Heading:\s*([\d.]+)\s*deg", line)
    result["heading_deg"] = float(m.group(1)) if m else None

    result["raw_line"] = line
    return result


# -----------------------------------------------------------------------------
# Background thread
# -----------------------------------------------------------------------------

def _serial_loop():
    """
    Runs forever as a daemon thread. Connects to Arduino, reads lines,
    parses them, updates shared state, and writes to the sensor log file.

    If the Arduino disconnects (serial exception), waits 5 seconds and
    attempts to reconnect. This prevents a hardware glitch from silently
    killing the thread for the rest of a deployment.
    """
    while True:
        try:
            logger.info(f"Connecting to Arduino on {SERIAL_PORT} at {SERIAL_BAUD} baud")
            ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=2)
            logger.info("Arduino connected")

            while True:
                raw = ser.readline()
                if not raw:
                    continue  # timeout — no data, loop back

                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                # Write raw line to sensor log (same behaviour as AquaSound)
                try:
                    with open(SENSOR_LOG, "a") as f:
                        f.write(line + "\n")
                except OSError as e:
                    logger.warning(f"Could not write to sensor log: {e}")

                # Parse and update shared state
                parsed = parse_serial_line(line)
                if parsed:
                    with _lock:
                        _latest.update(parsed)

        except serial.SerialException as e:
            logger.warning(f"Serial error: {e} — retrying in 5 s")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Unexpected error in serial thread: {e} — retrying in 5 s")
            time.sleep(5)


def start():
    """
    Start the serial reader as a background daemon thread.
    Call once from main.py at startup. Returns immediately.
    """
    t = threading.Thread(target=_serial_loop, daemon=True, name="serial_reader")
    t.start()
    logger.info("Serial reader thread started")
