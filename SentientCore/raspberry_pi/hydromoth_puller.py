# =============================================================================
# AquaEye-Sentient — hydromoth_puller.py
# =============================================================================
# Copies new WAV files from each HydroMoth SD card to a local staging folder
# on the Pi, then deletes the original from the SD card.
#
# WHY DELETE FROM THE SD CARD
# ---------------------------
# HydroMoth SD cards have limited storage. Once a file is safely on the Pi,
# keeping it on the SD card wastes space and prevents the HydroMoth from
# recording new audio. Deleting after a verified copy keeps the SD card clear
# for the next deployment period.
#
# SAFETY GUARANTEE
# ----------------
# The original on the SD card is NEVER deleted until:
#   1. The copy exists in STAGING_FOLDER
#   2. The copied file size matches the source file size exactly
# If either check fails, the source is kept and an error is logged.
# A partial copy left in staging is removed before retrying.
#
# STAGING FILENAME FORMAT
# -----------------------
# Files are renamed on copy to include the HydroMoth ID:
#   Source:  /media/pi/HYDROMOTH_A/20250325_120000.WAV
#   Staged:  /home/pi/aquaeye/staging/HM_A__20250325_120000.WAV
#
# The double underscore (__) separates the HydroMoth ID from the original
# filename, making it easy to parse back out in session_stitcher.py.
#
# KEY FUNCTION
# ------------
#   pull_all()
#     Scans all three SD card mounts, copies new WAV files to staging,
#     deletes verified originals. Returns a summary dict.
# =============================================================================

import os
import shutil
import logging

from config import HYDROMOTHS, STAGING_FOLDER

logger = logging.getLogger(__name__)

# Separator between HydroMoth ID and original filename in staged name.
# Must not appear in HydroMoth IDs or in HydroMoth filenames.
ID_SEP = "__"


def _staged_name(hydromoth_id: str, original_filename: str) -> str:
    """
    Build the staged filename for a given source file.

    Example:
        _staged_name("HM_A", "20250325_120000.WAV")
        → "HM_A__20250325_120000.WAV"
    """
    return f"{hydromoth_id}{ID_SEP}{original_filename}"


def _verify_copy(src: str, dst: str) -> bool:
    """
    Return True if dst exists and its size matches src exactly.
    Size comparison is the minimum integrity check — catches truncated copies.
    """
    if not os.path.exists(dst):
        return False
    return os.path.getsize(dst) == os.path.getsize(src)


def pull_all() -> dict:
    """
    Pull all new WAV files from every mounted HydroMoth SD card into staging.

    For each HydroMoth:
      - Skips if SD card is not mounted
      - Skips files already in staging (by staged filename)
      - Copies each new WAV to STAGING_FOLDER with prefixed name
      - Verifies the copy, then deletes the source from the SD card
      - On verification failure: removes the partial copy, keeps the source

    Returns
    -------
    dict with keys:
        pulled   (int) — number of files successfully copied and deleted
        skipped  (int) — files already in staging (previously pulled)
        failed   (int) — files where copy or verification failed
        errors   (list of str) — one message per failure
    """
    os.makedirs(STAGING_FOLDER, exist_ok=True)

    # Build set of filenames already in staging for fast lookup
    already_staged = set(os.listdir(STAGING_FOLDER))

    summary = {"pulled": 0, "skipped": 0, "failed": 0, "errors": []}

    for hm in HYDROMOTHS:
        hm_id = hm["id"]
        mount = hm["sd_mount"]

        if not os.path.isdir(mount):
            logger.debug(f"{hm_id}: SD card not mounted at {mount} — skipping")
            continue

        wav_files = sorted(
            f for f in os.listdir(mount) if f.upper().endswith(".WAV")
        )

        if not wav_files:
            logger.debug(f"{hm_id}: no WAV files on SD card")
            continue

        logger.info(f"{hm_id}: found {len(wav_files)} WAV file(s) on SD card")

        for fname in wav_files:
            staged_fname = _staged_name(hm_id, fname)

            # Already in staging — skip copy, but still delete from SD if
            # we somehow failed to delete it last time
            if staged_fname in already_staged:
                src = os.path.join(mount, fname)
                if _verify_copy(src, os.path.join(STAGING_FOLDER, staged_fname)):
                    try:
                        os.remove(src)
                        logger.debug(f"{hm_id}: late-deleted {fname} from SD (was already staged)")
                    except OSError as e:
                        logger.warning(f"{hm_id}: could not late-delete {fname}: {e}")
                summary["skipped"] += 1
                continue

            src = os.path.join(mount, fname)
            dst = os.path.join(STAGING_FOLDER, staged_fname)

            # --- Copy ---
            try:
                shutil.copy2(src, dst)
            except Exception as e:
                msg = f"{hm_id}/{fname}: copy failed — {e}"
                logger.error(msg)
                summary["failed"] += 1
                summary["errors"].append(msg)
                # Remove partial copy if it was created
                if os.path.exists(dst):
                    try:
                        os.remove(dst)
                    except OSError:
                        pass
                continue

            # --- Verify ---
            if not _verify_copy(src, dst):
                msg = (
                    f"{hm_id}/{fname}: size mismatch after copy "
                    f"(src={os.path.getsize(src)}, "
                    f"dst={os.path.getsize(dst)}) — keeping source"
                )
                logger.error(msg)
                summary["failed"] += 1
                summary["errors"].append(msg)
                try:
                    os.remove(dst)
                except OSError:
                    pass
                continue

            # --- Delete source ---
            try:
                os.remove(src)
            except OSError as e:
                # Copy is safe but we couldn't delete the source.
                # Log it — the file will be detected as "already staged"
                # on the next pull and deletion retried then.
                logger.warning(f"{hm_id}: copied {fname} but could not delete source: {e}")

            logger.info(f"{hm_id}: pulled {fname} → {staged_fname}")
            summary["pulled"] += 1
            already_staged.add(staged_fname)

    logger.info(
        f"Pull complete — pulled: {summary['pulled']}, "
        f"skipped: {summary['skipped']}, failed: {summary['failed']}"
    )
    return summary
