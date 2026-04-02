# AquaEye-Sentient — Raspberry Pi Pipeline

**Student:** Fazley Alahi (1934714)
**Cycle:** AquaEye-Sentient (2025-26)
**Target hardware:** Raspberry Pi 5

This folder contains the 8 deployable Python modules that run the full acoustic
data pipeline on the buoy. The pipeline collects WAV recordings from three HydroMoth
hydrophone recorders, compresses them to FLAC, attaches sensor metadata, and uploads
to Google Drive when Wi-Fi is available.

---

## Pipeline Overview

```
HydroMoth SD cards (×3)
        │
        ▼
hydromoth_puller   — copies WAV files to staging, verifies, deletes from SD
        │
        ▼
session_stitcher   — groups files from all 3 units by timestamp into sessions
        │
        ▼
audio_processor    — converts each WAV to FLAC (lossless)
        │
        ▼
metadata_writer    — writes _meta.json sidecar alongside each FLAC
        │
        ▼
cloud_uploader     — uploads FLAC + sidecar pairs to Google Drive (if Wi-Fi)
```

`serial_reader` runs as a background thread throughout, continuously reading
GPS, TDS, and turbidity data from the Arduino over UART.

---

## Files

| File | Purpose |
|------|---------|
| `config.py` | All tunable parameters — edit this first for any deployment |
| `main.py` | Top-level orchestration — the script you run on the Pi |
| `hydromoth_puller.py` | Pulls WAV files from each HydroMoth SD card to staging |
| `session_stitcher.py` | Groups staged WAVs into time-synchronised sessions |
| `audio_processor.py` | WAV → FLAC lossless compression |
| `metadata_writer.py` | Writes `_meta.json` sidecar file alongside each FLAC |
| `serial_reader.py` | Reads Arduino sensor data (GPS, TDS, turbidity) over UART |
| `cloud_uploader.py` | Uploads completed FLACs and sidecars to Google Drive |

---

## Dependencies

Install on the Pi before first run:

```bash
pip3 install soundfile pyserial requests google-api-python-client google-auth-oauthlib
```

Arduino library (in Arduino IDE):
- `TinyGPS++`
- `SoftwareSerial` (built-in)

---

## Configuration

Open `config.py` and set these before deploying:

**HydroMoth SD card mount points**
```python
HYDROMOTHS = [
    {"id": "HM_A", "sd_mount": "/media/pi/HYDROMOTH_A", "angle_deg": 0,   "channel": 0},
    {"id": "HM_B", "sd_mount": "/media/pi/HYDROMOTH_B", "angle_deg": 120, "channel": 1},
    {"id": "HM_C", "sd_mount": "/media/pi/HYDROMOTH_C", "angle_deg": 240, "channel": 2},
]
```
Check actual mount points with `lsblk` or `ls /media/pi/` after inserting the USB card readers.

**Sample rate** — must match what is set on the HydroMoth devices using the AudioMoth app:
```python
SAMPLE_RATE = 96000   # Hz — change to 192000 or 384000 for echolocation
```

**Arduino serial port:**
```python
SERIAL_PORT = "/dev/ttyACM0"   # or /dev/ttyUSB0 depending on connection type
```

**Google Drive folder ID** — from the Drive folder URL:
```python
GOOGLE_DRIVE_FOLDER_ID = "your_folder_id_here"
```

---

## Google Drive Setup (first time only)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable the Google Drive API
3. Create OAuth 2.0 credentials → Download as `credentials.json`
4. Place `credentials.json` at `/home/pi/aquaeye/credentials.json`
5. On first run, a browser window will open for sign-in. After signing in, `token.json`
   is saved automatically. All future runs are silent — no browser needed.

If the Pi has no display, run the first authentication on a desktop machine and
copy `token.json` to the Pi.

---

## Running

### Loop mode — for bench testing and development

Runs cycles continuously. The Pi stays on. Press `Ctrl+C` to stop.

```bash
python3 /home/pi/aquaeye/raspberry_pi/main.py
```

### Once mode — for field deployment on the buoy

Runs one cycle, then halts the Pi. The RTC wakes it up for the next cycle.
This is the low-power deployment mode.

```bash
python3 /home/pi/aquaeye/raspberry_pi/main.py --once
```

Requires `sudo` or passwordless sudo for `rtcwake` in `/etc/sudoers`:
```
pi ALL=(ALL) NOPASSWD: /usr/sbin/rtcwake
```

### Run on boot (systemd)

To start automatically on boot, create `/etc/systemd/system/aquaeye.service`:

```ini
[Unit]
Description=AquaEye-Sentient Pipeline
After=network.target

[Service]
ExecStart=python3 /home/pi/aquaeye/raspberry_pi/main.py --once
User=pi
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then enable:
```bash
sudo systemctl enable aquaeye.service
sudo systemctl start aquaeye.service
```

---

## Logs

All activity is logged to `/home/pi/aquaeye/aquaeye.log` and also printed to the terminal.

```bash
tail -f /home/pi/aquaeye/aquaeye.log   # live log output
```

Arduino sensor readings are also written to `/home/pi/aquaeye/arduino_readings.txt`.

---

## Folder Structure at Runtime

Once running, the pipeline creates and uses these folders:

```
/home/pi/aquaeye/
├── staging/              ← WAV files pulled from SD cards (temporary)
├── flac_files/           ← compressed FLACs + _meta.json sidecars
│   └── uploaded/         ← files moved here after successful upload
├── aquaeye.log           ← system log
├── arduino_readings.txt  ← raw Arduino serial lines
├── processed_files.log   ← tracks which staged WAVs have been compressed
├── credentials.json      ← Google OAuth credentials (you provide this)
└── token.json            ← Google OAuth token (auto-generated on first run)
```

---

## Hardware Wiring

**Arduino → Pi (UART):**
- Arduino USB → Pi USB port (appears as `/dev/ttyACM0`)

**HydroMoth SD cards → Pi:**
- 3× USB card readers → Pi USB ports
- Each card mounts automatically at `/media/pi/<label>`

**Arduino sensor wiring:**
- TDS sensor → A1
- Turbidity sensor → A0
- GPS TX → D2, GPS RX → D3

---

## Notes

- HydroMoth records autonomously to its own SD card — it does not stream live to the Pi
- The pipeline never deletes a file from the SD card unless the local copy is verified
- If Wi-Fi is unavailable, the upload step is skipped and files remain in `flac_files/` until the next cycle with connectivity
- Sensor fields in `_meta.json` are written as `null` if the Arduino is not connected — the pipeline keeps running regardless
- The IMU heading field is always `null` in this iteration — no compass fitted yet
