# Session Mixing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mix the 3 simultaneous HydroMoth WAV files from each session into a single omnidirectional FLAC, replacing the current per-file encode.

**Architecture:** Add `mix_session_to_flac()` to `audio_processor.py` — loads all WAV files as float64 arrays, sums them, normalises to [-1, 1], writes a temp WAV, then calls the flac CLI. Update `metadata_writer.py` with a new `write_mixed_metadata()` that records all contributing units. Update `main.py` and `pipeline_benchmark.py` to call the mix function once per session instead of encoding per file.

**Tech Stack:** Python 3, soundfile (numpy array I/O), flac CLI (encoding), existing pipeline stack.

---

## File Map

| Action | Path | Change |
|--------|------|--------|
| Modify | `SentientCore/raspberry_pi/audio_processor.py` | Add `mix_session_to_flac()` |
| Modify | `SentientCore/raspberry_pi/metadata_writer.py` | Add `write_mixed_metadata()` |
| Modify | `SentientCore/raspberry_pi/main.py` | Call mix function per session |
| Modify | `SentientCore/tests/pipeline_benchmark.py` | Call mix function per session |
| Create | `SentientCore/tests/test_mixing.py` | Unit tests for mix functions |

---

## Task 1: Failing tests for mix_session_to_flac

**Files:**
- Create: `SentientCore/tests/test_mixing.py`

- [ ] **Step 1: Create test file**

Create `SentientCore/tests/test_mixing.py`:

```python
import numpy as np
import os
import pytest
import soundfile as sf
import tempfile


SAMPLE_RATE = 96000
DURATION_SEC = 2
N_SAMPLES = SAMPLE_RATE * DURATION_SEC


def _write_wav(path: str, data: np.ndarray, sr: int = SAMPLE_RATE):
    sf.write(path, data.astype(np.int16), sr, subtype="PCM_16")


def test_mix_produces_single_flac(tmp_path):
    from audio_processor import mix_session_to_flac
    wav_paths = []
    for i in range(3):
        data = (np.random.default_rng(i).standard_normal(N_SAMPLES) * 10000).astype(np.int16)
        p = str(tmp_path / f"HM_{i}.WAV")
        _write_wav(p, data)
        wav_paths.append(p)
    flac_path = str(tmp_path / "MIXED__20260401_120000.flac")
    result = mix_session_to_flac(wav_paths, flac_path)
    assert result["success"] is True
    assert os.path.exists(flac_path)


def test_mix_result_has_expected_keys(tmp_path):
    from audio_processor import mix_session_to_flac
    wav_paths = []
    for i in range(3):
        data = (np.random.default_rng(i).standard_normal(N_SAMPLES) * 10000).astype(np.int16)
        p = str(tmp_path / f"HM_{i}.WAV")
        _write_wav(p, data)
        wav_paths.append(p)
    flac_path = str(tmp_path / "MIXED.flac")
    result = mix_session_to_flac(wav_paths, flac_path)
    for key in ("success", "duration_sec", "flac_bytes", "encode_sec", "error"):
        assert key in result


def test_mix_output_duration_matches_input(tmp_path):
    from audio_processor import mix_session_to_flac
    wav_paths = []
    for i in range(3):
        data = (np.random.default_rng(i).standard_normal(N_SAMPLES) * 10000).astype(np.int16)
        p = str(tmp_path / f"HM_{i}.WAV")
        _write_wav(p, data)
        wav_paths.append(p)
    flac_path = str(tmp_path / "MIXED.flac")
    result = mix_session_to_flac(wav_paths, flac_path)
    assert result["success"] is True
    assert abs(result["duration_sec"] - DURATION_SEC) < 0.1


def test_mix_single_file_falls_back_to_convert(tmp_path):
    from audio_processor import mix_session_to_flac
    data = (np.random.default_rng(0).standard_normal(N_SAMPLES) * 10000).astype(np.int16)
    p = str(tmp_path / "HM_A.WAV")
    _write_wav(p, data)
    flac_path = str(tmp_path / "MIXED.flac")
    result = mix_session_to_flac([p], flac_path)
    assert result["success"] is True
    assert os.path.exists(flac_path)


def test_mix_truncates_to_shortest_file(tmp_path):
    from audio_processor import mix_session_to_flac
    wav_paths = []
    lengths = [N_SAMPLES, N_SAMPLES + 1000, N_SAMPLES - 500]
    for i, n in enumerate(lengths):
        data = (np.random.default_rng(i).standard_normal(n) * 10000).astype(np.int16)
        p = str(tmp_path / f"HM_{i}.WAV")
        _write_wav(p, data)
        wav_paths.append(p)
    flac_path = str(tmp_path / "MIXED.flac")
    result = mix_session_to_flac(wav_paths, flac_path)
    assert result["success"] is True
    info = sf.info(flac_path)
    assert info.frames == min(lengths)


def test_mix_normalises_output(tmp_path):
    from audio_processor import mix_session_to_flac
    # Three identical loud signals — sum would clip without normalisation
    wav_paths = []
    data = np.full(N_SAMPLES, 30000, dtype=np.int16)
    for i in range(3):
        p = str(tmp_path / f"HM_{i}.WAV")
        _write_wav(p, data)
        wav_paths.append(p)
    flac_path = str(tmp_path / "MIXED.flac")
    mix_session_to_flac(wav_paths, flac_path)
    mixed, _ = sf.read(flac_path, dtype="float64")
    assert np.max(np.abs(mixed)) <= 1.0 + 1e-6
```

