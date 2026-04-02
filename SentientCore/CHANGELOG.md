# AquaEye-Sentient — Development Changelog

**Student:** Fazley Alahi (1934714)
**Cycle:** AquaEye-Sentient (2025-26)
**Baseline inherited from:** AquaSound (2024-25) by Victory Anyalewechi

This file logs every change made to the codebase relative to the AquaSound baseline.
For each change: what was done, why it was necessary, and what it replaces or improves.

---

## Baseline: AquaSound (2024-25)

AquaSound's codebase consisted of a single monolithic script (`main_recording.py`)
and one Arduino sketch (`sensor_hub.ino`).

**What it did:**
- Recorded audio from the Raspberry Pi's default USB/onboard microphone at 48 kHz mono using PyAudio
- Converted each WAV recording to FLAC using soundfile
- Read Arduino sensor data (TDS, turbidity, GPS) over serial in a daemon thread, writing raw lines to a .txt log
- Uploaded FLAC files to Google Drive over Wi-Fi using OAuth2

**What it did NOT do:**
- Record from a hydrophone underwater
- Handle multiple audio sources
- Tag audio files with structured sensor metadata (no sidecar files)
- Handle SD card data from an autonomous recorder
- Have any separation of concerns — all logic lived in one file

**Critical gap:** No underwater acoustic data was ever captured. The microphone used
was not a hydrophone. All ML development in prior cycles used existing labelled datasets,
not data from the project's own hardware.

---

## AquaEye-Sentient Changes

---

### [001] Modular code structure

**What changed:** Split the monolithic `main_recording.py` into separate modules, each
with a single responsibility. Added `config.py` as a centralised settings file.

**Why necessary:** AquaSound's single-file approach made it difficult to modify one
part without risk of breaking another. With 3 HydroMoths, a puller, a stitcher,
a compressor, and an uploader all needing shared parameters, a single config file
prevents the same path or rate being hardcoded in multiple places.

**Files introduced:**
- `config.py` — all tunable parameters in one place
- `hydromoth_puller.py` — SD card pull with copy-verify-delete safety
- `session_stitcher.py` — groups staged WAVs into time-synchronised sessions
- `audio_processor.py` — WAV to FLAC conversion
- `serial_reader.py` — Arduino data ingest
- `metadata_writer.py` — structured sidecar files
- `main.py` — top-level orchestration
- `cloud_uploader.py` — Google Drive upload
- `pipeline_benchmark.py` — pipeline bench harness

**Replaces:** `main_recording.py` (AquaSound)

---

### [002] HydroMoth SD card pull instead of live PyAudio capture

**What changed:** The primary audio ingestion method is now SD card pulling
(`hydromoth_puller.py`) rather than live PyAudio capture from a USB microphone.

**Why necessary:** HydroMoth is a standalone autonomous recorder. It does not
stream audio live to the Pi over USB while recording — it writes WAV files
directly to its own MicroSD card on a schedule set by the HydroMoth app.
Attempting to use PyAudio to capture from a HydroMoth would miss the underwater
recordings entirely. The correct approach is to let the HydroMoth record
independently, then have the Pi collect the WAV files from the SD card
(mounted via USB card reader) at intervals.

PyAudio is retained only as a fallback stub for bench testing (e.g. testing
the pipeline with a regular USB microphone before hydrophone deployment).

**Replaces:** `record_audio()` in AquaSound's `main_recording.py`

---

### [003] Three-HydroMoth configuration (Config C — 120° spacing)

**What changed:** `config.py` defines a `HYDROMOTHS` list describing each of the
three units: its SD card mount point, its physical mounting angle on the buoy,
and its channel index.

**Why necessary:** Three HydroMoths are mounted at 0°, 120°, and 240° around the
buoy to achieve near-omnidirectional acoustic coverage. This addresses the central
engineering challenge of uncontrolled buoy rotation: a single HydroMoth has
directional sensitivity and will have blind spots depending on its heading at any
moment. Three units at 120° spacing significantly reduces the probability of all
three simultaneously facing away from an acoustic source.

The `angle_deg` field records the physical position of each unit relative to the
buoy structure. This is a fixed value set at deployment — it does not change at
runtime. It is used during the stitching stage to label which channel recorded
which file, enabling post-processing analysis of directional coverage.

