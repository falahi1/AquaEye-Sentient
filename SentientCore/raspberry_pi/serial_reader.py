# =============================================================================
# AquaEye-Sentient — serial_reader.py
# =============================================================================
# Reads sensor data from the Arduino (custom sketch) over UART in a
# background daemon thread. Parses each line into structured fields and
# makes the latest reading available thread-safely to other modules.
#
# ARDUINO SKETCH OUTPUT FORMAT
# ----------------------------
# Two line types are produced by the Arduino:
#
#   1. NMEA GPS sentences (raw pass-through from GPS module):
#        $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,...
#        $GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,...
#        $GPGLL, $GPGSV, etc. (ignored)
#      Also handles GN-prefix variants ($GNGGA, $GNRMC) from combined
#      GPS/GLONASS modules.
#
#   2. Sensor readings (every 2 seconds):
#        [SENSOR] Temp: 22.50 C | Turbidity: 2.10 V | TDS: 1.30 V
#        [SENSOR] Temp: ERROR (Check Resistor/Wiring) | Turbidity: ... | TDS: ...
#
# All other lines (startup message, blank lines) are logged raw and ignored.
#
# TDS PPM CONVERSION
# ------------------
# The Arduino sketch outputs raw TDS voltage only. PPM is calculated here
# using the same formula as sensor_hub.ino (assumed 25°C — will be replaced
# with DS18B20 temp once cross-module sharing is implemented):
#   tds_ppm = (133.42*v^3 - 255.86*v^2 + 857.39*v) * 0.5
#
# GPS COORDINATE CONVERSION
# -------------------------
# NMEA encodes coordinates as DDMM.MMMM — converted to decimal degrees:
#   decimal = DD + MM.MMMM / 60
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
    "temp_c":        None,
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
# Pre-compiled regex patterns
# -----------------------------------------------------------------------------
_RE_SENSOR = re.compile(
    r"\[SENSOR\]\s+Temp:\s+(?P<temp>[\d.]+|ERROR[^|]*)"
    r"\s*\|\s*Turbidity:\s+(?P<turb>[\d.]+)\s*V"
    r"\s*\|\s*TDS:\s+(?P<tds>[\d.]+)\s*V",
    re.IGNORECASE,
)

# NMEA sentence types we care about (GP and GN prefixes)
_RE_GGA = re.compile(r"^\$(GP|GN)GGA,")
_RE_RMC = re.compile(r"^\$(GP|GN)RMC,")


# -----------------------------------------------------------------------------
# TDS voltage → ppm conversion
# Same formula as sensor_hub.ino (temperature-compensated at 25°C)
# -----------------------------------------------------------------------------
def _tds_voltage_to_ppm(voltage: float) -> float:
    compensation = 1.0 + 0.02 * (25.0 - 25.0)   # = 1.0 at 25°C
    cv = voltage / compensation
    return (133.42 * cv**3 - 255.86 * cv**2 + 857.39 * cv) * 0.5


# -----------------------------------------------------------------------------
# NMEA coordinate conversion: DDMM.MMMM → decimal degrees
# -----------------------------------------------------------------------------
def _nmea_to_decimal(value: str, direction: str) -> float | None:
    """Convert NMEA DDMM.MMMM + N/S/E/W to signed decimal degrees."""
    try:
        value = value.strip()
        if not value:
            return None
        dot = value.index(".")
        degrees = float(value[:dot - 2])
        minutes = float(value[dot - 2:])
        decimal = degrees + minutes / 60.0
        if direction.upper() in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except (ValueError, IndexError):
        return None


# -----------------------------------------------------------------------------
# Parse a $GPGGA / $GNGGA sentence → lat, lon, alt
# Format: $GPGGA,HHMMSS.ss,DDMM.MMMM,N,DDDMM.MMMM,E,Q,...,ALT,M,...
# -----------------------------------------------------------------------------
def _parse_gga(line: str) -> dict | None:
    parts = line.split(",")
    if len(parts) < 10:
        return None
    fix_quality = parts[6].strip()
    if fix_quality == "0" or fix_quality == "":
        return None   # no fix — indoors GPS will hit this
    lat = _nmea_to_decimal(parts[2], parts[3])
    lon = _nmea_to_decimal(parts[4], parts[5])
    try:
        alt = float(parts[9]) if parts[9].strip() else None
    except ValueError:
        alt = None
    if lat is None or lon is None:
        return None
    return {"gps_lat": lat, "gps_lon": lon, "gps_alt_m": alt}


# -----------------------------------------------------------------------------
# Parse a $GPRMC / $GNRMC sentence → date, time
# Format: $GPRMC,HHMMSS.ss,A,DDMM,N,DDDMM,E,...,DDMMYY,...
# -----------------------------------------------------------------------------
def _parse_rmc(line: str) -> dict | None:
    parts = line.split(",")
    if len(parts) < 10:
        return None
    status = parts[2].strip()
    if status != "A":
        return None   # void — no valid fix
    time_raw = parts[1].strip()
    date_raw = parts[9].strip()
    try:
        time_utc = f"{time_raw[:2]}:{time_raw[2:4]}:{time_raw[4:6]}"
        date_str = f"{date_raw[2:4]}/{date_raw[:2]}/{date_raw[4:6]}"
    except IndexError:
        return None
    return {"gps_date": date_str, "gps_time_utc": time_utc}


# -----------------------------------------------------------------------------
# Parse one line from the Arduino
# -----------------------------------------------------------------------------
def parse_serial_line(line: str) -> dict | None:
    """
    Parse one line from the Arduino sketch into a structured dict.

    Returns a partial dict of fields parsed from this line, or None if the
    line contains no recognisable data (startup message, blank line, etc.).
    Fields not present in this line are not included in the returned dict —
    callers should update shared state with dict.update(), not replace it.
    """
    # --- [SENSOR] line ---
    m = _RE_SENSOR.search(line)
    if m:
        result = {}

        temp_str = m.group("temp").strip()
        if temp_str.upper().startswith("ERROR"):
            result["temp_c"] = None
        else:
            try:
                result["temp_c"] = float(temp_str)
            except ValueError:
                result["temp_c"] = None

        try:
            turb_v = float(m.group("turb"))
            result["turbidity_v"] = turb_v
        except ValueError:
            result["turbidity_v"] = None

        try:
            tds_v = float(m.group("tds"))
            result["tds_voltage"] = tds_v
            result["tds_ppm"] = round(_tds_voltage_to_ppm(tds_v), 2)
        except ValueError:
            result["tds_voltage"] = None
            result["tds_ppm"] = None

        result["raw_line"] = line
        return result

    # --- GGA sentence (lat/lon/alt) ---
    if _RE_GGA.match(line):
        parsed = _parse_gga(line)
        if parsed:
            parsed["raw_line"] = line
        return parsed   # may be None if no fix

    # --- RMC sentence (date/time) ---
    if _RE_RMC.match(line):
        parsed = _parse_rmc(line)
        if parsed:
            parsed["raw_line"] = line
        return parsed   # may be None if void

    return None


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

            with open(SENSOR_LOG, "a") as log_file:
                while True:
                    raw = ser.readline()
                    if not raw:
                        continue

                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue

                    try:
                        log_file.write(line + "\n")
                        log_file.flush()
                    except OSError as e:
                        logger.warning(f"Could not write to sensor log: {e}")

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