- [ ] **Step 2: Run tests — expect all 6 to fail**

```bash
cd C:\Users\alahi\Desktop\AquaEye-Sentient
pytest SentientCore/tests/test_mixing.py -v
```

Expected: All 6 fail with `ModuleNotFoundError: No module named 'audio_processor'` or `ImportError: cannot import name 'mix_session_to_flac'`.

- [ ] **Step 3: Commit failing tests**

```bash
git add SentientCore/tests/test_mixing.py
git commit -m "test: add failing tests for mix_session_to_flac"
```

---

## Task 2: Implement mix_session_to_flac in audio_processor.py

**Files:**
- Modify: `SentientCore/raspberry_pi/audio_processor.py`

- [ ] **Step 1: Add numpy import and mix_session_to_flac function**

Add `import numpy as np` after the existing imports, then append the following function to `audio_processor.py`:

```python
import numpy as np  # add alongside existing imports at top of file
```

Append after the existing `convert_wav_to_flac` function:

```python

def mix_session_to_flac(wav_paths: list, flac_path: str,
                        compression_level: int = 4) -> dict:
    """
    Mix multiple simultaneous HydroMoth WAV files into one normalised FLAC.

    Algorithm: sum-then-normalise.
      1. Load each WAV as float64 (soundfile normalises int16 → [-1, 1]).
      2. Truncate all arrays to the shortest file length.
      3. Sum into a single float64 array.
      4. Normalise: divide by max(abs) if > 1.0 to prevent clipping.
      5. Convert to int16, write a temporary WAV.
      6. Encode the temp WAV to FLAC using the native CLI.
      7. Delete the temp WAV.

    Falls back to convert_wav_to_flac() when only one path is provided.

    Parameters
    ----------
    wav_paths         : list of absolute paths to WAV files for this session
                        (typically 3 — one per HydroMoth)
    flac_path         : output path for the mixed FLAC
    compression_level : FLAC compression level 0–8 (default 4)

    Returns
    -------
    Same dict schema as convert_wav_to_flac():
        success, duration_sec, flac_bytes, encode_sec, error
    """
    result = {
        "success":      False,
        "duration_sec": None,
        "flac_bytes":   None,
        "encode_sec":   None,
        "error":        None,
    }

    if len(wav_paths) == 1:
        return convert_wav_to_flac(wav_paths[0], flac_path, compression_level)

    try:
        # --- Load all channels -----------------------------------------------
        arrays = []
        sample_rate = None
        for p in wav_paths:
            data, sr = sf.read(p, dtype="float64", always_2d=False)
            if sample_rate is None:
                sample_rate = sr
            arrays.append(data)

        # --- Truncate to shortest length -------------------------------------
        min_len = min(len(a) for a in arrays)
        arrays  = [a[:min_len] for a in arrays]

        # --- Sum and normalise -----------------------------------------------
        mixed    = np.sum(arrays, axis=0)           # float64
        peak     = np.max(np.abs(mixed))
        if peak > 1.0:
            mixed = mixed / peak                    # scale to [-1, 1]

        # --- Write temp WAV (int16 PCM) --------------------------------------
        temp_wav = flac_path + ".tmp.wav"
        mixed_i16 = (mixed * 32767).astype(np.int16)
        sf.write(temp_wav, mixed_i16, sample_rate, subtype="PCM_16")

        result["duration_sec"] = min_len / sample_rate

        # --- Encode with FLAC CLI -------------------------------------------
        cmd = [
            "flac",
            f"-{compression_level}",
            "-f",
            "--silent",
            temp_wav,
            "-o", flac_path,
        ]

        t0 = time.perf_counter()
        subprocess.run(cmd, check=True)
        result["encode_sec"] = time.perf_counter() - t0

        result["flac_bytes"] = os.path.getsize(flac_path)
        result["success"]    = True

        logger.debug(
            f"Mixed {len(wav_paths)} files → {os.path.basename(flac_path)} "
            f"({result['flac_bytes'] // 1024} KB) in {result['encode_sec']:.2f} s"
        )

    except subprocess.CalledProcessError as e:
        result["error"] = f"flac CLI failed: {e}"
        logger.error(result["error"])
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"mix_session_to_flac failed: {e}")
    finally:
        # Always clean up temp WAV
        if "temp_wav" in dir() and os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except OSError:
                pass

    return result
```