Note: `angle_deg` is relative to the buoy, not to magnetic north. Absolute bearing
would require an IMU/compass (not fitted in this iteration).

**New in this cycle:** No previous AquaSound or AquaEye iteration used multiple
hydrophones or any directional configuration.

---

### [004] hydromoth_puller.py — SD card pull with copy-verify-delete safety

**What changed:** New module that copies WAV files from each HydroMoth SD card
to a local staging folder, then deletes the originals from the SD card after
a verified copy.

**Why necessary:** HydroMoth SD cards must be cleared periodically to free space
for new recordings. Simply deleting files after a naive copy risks losing data
if the copy is interrupted (e.g. SD card ejected mid-copy, disk full). The
copy-verify-delete sequence protects against this: the source file is never
deleted unless the staged copy size exactly matches the source size.

**Safety sequence per file:**
1. Copy WAV to `STAGING_FOLDER` with a prefixed name (`HM_A__YYYYMMDD_HHMMSS.WAV`)
2. Verify staged file size == source file size
3. Delete source only on a size match
4. If size mismatch: remove the partial copy, log an error, leave source intact
5. If file already staged: skip copy, attempt late-delete of source if size matches

**Staging filename format:** `{hydromoth_id}__{original_name}.WAV` (double underscore
separator `__` is used by `session_stitcher.py` to recover the unit ID and timestamp).

**Files introduced:** `hydromoth_puller.py`

**Replaces:** Nothing in AquaSound (entirely new functionality)

---

### [005] session_stitcher.py — groups staged WAVs into sessions

**What changed:** New module that groups the staged WAV files from all three
HydroMoths into time-synchronised sessions before compression.

**Why necessary:** Each HydroMoth records independently to its own SD card with
its own internal clock. After pulling, the staging folder contains files like:

```
HM_A__20250325_120000.WAV   (unit A, started 12:00:00)
HM_B__20250325_120001.WAV   (unit B, started 12:00:01 — 1 s clock drift)
HM_C__20250325_120000.WAV   (unit C, started 12:00:00)
HM_A__20250325_121000.WAV   (unit A, next recording window)
```

Without stitching, there is no way to know that the first three files are all
recordings of the same 10-minute acoustic window from three different angles.
Stitching groups them by timestamp proximity and assigns a shared `session_id`,
enabling future TDOA / bearing analysis across units.

**Algorithm:** Greedy chronological sweep — each file either joins the current
open group (if within `STITCH_TOLERANCE_SEC` of the group anchor timestamp) or
starts a new group. Sessions are flagged `complete=True` only if all 3 units
contributed. Partial sessions (1 or 2 units) are still processed.

**Files introduced:** `session_stitcher.py`

**Replaces:** An earlier draft that incorrectly placed stitching logic inside
`hydromoth_poller.py` (that file has been superseded entirely).

---

### [006] audio_processor.py — WAV to FLAC with benchmark timing

**What changed:** New module with a single function `convert_wav_to_flac()` that
reads a WAV file with `soundfile` and writes a FLAC file losslessly.

**Why FLAC:** FLAC is the industry standard for Passive Acoustic Monitoring research.
It is lossless (no audio data discarded), typically ~50–60% smaller than the
source WAV, and is natively supported by analysis tools (Raven Pro, PAMGuard, Python
`soundfile`). WAV files from HydroMoth are large (96 kHz × 16-bit × 10 min ≈ 110 MB
per unit); FLAC reduces this to ~55–65 MB, meaningfully reducing upload bandwidth
and Google Drive quota consumption.

**Returns:** A dict with `success`, `wav_bytes`, `flac_bytes`, `encode_sec`, `error`.
The `encode_sec` field is measured with `time.perf_counter()` specifically to validate
D.2 Power System Analysis Assumption A3 (encode time ~8 s per file at 96 kHz).

**Replaces:** The `convert_to_flac()` function in AquaSound's `main_recording.py`
(which had no return value, no error handling, and no timing)

---

### [007] metadata_writer.py — structured JSON sidecar per FLAC

**What changed:** New module that writes a `_meta.json` sidecar file alongside
each FLAC immediately after compression.

