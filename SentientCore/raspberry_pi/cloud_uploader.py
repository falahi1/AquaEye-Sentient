# =============================================================================
# AquaEye-Sentient — cloud_uploader.py
# =============================================================================
# Uploads completed FLAC files and their _meta.json sidecars to Google Drive.
#
# Ported from AquaSound (2024-25) — Victory Anyalewechi's main_recording.py.
# Three issues fixed from the AquaSound version:
#
#   1. Token storage: AquaSound used pickle (token.pickle) which is outdated.
#      Google's own library now uses JSON (token.json). Switched to JSON so
#      the token file is human-readable and compatible with current library.
#
#   2. Sidecars: AquaSound only uploaded .flac files. Each FLAC now has a
#      _meta.json sidecar that must be uploaded alongside it so the two files
#      stay linked in Drive.
#
#   3. Mimetype: AquaSound hardcoded 'audio/flac' for all uploads. JSON files
#      now use 'application/json'.
#
# HOW GOOGLE DRIVE AUTH WORKS (first-time setup)
# -----------------------------------------------
# 1. First run opens a browser window for OAuth2 sign-in (or prints a URL
#    if the Pi has no display — use SSH port forwarding or run setup on a
#    desktop first).
# 2. After sign-in, a token.json is saved at TOKEN_FILE (config.py).
# 3. All future runs load token.json silently — no browser needed.
# 4. If the token expires, the library refreshes it automatically using the
#    refresh token stored inside token.json.
#
# CREDENTIALS FILE
# ----------------
# credentials.json must be present at CREDENTIALS_FILE (config.py) before
# first use. Download it from Google Cloud Console → APIs & Services →
# OAuth 2.0 Client IDs → Download JSON.
# See Victory's report (Section 7) for the full setup walkthrough.
#
# KEY FUNCTION
# ------------
#   upload_pending()
#     Uploads all .flac files in FLAC_FOLDER plus their _meta.json sidecars.
#     Moves successfully uploaded files to UPLOADED_FOLDER.
#     Skips upload entirely if no internet connection is detected.
# =============================================================================

import logging
import os

import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import (
    FLAC_FOLDER, UPLOADED_FOLDER,
    GOOGLE_DRIVE_FOLDER_ID, CREDENTIALS_FILE, TOKEN_FILE,
)

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _authenticate():
    """
    Load or create OAuth2 credentials for Google Drive.

    - If TOKEN_FILE exists and is valid: loads it silently.
    - If the access token is expired but a refresh token exists: refreshes automatically.
    - If no token exists: opens OAuth2 browser flow to sign in and saves token.json.

    Returns a Google API service object for Drive v3.
    """
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Google Drive token ...")
            creds.refresh(Request())
        else:
            logger.info("No valid token found — starting OAuth2 flow ...")
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_FILE}. "
                    "Download it from Google Cloud Console and place it there."
                )
            flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the token for next run
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        logger.info(f"Token saved to {TOKEN_FILE}")

    return build("drive", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Connectivity check
# ---------------------------------------------------------------------------

def _is_connected() -> bool:
    """Return True if the Pi can reach the internet (Google's servers)."""
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except requests.ConnectionError:
        return False


# ---------------------------------------------------------------------------
# Single file upload
# ---------------------------------------------------------------------------

def _upload_file(service, file_path: str) -> bool:
    """
    Upload one file to Google Drive into GOOGLE_DRIVE_FOLDER_ID.

    Returns True on success, False on failure.
    Determines mimetype from file extension:
      .flac → audio/flac
      .json → application/json
      anything else → application/octet-stream
    """
    ext = os.path.splitext(file_path)[1].lower()
    mimetypes = {
        ".flac": "audio/flac",
        ".json": "application/json",
    }
    mimetype = mimetypes.get(ext, "application/octet-stream")

    file_name     = os.path.basename(file_path)
    file_metadata = {
        "name":    file_name,
        "parents": [GOOGLE_DRIVE_FOLDER_ID],
    }

    try:
        media = MediaFileUpload(file_path, mimetype=mimetype, resumable=True)
        result = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )
        logger.info(f"Uploaded {file_name} (Drive ID: {result.get('id')})")
        return True
    except Exception as e:
        logger.error(f"Failed to upload {file_name}: {e}")
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_pending() -> dict:
    """
    Upload all pending FLAC files and their _meta.json sidecars from
    FLAC_FOLDER to Google Drive, then move them to UPLOADED_FOLDER.

    A FLAC and its sidecar are uploaded as a pair — if the FLAC upload
    fails, the sidecar is not moved either (so both retry together next time).

    Skips entirely if no internet connection is detected.

    Returns
    -------
    dict with keys:
        uploaded  (int) — number of FLAC files successfully uploaded
        skipped   (int) — files skipped (no connection, or no files)
        failed    (int) — FLAC files that failed to upload
    """
    summary = {"uploaded": 0, "skipped": 0, "failed": 0}

    if not _is_connected():
        logger.info("No internet connection — upload skipped")
        summary["skipped"] = len(
            [f for f in os.listdir(FLAC_FOLDER) if f.endswith(".flac")]
        )
        return summary

    try:
        service = _authenticate()
    except Exception as e:
        logger.error(f"Google Drive authentication failed: {e}")
        return summary

    os.makedirs(UPLOADED_FOLDER, exist_ok=True)

    flac_files = sorted(
        f for f in os.listdir(FLAC_FOLDER) if f.endswith(".flac")
    )

    if not flac_files:
        logger.debug("No FLAC files pending upload")
        return summary

    for flac_name in flac_files:
        flac_path = os.path.join(FLAC_FOLDER, flac_name)
        stem      = os.path.splitext(flac_name)[0]
        meta_name = stem + "_meta.json"
        meta_path = os.path.join(FLAC_FOLDER, meta_name)

        # Upload FLAC
        flac_ok = _upload_file(service, flac_path)

        if not flac_ok:
            summary["failed"] += 1
            continue

        # Upload sidecar if it exists
        if os.path.exists(meta_path):
            _upload_file(service, meta_path)
            # Sidecar failure is logged but does not block moving the FLAC

        # Move both to UPLOADED_FOLDER
        try:
            os.rename(flac_path, os.path.join(UPLOADED_FOLDER, flac_name))
            if os.path.exists(meta_path):
                os.rename(meta_path, os.path.join(UPLOADED_FOLDER, meta_name))
        except OSError as e:
            logger.warning(f"Could not move {flac_name} to uploaded folder: {e}")

        summary["uploaded"] += 1

    logger.info(
        f"Upload complete — uploaded: {summary['uploaded']}, "
        f"failed: {summary['failed']}"
    )
    return summary