- [ ] **Step 2: Add numpy import at top of file**

In `SentientCore/raspberry_pi/audio_processor.py`, the existing imports are:

```python
import os
import subprocess
import time
import logging
import soundfile as sf
```

Change to:

```python
import os
import subprocess
import time
import logging
import numpy as np
import soundfile as sf
```

- [ ] **Step 3: Run tests from project root**

```bash
cd C:\Users\alahi\Desktop\AquaEye-Sentient
pytest SentientCore/tests/test_mixing.py -v --tb=short
```

Expected: All 6 tests pass.

- [ ] **Step 4: Commit**

```bash
git add SentientCore/raspberry_pi/audio_processor.py
git commit -m "feat: add mix_session_to_flac — sum-normalise 3 HydroMoth WAVs into one FLAC"
```

---

## Task 3: Failing tests and implementation for write_mixed_metadata

**Files:**
- Modify: `SentientCore/tests/test_mixing.py` (append tests)
- Modify: `SentientCore/raspberry_pi/metadata_writer.py` (add function)

- [ ] **Step 1: Append metadata tests to test_mixing.py**

Append to `SentientCore/tests/test_mixing.py`:

```python

# ---------------------------------------------------------------------------
# write_mixed_metadata tests
# ---------------------------------------------------------------------------

def test_write_mixed_metadata_creates_json(tmp_path):
    from metadata_writer import write_mixed_metadata
    flac_path = str(tmp_path / "MIXED__20260401_120000.flac")
    open(flac_path, "w").close()   # empty placeholder
    units = [
        {"hydromoth_id": "HM_A", "angle_deg": 0,   "channel": 0},
        {"hydromoth_id": "HM_B", "angle_deg": 120,  "channel": 1},
        {"hydromoth_id": "HM_C", "angle_deg": 240,  "channel": 2},
    ]
    meta_path = write_mixed_metadata(
        flac_path=flac_path, units=units,
        session_id="20260401_120000", sample_rate=96000, sensor=None,
    )
    assert os.path.exists(meta_path)
    assert meta_path.endswith("_meta.json")


def test_write_mixed_metadata_schema(tmp_path):
    import json
    from metadata_writer import write_mixed_metadata
    flac_path = str(tmp_path / "MIXED__20260401_120000.flac")
    open(flac_path, "w").close()
    units = [
        {"hydromoth_id": "HM_A", "angle_deg": 0,   "channel": 0},
        {"hydromoth_id": "HM_B", "angle_deg": 120,  "channel": 1},
        {"hydromoth_id": "HM_C", "angle_deg": 240,  "channel": 2},
    ]
    meta_path = write_mixed_metadata(
        flac_path=flac_path, units=units,
        session_id="20260401_120000", sample_rate=96000, sensor=None,
    )
    with open(meta_path) as f:
        meta = json.load(f)
    assert meta["audio"]["mix_type"] == "sum_normalised"
    assert len(meta["audio"]["units"]) == 3
    assert meta["audio"]["units"][0]["hydromoth_id"] == "HM_A"
    assert meta["session_id"] == "20260401_120000"
    assert meta["audio"]["sample_rate"] == 96000
```