**Why necessary:** AquaSound wrote Arduino sensor data to a plain `.txt` log with
no link between a sensor reading and a specific audio recording. There was no way
to know what the GPS position or water quality values were at the moment a given
recording was made. The sidecar approach ties each audio file to its environmental
context at recording time.

**Contents of each `_meta.json`:**
- `schema_version` — version string for future parser compatibility
- `written_utc` — ISO 8601 timestamp of when the sidecar was written
- `session_id` — shared ID linking concurrent recordings across all 3 units
- `audio`: `flac_file`, `hydromoth_id`, `angle_deg`, `channel`, `sample_rate`
- `gps`: `lat`, `lon`, `alt_m`, `date`, `time_utc`
- `water_quality`: `tds_ppm`, `tds_voltage`, `turbidity_v`
- `orientation`: `heading_deg` (null until IMU fitted)

All sensor fields are written as `null` (not omitted) if the Arduino is not
connected, so the schema is identical for every file — easier to parse in
post-processing.

**Replaces:** Raw `.txt` sensor log from AquaSound (retained for reference only)

---

### [008] serial_reader.py — structured in-memory sensor access

**What changed:** Written as a proper standalone module with three public components:
`parse_serial_line()`, `get_latest_reading()`, and `start()`.

**Why the AquaSound version could not be reused:**
AquaSound had no `serial_reader.py`. The entire serial logic was one function
inside `main_recording.py`:

```python
def read_serial():
    ser = serial.Serial('/dev/ttyACM0', 9600)
    while True:
        line = ser.readline().decode('utf-8').strip()
        with open(sensor_readings, 'a') as f:
            f.write(line + '\n')
```

This only dumped raw text to a file. Three problems make it unusable here:

1. **No structured access.** `metadata_writer.py` needs GPS, TDS, and turbidity
   values at the moment an audio file is processed. It cannot parse a growing
   .txt file at that point. The new module keeps the latest reading in memory
   in a dict, updated continuously, accessible via `get_latest_reading()`.

2. **Hardcoded port and baud.** `config.py` now owns these. The new module
   imports `SERIAL_PORT` and `SERIAL_BAUD` from config — nothing is hardcoded.

3. **No error handling.** If the Arduino disconnects mid-deployment, the old
   function would throw an unhandled exception and the thread would die silently.
   The new module catches `SerialException`, logs a warning, waits 5 seconds,
   and attempts to reconnect — keeping the system alive through hardware glitches.

**What is preserved from AquaSound:**
- Raw lines are still appended to the sensor log file (`SENSOR_LOG` from config)
- The thread is still a daemon (dies cleanly when the main process exits)
- Serial format from `sensor_hub.ino` is unchanged — parsing is designed around it

**New functions:**
- `parse_serial_line(line)` — regex extraction of TDS voltage, TDS ppm,
  turbidity voltage, GPS lat/lon/alt/date/time, and optional heading field
- `get_latest_reading()` — thread-safe snapshot of latest parsed values
- `start()` — called once from `main.py` at startup; launches the daemon thread

**Thread safety:** A `threading.Lock` protects the shared `_latest` dict so
`get_latest_reading()` in the main thread and `_serial_loop()` in the background
thread never access it simultaneously.

---

### [009] cloud_uploader.py — three fixes over AquaSound

**What changed:** Ported from AquaSound's `main_recording.py` authenticate/upload
logic. Three issues from the AquaSound version are fixed.

**Fix 1 — Token storage format:**
AquaSound used `pickle` (token.pickle) to store the OAuth2 token. Google's own
library now uses JSON (token.json). Switched to JSON so the token file is
human-readable and compatible with the current google-auth library without
deprecation warnings.

**Fix 2 — Sidecar upload:**
AquaSound only uploaded `.flac` files. Each FLAC now has a `_meta.json` sidecar
that must be uploaded alongside it so the two files stay linked in Drive. FLAC
and sidecar are treated as a pair: if the FLAC upload fails, the sidecar is not
moved either, so both retry together next cycle.

**Fix 3 — MIME types:**
AquaSound hardcoded `audio/flac` for all uploads. JSON sidecars now use
`application/json`. Unknown extensions fall back to `application/octet-stream`.

