# AquaEye-Sentient

**Student:** Fazley Alahi (1934714)
**Degree:** BEng Aerospace Engineering
**Institution:** Brunel University London, Department of Mechanical & Aerospace Engineering
**Module:** ME3620 Major Individual Project
**Academic Year:** 2025-26

---

## Overview

AquaEye-Sentient is the third cycle of the AquaEye project series — a low-cost, autonomous acoustic buoy system for detecting marine mammal vocalisations in the East Aegean Sea and Mediterranean coastal waters.

The system deploys **HydroMoth hydrophone recorders** on floating buoys to passively record underwater sound. Recordings are compressed, tagged with GPS and water quality metadata, and uploaded to cloud storage when Wi-Fi is available.

This cycle's primary contribution is the first integration of a real underwater acoustic subsystem into the platform. Previous cycles developed the ML classifier and recording pipeline using existing datasets; this cycle integrates, characterises, and deploys HydroMoth hydrophones for the first time.

---

## Repository Structure

```
AquaEye-Sentient/
├── SentientCore/                   ← Active code for this cycle
│   ├── raspberry_pi/               ← Python pipeline (8 modules)
│   │   ├── main.py                 ← Entry point — orchestrates the full pipeline
│   │   ├── hydromoth_puller.py     ← Copies WAV files from HydroMoth SD cards
│   │   ├── session_stitcher.py     ← Groups files from all 3 units by timestamp
│   │   ├── audio_processor.py      ← WAV → FLAC compression; multi-channel mix
│   │   ├── metadata_writer.py      ← Writes _meta.json sidecar per recording
│   │   ├── serial_reader.py        ← Reads Arduino sensor data over serial
│   │   ├── hub_controller.py       ← USB hub power control via uhubctl
│   │   ├── cloud_uploader.py       ← Uploads FLAC + metadata to Google Drive
│   │   ├── config.py               ← All tunable parameters in one place
│   │   └── README.md               ← Full pipeline documentation
│   ├── arduino/
│   │   └── sensor_hub/
│   │       ├── sensor_hub.ino      ← Arduino sketch: TDS, turbidity, GPS
│   │       └── README.md           ← Wiring, libraries, serial format
│   ├── tests/
│   │   ├── pipeline_benchmark.py   ← Performance and timing benchmark suite
│   │   ├── test_mixing.py          ← Unit tests for session mixing functions
│   │   ├── conftest.py             ← pytest path setup
│   │   └── README.md
│   ├── ARCHITECTURE.md             ← Design decisions and module responsibilities
│   └── CHANGELOG.md                ← Version history
│
├── tools/
│   ├── generate_test_audio.py      ← Generates synthetic HydroMoth WAV files for testing
│   └── tests/
│       └── test_generate_test_audio.py
│
├── analysis/
│   ├── run_power_validation.py     ← Compares D.2 modelled vs measured power values
│   └── power_budget/               ← Power budget calculation modules
│
├── docs/
│   └── test_logs/
│       ├── phase4_power_log.md     ← Power measurement results (2026-04-12)
│       └── ...
│
├── Inherited_Codes/                ← Unmodified code from previous cycles
│   ├── AquaEye_2023-24_Andia/      ← ML classifiers (RFC, GBM, kNN) — 83% accuracy
│   ├── AquaSound_2024-25_Victory/  ← Recording pipeline + Arduino sensor hub
│   └── README.md                   ← Attribution and description of each file
│
└── .gitignore
```

---

## Hardware

| Component | Role |
|-----------|------|
| HydroMoth × 3 | Underwater acoustic recorders (up to 384 kHz) |
| Raspberry Pi 4 / 5 | Central processing, pipeline orchestration |
| Arduino Nano / Uno | Environmental sensor hub |
| NEO-6M GPS | Position and timestamp |
| TDS sensor | Water conductivity (A1) |
| Turbidity sensor | Water clarity (A0) |
| Solar panel + Li-ion | Power subsystem |

---

## Getting Started

See [`SentientCore/raspberry_pi/README.md`](SentientCore/raspberry_pi/README.md) for full setup and deployment instructions.

See [`SentientCore/arduino/sensor_hub/README.md`](SentientCore/arduino/sensor_hub/README.md) for Arduino wiring and library setup.

---

## Project Lineage

| Cycle | Student | Key Contribution |
|-------|---------|-----------------|
| AquaEye (2023-24) | Andia Roumina | ML species classifier — 83% accuracy on 3 dolphin species |
| AquaSound (2024-25) | Victory Anyalewechi + team | Raspberry Pi + Arduino platform, FLAC pipeline, cloud upload |
| **AquaEye-Sentient (2025-26)** | **Fazley Alahi** | **HydroMoth integration, multi-hydrophone pipeline, metadata system** |

Code from previous cycles is preserved unmodified in `Inherited_Codes/` with full attribution.

---

## Target Species

| Species | Vocalisation | Frequency Range |
|---------|--------------|-----------------|
| Common Dolphin (*Delphinus delphis*) | Whistles, clicks | 2–20 kHz |
| Bottlenose Dolphin (*Tursiops truncatus*) | Whistles, echolocation | 2–130 kHz |
| Striped Dolphin (*Stenella coeruleoalba*) | Whistles, clicks | 6–20 kHz |