- [ ] **Step 2: Run new tests — expect them to fail**

```bash
pytest SentientCore/tests/test_mixing.py::test_write_mixed_metadata_creates_json SentientCore/tests/test_mixing.py::test_write_mixed_metadata_schema -v
```

Expected: FAIL with `ImportError: cannot import name 'write_mixed_metadata'`.

- [ ] **Step 3: Add write_mixed_metadata to metadata_writer.py**

Append after the existing `write_metadata` function in `SentientCore/raspberry_pi/metadata_writer.py`:

```python

def write_mixed_metadata(
    flac_path:  str,
    units:      list,
    sample_rate: int,
    session_id: str  = None,
    sensor:     dict | None = None,
) -> str:
    """
    Write a _meta.json sidecar for a mixed-session FLAC.

    Parameters
    ----------
    flac_path   : absolute path to the mixed .flac file
    units       : list of dicts, one per contributing HydroMoth:
                  [{"hydromoth_id": "HM_A", "angle_deg": 0, "channel": 0}, ...]
    sample_rate : Hz — as configured on the HydroMoth devices
    session_id  : shared session timestamp string (e.g. "20260401_120000")
    sensor      : dict from serial_reader.get_latest_reading(), or None

    Returns
    -------
    Path to the written _meta.json file.
    """
    s = sensor or {}

    meta = {
        "schema_version": "1.1",
        "written_utc":    datetime.now(timezone.utc).isoformat(),
        "session_id":     session_id,
        "audio": {
            "flac_file":  os.path.basename(flac_path),
            "mix_type":   "sum_normalised",
            "units":      units,
            "sample_rate": sample_rate,
        },
        "gps": {
            "lat":      s.get("gps_lat"),
            "lon":      s.get("gps_lon"),
            "alt_m":    s.get("gps_alt_m"),
            "date":     s.get("gps_date"),
            "time_utc": s.get("gps_time_utc"),
        },
        "water_quality": {
            "tds_ppm":     s.get("tds_ppm"),
            "tds_voltage": s.get("tds_voltage"),
            "turbidity_v": s.get("turbidity_v"),
            "temp_c":      s.get("temp_c"),
        },
        "orientation": {
            "heading_deg": s.get("heading_deg"),
        },
    }

    stem      = os.path.splitext(flac_path)[0]
    meta_path = stem + "_meta.json"
    temp_path = meta_path + ".tmp"

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, meta_path)
    except Exception as e:
        logger.error(f"Failed to write mixed metadata for {flac_path}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)

    logger.debug(f"Mixed metadata written → {os.path.basename(meta_path)}")
    return meta_path
```