**Added — Connectivity check:**
A `_is_connected()` check (HTTP GET to google.com, 5 s timeout) runs before
attempting any upload. If no internet connection is detected, the upload step
is skipped cleanly and the pending file count is logged. This prevents the system
from hanging on OAuth token refresh when there is no internet.

---

### [010] main.py — two-mode orchestration with RTC halt

**What changed:** New top-level script replacing AquaSound's `main_recording.py`.

**Loop mode (default):** Runs pipeline cycles continuously, sleeping
`POLL_INTERVAL_SEC` between them. Used for bench testing and development.
Does not halt the Pi.

**Once mode (`--once`):** Runs exactly one pipeline cycle, then calls
`sudo rtcwake -m halt -s N` to halt the Pi and schedule the next wake via the
Pi 5's built-in PCF85063A RTC. This is the D.2 power model: ~70 s active per
10-minute cycle, ~530 s halted. The halt state draws ~20 mA vs 600–900 mA active,
giving an estimated 6–7× improvement in energy per cycle.

**Resilience:** Each pipeline step (pull, stitch, encode, upload) is wrapped in
an individual try/except. A single bad file or a missing SD card logs an error
and allows the cycle to continue — it does not crash the system.

**Replaces:** `main_recording.py` (AquaSound)

---

### [011] pipeline_benchmark.py — pipeline bench harness for D.2 validation

**What changed:** New module for measuring real pipeline performance on the Pi 5
before deployment.

**Why necessary:** The D.2 Power System Analysis makes specific time assumptions
that determine whether the duty cycle model is valid:
- A3: encode time ~8 s per file at 96 kHz (HIGH risk — untested on Pi 5)
- A4: overhead (pull + stitch + metadata + upload) ~20 s per cycle

If these are wrong, the calculated 70 s active window is wrong, which invalidates
the entire power budget. `pipeline_benchmark.py` measures actual times on real hardware
before committing to the power system design.

**Features:**
- `--generate_wav`: creates synthetic 60 s silence WAV files at 96 kHz if no
  real HydroMoth recordings are available yet
- `--wav_dir`: use real recordings from a specified directory
- `--cycles N`: run N back-to-back cycles for statistical reliability
- `--no_serial`: run without Arduino connected (sensor fields will be null)
- Per-step timing: `t_stage`, `t_stitch`, `t_encode`, `t_metadata`, `t_total`
- Output: per-cycle table, aggregate stats (mean/SD/min/max), D.2 comparison
  table flagging each assumption as OK or REVISE

---

### [012] Arduino sensor_hub.ino — three changes from AquaSound

**What changed:** Ported from `Inherited_Codes/AquaSound_2024-25_Victory/arduino/sensor_hub.ino`
to `SentientCore/arduino/sensor_hub/sensor_hub.ino`. Three changes from the original.

**Change 1 — Startup message:**
Changed `"AquaSound Sensor Hub Starting..."` to `"AquaEye-Sentient Sensor Hub Starting..."`
for correct project identification in the serial monitor.

**Change 2 — IMU heading stub:**
A commented-out block is added at the end of the serial print section, marking
exactly where `" Heading: X.XX deg"` would be appended when a compass/IMU is fitted
to the Arduino. `serial_reader.py`'s `parse_serial_line()` regex already handles
this optional field gracefully (returns `null` when absent). The stub prevents
this from being a redesign exercise later — it is a one-line uncomment.

**Change 3 — File location:**
Moved to the correct project structure (`SentientCore/arduino/sensor_hub/`) instead
of the inherited `Inherited_Codes/` folder. All deployment and future modifications
should use the `SentientCore/` copy.

**Core logic unchanged:** TDS median filter, turbidity 100-sample average, GPS
TinyGPS++ decode, non-blocking `millis()` loop — all identical to AquaSound.
Serial output format is verified to match all regex patterns in `serial_reader.py`
exactly.

**Known limitations (documented, not fixed):**
- TDS temperature hardcoded at 25°C. Acceptable for bench testing. For Aegean Sea
  deployment (15–25°C), connect a DS18B20 waterproof probe to update `temperature`.
- GPS decode uses a blocking `while` loop capped at 1000 ms. Acceptable given the
  ~1 s GPS sentence interval, but the loop body can take up to 1 s.
