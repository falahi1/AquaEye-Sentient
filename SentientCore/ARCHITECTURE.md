# AquaEye-Sentient — Code Architecture

**Student:** Fazley Alahi (1934714)
**Cycle:** AquaEye-Sentient (2025-26)
**Inherited from:** AquaSound (2024-25) by Victory Anyalewechi

---

## What We Inherit from AquaSound

AquaSound's `main_recording.py` is a single monolithic script. It does:

1. **Serial read** — daemon thread reads Arduino sensor data (TDS, turbidity, GPS) over UART and writes raw lines to a `.txt` log file
2. **Audio record** — PyAudio captures from the system's default audio input at 48 kHz mono, saves as `.wav`
3. **FLAC convert** — `soundfile` compresses each `.wav` to `.flac` in-place
4. **Cloud upload** — Google Drive OAuth2 upload for any pending `.flac` files when Wi-Fi is available

The `sensor_hub.ino` is already well-structured: non-blocking millis-based loop reading TDS, turbidity, and GPS, printing one combined line per cycle over serial at 9600 baud.

**What AquaSound did NOT do:**
- Record from a hydrophone (it used the Pi's onboard/USB mic at 48 kHz — no underwater audio)
- Handle multiple audio sources simultaneously
- Tag audio files with sensor metadata (heading, GPS, timestamp) as a structured sidecar
- Have any SD-card polling from a HydroMoth
- Stage, group, or stitch files from multiple independent recorders

---

## What AquaEye-Sentient Adds (This Cycle)

The central new element is the **HydroMoth** as the primary underwater acoustic sensor.

The HydroMoth records autonomously to its own MicroSD card in scheduled or triggered mode. It does **not** stream audio live over USB to the Pi while recording — it is a standalone recorder. Therefore the integration approach is **SD-card pull**: the Pi periodically copies new `.WAV` files from each HydroMoth SD card to a local staging area, groups them into sessions by timestamp, compresses them, tags them with sensor metadata, and uploads.

The old `record_audio()` PyAudio approach is **not the primary path** for hydrophone data. It is retained only as a fallback/test mode.

---

## Folder Structure

```
SentientCore/
│
├── ARCHITECTURE.md              ← this file
├── CHANGELOG.md                 ← per-change log relative to AquaSound baseline
│
├── raspberry_pi/                ← runs on Raspberry Pi 5
│   ├── config.py                ← ALL tunable parameters (paths, rates, device IDs)
│   ├── main.py                  ← top-level orchestration: loop or --once (RTC halt)
│   ├── hydromoth_puller.py      ← copies WAV files from each HydroMoth SD card to staging
│   ├── session_stitcher.py      ← groups staged WAV files into time-synchronised sessions
│   ├── audio_processor.py       ← WAV → FLAC conversion (soundfile)
│   ├── metadata_writer.py       ← writes _meta.json sidecar alongside each FLAC
│   ├── serial_reader.py         ← Arduino sensor data ingest (daemon thread)
│   ├── cloud_uploader.py        ← Google Drive OAuth2 upload (FLAC + sidecar pairs)
│   └── pipeline_benchmark.py    ← pipeline bench harness for D.2 power model validation
│
├── arduino/
│   └── sensor_hub/
│       └── sensor_hub.ino       ← Arduino C++: TDS + turbidity + GPS (+ IMU heading stub)
│
└── ml_classifier/               ← offline post-processing (not on-device)
    ├── random_forest_classifier.py
    ├── gradient_boosting_classifier.py
    └── knn_classifier.py
```

---

## System Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BUOY (at sea)                               │
│                                                                     │
│  ┌──────────────────┐      ┌─────────────────────────────────────┐  │
│  │  HydroMoth ×3    │      │          Raspberry Pi 5             │  │
│  │  (0°, 120°, 240°)│      │                                     │  │
│  │                  │      │  main.py (orchestration loop)       │  │
│  │  Records .WAV    │      │   │                                 │  │
│  │  autonomously    │─USB─▶│   ├─ hydromoth_puller.py            │  │
│  │  to SD card      │ mount│   │    copy WAV → staging/          │  │
│  └──────────────────┘      │   │    verify size → delete source  │  │
│                             │   │                                 │  │
│                             │   ├─ session_stitcher.py            │  │
│                             │   │    group files by timestamp     │  │
│                             │   │    assign shared session_id     │  │
│                             │   │                                 │  │
│                             │   ├─ audio_processor.py             │  │
│                             │   │    WAV → FLAC (lossless)        │  │
│                             │   │                                 │  │
│                             │   ├─ metadata_writer.py             │  │
│                             │   │    write _meta.json sidecar     │  │
│                             │   │                                 │  │
│  ┌──────────────────┐      │   ├─ serial_reader.py  [thread]    │  │
│  │  Arduino         │      │   │    TDS / turbidity / GPS / hdg  │  │
│  │  sensor_hub      │─UART▶│   │                                 │  │
│  │                  │ 9600 │   └─ cloud_uploader.py              │  │
│  │  TDS       A1    │      │        FLAC + _meta.json → Drive    │  │
│  │  Turbidity A0    │      └──────────────────────┬──────────────┘  │
│  │  GPS     D2/D3   │                             │ Wi-Fi           │
│  │  (IMU    future) │                             │                 │
│  └──────────────────┘                             │                 │
└──────────────────────────────────────────────────┼─────────────────┘
                                                   ▼
                                           [Google Drive]
                                    FLAC files + _meta.json sidecars

─────────────────────────────────────────────────────────────────────
  OFFLINE (lab / desktop)

  .flac files + _meta.json sidecars
       ↓
  ml_classifier/*.py  (using Species Data.csv from Raven Pro)
       ↓
  Species predictions.csv
```

---

## Module Responsibilities

### `config.py`
Single source of truth for all parameters. Nothing else in the codebase has
hardcoded paths, ports, or rates. Edit this file first for any deployment changes.

Key parameters:
- `HYDROMOTHS` — list of dicts, one per unit: `id`, `sd_mount`, `angle_deg`, `channel`
- `STAGING_FOLDER` — local directory where pulled WAV files are held before processing
- `STITCH_TOLERANCE_SEC` — max timestamp difference (seconds) for two files to be grouped into the same session (default: 5)
- `SAMPLE_RATE` — recording sample rate set on the HydroMoth devices (e.g. 96000)
- `SERIAL_PORT` — Arduino UART port (e.g. `/dev/ttyACM0`)
- `FLAC_FOLDER`, `UPLOADED_FOLDER` — local storage paths
- `PROCESSED_LOG` — flat text file tracking which staged WAVs have been compressed
- `GOOGLE_DRIVE_FOLDER_ID` — Drive folder for uploads
- `POLL_INTERVAL_SEC` — seconds between pipeline cycles

### `main.py`
Top-level orchestration. Two operating modes:

- **Loop mode** (default): runs cycles continuously, sleeping `POLL_INTERVAL_SEC` between them. Used for bench testing and development.
- **Once mode** (`--once`): runs exactly one cycle, then halts the Pi via `sudo rtcwake -m halt -s N`. This is the D.2 power model — 70 s active per 10-minute cycle, ~530 s halted.

A single failed step (SD card not mounted, Wi-Fi down, bad file) logs an error and continues — it does not crash the system.

### `hydromoth_puller.py`
Copies new WAV files from each HydroMoth SD card to `STAGING_FOLDER`.

Safety sequence per file:
1. Copy WAV to staging with a prefixed name (`HM_A__20250325_120000.WAV`)
2. Verify the staged file size matches the source
3. Only delete the source after a verified size match
4. If size mismatch: remove the partial copy, log an error, do not delete source

Key function: `pull_all() -> dict` with `pulled`, `skipped`, `failed` counts.

### `session_stitcher.py`
Groups staged WAV files from all three HydroMoths into time-synchronised sessions.

Algorithm:
1. Parse the timestamp from every staged WAV filename
2. Sort all files chronologically
3. Sweep through: each file either joins the current open group (if within `STITCH_TOLERANCE_SEC` of the group anchor) or starts a new group
4. Each group becomes a session with a shared `session_id` (format: `YYYYMMDD_HHMMSS`)

Sessions are flagged `complete=True` only if all three HydroMoths contributed a file.
Partial sessions (1 or 2 units) are still returned and processed.

Key function: `get_unprocessed_sessions() -> list`

### `audio_processor.py`
Single function: `convert_wav_to_flac(wav_path, flac_path) -> dict`

Uses `soundfile` to read WAV and write FLAC (lossless). Returns timing and size
information for benchmarking against D.2 Assumption A3 (encode time ~8 s/file).

### `metadata_writer.py`
Writes a `_meta.json` sidecar file alongside each FLAC. Contents:
- `schema_version`, `written_utc`, `session_id`
- `audio`: `flac_file`, `hydromoth_id`, `channel`, `angle_deg`, `sample_rate`
- `gps`: `lat`, `lon`, `alt_m`, `date`, `time_utc`
- `water_quality`: `tds_ppm`, `tds_voltage`, `turbidity_v`
- `orientation`: `heading_deg` (null until IMU fitted)

All sensor fields are written as `null` (not omitted) if the Arduino is not connected,
keeping the schema consistent across all files.

### `serial_reader.py`
Daemon thread reads Arduino serial lines continuously. `parse_serial_line()` extracts
TDS voltage/ppm, turbidity voltage, GPS lat/lon/alt/date/time, and optional heading.
`get_latest_reading()` gives `main.py` a thread-safe snapshot for the metadata writer.
Reconnects automatically if the Arduino disconnects mid-deployment.

### `cloud_uploader.py`
Uploads all pending FLAC files and their `_meta.json` sidecars to Google Drive.
FLAC and sidecar are treated as a pair: if the FLAC upload fails, neither file is
moved to `UPLOADED_FOLDER` so both retry together next cycle.

Three improvements over AquaSound:
1. Token stored as JSON (not pickle) — compatible with current Google library
2. Uploads `_meta.json` sidecars alongside each FLAC
3. Correct mimetypes per file type (`audio/flac` vs `application/json`)

### `pipeline_benchmark.py`
Pipeline bench harness for validating D.2 power model assumptions before deployment.

- Generates synthetic WAV files or uses real recordings (`--wav_dir`)
- Stages test files, runs full stitch → encode → metadata pipeline per cycle
- Times each step individually and reports mean/SD/min/max across N cycles
- Compares measured times against D.2 thresholds and flags OK / REVISE
- `--no_serial` flag for running without Arduino connected

Usage: `python3 pipeline_benchmark.py --wav_dir ~/aquaeye/bench_wav --cycles 10 --no_serial`

### `sensor_hub.ino`
Ported from AquaSound. Non-blocking `millis()` loop reading:
- TDS sensor (A1) — 30-sample median filter, 25°C temperature compensation
- Turbidity sensor (A0) — 100-sample average
- GPS (D2/D3 SoftwareSerial) — TinyGPS++ NMEA decode

One combined serial line is printed per cycle at 9600 baud. An IMU heading stub
marks exactly where `" Heading: X.XX deg"` would be appended when a compass is fitted.
`serial_reader.py`'s regex already handles this optional field.

### `ml_classifier/*.py`
Offline scripts — not deployed on the buoy. Inherited from AquaEye (2023-24).
Run on a laptop after collecting labelled data from Raven Pro.

---

## Pipeline Cycle (One Execution of `run_cycle()`)

```
Step 1 — Pull
  hydromoth_puller.pull_all()
  → copies new WAVs from each SD card to STAGING_FOLDER
  → verifies size, deletes source originals

Step 2 — Stitch
  session_stitcher.get_unprocessed_sessions()
  → groups staged WAVs by timestamp proximity
  → returns list of session dicts (each with files sorted by channel)

Step 3+4 — Encode + Metadata  (per session, per file)
  audio_processor.convert_wav_to_flac()
  → WAV → FLAC in FLAC_FOLDER
  metadata_writer.write_metadata()
  → writes <stem>_meta.json alongside FLAC
  → appends WAV path to PROCESSED_LOG

Step 5 — Upload
  cloud_uploader.upload_pending()
  → uploads FLAC + sidecar pairs to Google Drive
  → moves uploaded files to UPLOADED_FOLDER
```

---

## Key Libraries

| Library | Module | Purpose |
|---------|--------|---------|
| soundfile | audio_processor | WAV → FLAC conversion |
| pyserial | serial_reader | UART to Arduino |
| requests | cloud_uploader | connectivity check (GET google.com) |
| google-api-python-client | cloud_uploader | Drive API v3 |
| google-auth-oauthlib | cloud_uploader | OAuth2 flow |
| pandas, numpy | ml_classifier | Data handling |
| scikit-learn | ml_classifier | RF, GBM, kNN models |
| TinyGPS++ (Arduino) | sensor_hub | NMEA GPS decode |
| SoftwareSerial (Arduino) | sensor_hub | GPS UART on D2/D3 |

> **Removed from AquaSound:** `pyaudio` (no longer primary path), `tkinter.messagebox`
> (not needed on headless Pi), `pickle`-based token replaced by JSON OAuth flow.

---

## HydroMoth Integration: Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Integration method | SD card pull-and-stage | HydroMoth records autonomously; no live USB audio stream |
| Number of units | 3 (Config C — 120° spacing) | Near-omnidirectional coverage despite uncontrolled buoy rotation |
| Sample rate | Set on HydroMoth device | 96 kHz covers dolphin whistles to ~48 kHz; 384 kHz for echolocation |
| Compression format | FLAC (lossless) | ~50–60% smaller than WAV; no audio data lost; PAM research standard |
| Source delete safety | Copy → verify size → delete | Never lose recordings if staging fails mid-copy |
| Session linking | Shared `session_id` in metadata | Enables post-processing TDOA / bearing analysis across units |
| Metadata format | JSON sidecar per file | Structured; consistent schema regardless of sensor availability |
| Orientation | Not yet fitted | `heading_deg` is `null` until IMU added to Arduino |
| Power management | RTC halt (`--once` mode) | Pi halts after each cycle; D.2 model: 70 s active / ~530 s halted |

---

## Build Order (for reference)

Modules were written in this order. Dependencies flow downward.

1. `config.py` — all parameters defined first
2. `serial_reader.py` — ported from AquaSound; no dependencies
3. `sensor_hub.ino` — Arduino code; ported from AquaSound
4. `hydromoth_puller.py` — depends on `config.py`
5. `session_stitcher.py` — depends on `config.py`, `hydromoth_puller.ID_SEP`
6. `audio_processor.py` — depends on `config.py`
7. `metadata_writer.py` — depends on nothing (pure function)
8. `cloud_uploader.py` — depends on `config.py`
9. `main.py` — wires all modules together
10. `pipeline_benchmark.py` — depends on all pipeline modules