- [ ] **Step 4: Run all mixing tests**

```bash
pytest SentientCore/tests/test_mixing.py -v
```

Expected: All 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add SentientCore/raspberry_pi/metadata_writer.py SentientCore/tests/test_mixing.py
git commit -m "feat: add write_mixed_metadata for mixed-session FLAC sidecar"
```

---

## Task 4: Update main.py to use mix function

**Files:**
- Modify: `SentientCore/raspberry_pi/main.py`

- [ ] **Step 1: Replace the per-file encode loop with per-session mix**

In `main.py`, find the `# Step 3 + 4: Encode + Metadata (per session, per file)` block (lines ~251–311) and replace it entirely with:

```python
    # ------------------------------------------------------------------
    # Step 3 + 4: Mix + Metadata (one FLAC per session)
    # ------------------------------------------------------------------
    sensor_data = serial_reader.get_latest_reading()

    for session in sessions:
        session_id = session["session_id"]

        if not session["complete"]:
            logger.warning(
                f"Session {session_id} is partial "
                f"({session['n_units']}/{len(HYDROMOTHS)} units) — mixing available units"
            )

        wav_paths = [f["wav_path"] for f in session["files"]]
        flac_path = os.path.join(FLAC_FOLDER, f"MIXED__{session_id}.flac")

        # Mix all units into one FLAC
        enc = audio_processor.mix_session_to_flac(wav_paths, flac_path)

        if not enc["success"]:
            msg = f"Mix failed for session {session_id}: {enc['error']}"
            logger.error(msg)
            summary["errors"].append(msg)
            summary["encode_errors"] += 1
            continue

        logger.info(
            f"Mixed session {session_id} → {os.path.basename(flac_path)} "
            f"({len(wav_paths)} units, {enc['flac_bytes'] // 1024} KB, "
            f"{enc['encode_sec']:.1f} s)"
        )

        # Metadata
        units = [
            {
                "hydromoth_id": f["hydromoth_id"],
                "angle_deg":    f["angle_deg"],
                "channel":      f["channel"],
            }
            for f in session["files"]
        ]
        try:
            metadata_writer.write_mixed_metadata(
                flac_path   = flac_path,
                units       = units,
                sample_rate = SAMPLE_RATE,
                session_id  = session_id,
                sensor      = sensor_data,
            )
        except Exception as e:
            logger.warning(f"Metadata write failed for session {session_id}: {e}")

        # Mark all contributing WAVs as processed
        try:
            with open(PROCESSED_LOG, "a", encoding="utf-8") as f:
                for wav_path in wav_paths:
                    f.write(wav_path + "\n")
        except OSError as e:
            logger.warning(f"Could not update processed log: {e}")

        summary["encoded"] += 1
```

- [ ] **Step 2: Verify the file still imports cleanly**

```bash
cd C:\Users\alahi\Desktop\AquaEye-Sentient\SentientCore\raspberry_pi
python -c "import main; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add SentientCore/raspberry_pi/main.py
git commit -m "feat: update main.py pipeline to mix session into single FLAC per session"
```

---

## Task 5: Update pipeline_benchmark.py to use mix function

**Files:**
- Modify: `SentientCore/tests/pipeline_benchmark.py`

- [ ] **Step 1: Replace per-file encode loop in run_cycle with per-session mix**

In `pipeline_benchmark.py`, find the `# -- Encode + Metadata (per session, per file)` block and replace it with:

