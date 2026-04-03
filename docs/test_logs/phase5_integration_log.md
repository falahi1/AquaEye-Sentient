# Phase 5 Test Log — End-to-End Integration Test

**Date:** ___________
**Tester:** Fazley Alahi
**Pi hostname / IP:** _____
**Arduino connected:** Yes / No
**Wi-Fi hotspot:** Yes / No
**SD cards:** 3× HydroMoth (Phase 2 recordings loaded)

---

## Test 5.1 — SD Card Pull to FLAC

| Check | Pass | Notes |
|-------|------|-------|
| All 3 HydroMoth SD cards pulled without error | | |
| Session stitcher grouped all 3 units into same session | | |
| FLAC file produced for each of the 3 channels | | |
| JSON sidecar written for each FLAC | | |
| JSON contains correct `hydromoth_id` field | | |
| JSON contains correct `sample_rate` field | | |
| JSON contains valid `session_id` (shared across 3 files) | | |

**Overall: PASS / FAIL**

---

## Test 5.2 — Serial Integration (Arduino)

| Check | Pass | Notes |
|-------|------|-------|
| Serial reader daemon starts without error | | |
| GPS reading present in JSON sidecar | | |
| TDS reading present in JSON sidecar | | |
| Turbidity reading present in JSON sidecar | | |

**Overall: PASS / FAIL**

---

## Test 5.3 — Cloud Upload (Google Drive)

| Check | Pass | Notes |
|-------|------|-------|
| Wi-Fi detected before upload attempt | | |
| FLAC files appear in Google Drive folder | | |
| JSON sidecar files appear alongside FLAC files | | |
| No orphaned FLAC files without a matching JSON | | |

**Overall: PASS / FAIL**

---

## Test 5.4 — Resilience Check

| Failure injected | Expected behaviour | Actual behaviour | Pass |
|-----------------|-------------------|-----------------|------|
| One SD card removed mid-pull | Other 2 cards process normally; error logged for missing card | | |
| Arduino disconnected mid-cycle | Pipeline continues; sensor fields null in JSON | | |
| Wi-Fi disabled before upload attempt | Upload step skipped gracefully; FLAC/JSON retained locally | | |

**Overall: PASS / FAIL**

---

## Known Failures / Limitations

_List any tests that failed and the suspected cause._

---

## Notes