```python
    # -- Mix + Metadata (one FLAC per session) --------------------------------
    encode_times   = []
    t_encode_total = 0.0
    t_metadata_total = 0.0

    for session in sessions:
        session_id = session["session_id"]
        wav_paths  = [f["wav_path"] for f in session["files"]]
        flac_path  = os.path.join(FLAC_FOLDER, f"MIXED__{session_id}_c{cycle_num:03d}.flac")

        print(f"  [{ts()}] Mix START: session {session_id} ({len(wav_paths)} files)")
        t0  = time.perf_counter()
        enc = audio_processor.mix_session_to_flac(wav_paths, flac_path)
        t_file = round(time.perf_counter() - t0, 2)
        t_encode_total += t_file
        print(f"  [{ts()}] Mix END:   session {session_id} — {t_file} s")

        if enc["success"]:
            encode_times.append(enc["encode_sec"])
            result["n_success"] += 1

            units = [
                {
                    "hydromoth_id": f["hydromoth_id"],
                    "angle_deg":    f["angle_deg"],
                    "channel":      f["channel"],
                }
                for f in session["files"]
            ]
            t0 = time.perf_counter()
            metadata_writer.write_mixed_metadata(
                flac_path   = flac_path,
                units       = units,
                sample_rate = SAMPLE_RATE,
                session_id  = session_id,
                sensor      = sensor_data,
            )
            t_metadata_total += time.perf_counter() - t0

        result["n_files"] += len(wav_paths)

        # Mark all WAVs processed
        with open(PROCESSED_LOG, "a") as f:
            for wav_path in wav_paths:
                f.write(wav_path + "\n")

    result["t_encode_s"]   = round(t_encode_total,   2)
    result["t_metadata_s"] = round(t_metadata_total, 2)
    result["t_total_s"]    = round(time.perf_counter() - cycle_start, 2)
    result["avg_per_file_s"] = round(
        sum(encode_times) / len(encode_times) if encode_times else 0.0, 2
    )
```

- [ ] **Step 2: Run all mixing tests to confirm nothing broke**

```bash
cd C:\Users\alahi\Desktop\AquaEye-Sentient
pytest SentientCore/tests/test_mixing.py -v
```

Expected: All 8 tests pass.

- [ ] **Step 3: Commit**

```bash
git add SentientCore/tests/pipeline_benchmark.py
git commit -m "feat: update pipeline_benchmark to mix sessions into single FLAC"
```

---

## Task 6: Transfer updated files to Pi and re-run benchmark

> Manual task — no code changes.

- [ ] **Step 1: SCP updated files to Pi (Windows CMD)**

```
scp C:\Users\alahi\Desktop\AquaEye-Sentient\SentientCore\raspberry_pi\audio_processor.py alf0081@172.20.10.2:/home/alf0081/aquaeye/raspberry_pi/
scp C:\Users\alahi\Desktop\AquaEye-Sentient\SentientCore\raspberry_pi\metadata_writer.py alf0081@172.20.10.2:/home/alf0081/aquaeye/raspberry_pi/
scp C:\Users\alahi\Desktop\AquaEye-Sentient\SentientCore\raspberry_pi\main.py alf0081@172.20.10.2:/home/alf0081/aquaeye/raspberry_pi/
scp C:\Users\alahi\Desktop\AquaEye-Sentient\SentientCore\tests\pipeline_benchmark.py alf0081@172.20.10.2:/home/alf0081/aquaeye/raspberry_pi/
```

- [ ] **Step 2: Reboot Pi**

```bash
ssh alf0081@172.20.10.2
sudo reboot
```

- [ ] **Step 3: Wait ~5 minutes, SSH back in and check log**

```bash
ssh alf0081@172.20.10.2
cat /home/alf0081/benchmark_*.txt | tail -60
```

Expected: Log shows `Mix START/END` instead of `Encode START/END`. Each session produces one `MIXED__<session_id>.flac`.

- [ ] **Step 4: Verify FLAC files created**

```bash
ls /home/alf0081/aquaeye/flac_files/
```

Expected: 3 files named `MIXED__20260401_120000_c001.flac`, `MIXED__20260401_121000_c001.flac`, `MIXED__20260401_122000_c001.flac` (plus `_meta.json` sidecars).
