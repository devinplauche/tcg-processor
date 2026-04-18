"""Google Drive -> LangChain scan -> Flask inventory ingestion pipeline."""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import time

import pandas as pd
import requests

from services.manabox import import_csv

DEFAULT_DRIVE_FOLDER_URL = os.getenv("GOOGLE_DRIVE_TARGET_FOLDER_URL")
DEFAULT_MIN_CONFIDENCE = float(os.getenv("LANGCHAIN_MIN_CONFIDENCE", "0.90"))


class GoogleDriveIntegrationError(RuntimeError):
    """Raised when Google Drive or scanner integration fails validation."""


@dataclass
class ScanOutcome:
    card_name: str
    set_code: str
    set_name: str
    rarity: str
    confidence: float
    status: str = "success"


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Best-effort float conversion with a safe default for malformed values."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def extract_drive_folder_id(folder_url_or_id: str) -> str:
    """Extract a Google Drive folder ID from either a URL or raw ID."""
    value = (folder_url_or_id or "").strip()
    if not value:
        raise GoogleDriveIntegrationError("Google Drive folder URL or ID is required")

    url_match = re.search(r"/folders/([a-zA-Z0-9_-]+)", value)
    if url_match:
        return url_match.group(1)

    id_match = re.fullmatch(r"[a-zA-Z0-9_-]{10,}", value)
    if id_match:
        return value

    raise GoogleDriveIntegrationError("Invalid Google Drive folder URL/ID")


class GoogleDriveClient:
    """Minimal Google Drive API client for upload and download operations."""

    def __init__(self, credentials_json_path: str | None = None) -> None:
        self.credentials_json_path = credentials_json_path or os.getenv("GOOGLE_DRIVE_CREDENTIALS_JSON")
        self._service = None

    def _service_client(self):
        if self._service is not None:
            return self._service
        if not self.credentials_json_path:
            raise GoogleDriveIntegrationError(
                "GOOGLE_DRIVE_CREDENTIALS_JSON is not set. Provide a service account credentials file path."
            )

        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import credentials as oauth_credentials
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from google_auth_oauthlib.flow import InstalledAppFlow
        except Exception as exc:  # pragma: no cover - import error path depends on environment
            raise GoogleDriveIntegrationError(
                "Google Drive dependencies missing. Install google-api-python-client and google-auth."
            ) from exc

        scopes = ["https://www.googleapis.com/auth/drive"]
        credentials_path = Path(self.credentials_json_path)
        if not credentials_path.exists():
            raise GoogleDriveIntegrationError(
                f"Google Drive credentials file does not exist: {credentials_path}"
            )

        try:
            credentials_payload = json.loads(credentials_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise GoogleDriveIntegrationError("Unable to parse Google Drive credentials JSON") from exc

        token_path = Path(
            os.getenv(
                "GOOGLE_DRIVE_TOKEN_JSON",
                str(credentials_path.with_name("google_drive_token.json")),
            )
        )

        if credentials_payload.get("type") == "service_account":
            credentials = service_account.Credentials.from_service_account_file(
                str(credentials_path),
                scopes=scopes,
            )
        elif "installed" in credentials_payload or "web" in credentials_payload:
            credentials = None
            if token_path.exists():
                credentials = oauth_credentials.Credentials.from_authorized_user_file(
                    str(token_path),
                    scopes=scopes,
                )

            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())

            if not credentials or not credentials.valid:
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes=scopes)
                oauth_mode = os.getenv("GOOGLE_DRIVE_OAUTH_MODE", "local_server").strip().lower()
                if oauth_mode == "console":
                    credentials = flow.run_console()
                else:
                    oauth_port = int(os.getenv("GOOGLE_DRIVE_OAUTH_PORT", "0"))
                    credentials = flow.run_local_server(port=oauth_port)

                token_path.parent.mkdir(parents=True, exist_ok=True)
                token_path.write_text(credentials.to_json(), encoding="utf-8")
        else:
            raise GoogleDriveIntegrationError(
                "Unsupported Google Drive credentials JSON format. Use service_account or installed OAuth client JSON."
            )

        self._service = build("drive", "v3", credentials=credentials)
        return self._service

    def upload_file_bytes(self, file_bytes: bytes, filename: str, folder_id: str) -> dict[str, Any]:
        if not file_bytes:
            raise GoogleDriveIntegrationError("Uploaded file is empty")

        service = self._service_client()
        try:
            from googleapiclient.http import MediaIoBaseUpload
        except Exception as exc:  # pragma: no cover
            raise GoogleDriveIntegrationError("Google Drive upload transport dependency is unavailable") from exc

        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype="image/jpeg", resumable=False)
        metadata = {"name": filename, "parents": [folder_id]}

        created = (
            service.files()
            .create(body=metadata, media_body=media, fields="id,name,webViewLink")
            .execute()
        )
        return created

    def download_file_bytes(self, file_id: str) -> bytes:
        service = self._service_client()
        try:
            from googleapiclient.http import MediaIoBaseDownload
        except Exception as exc:  # pragma: no cover
            raise GoogleDriveIntegrationError("Google Drive download transport dependency is unavailable") from exc

        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        return fh.getvalue()


class LangChainScannerClient:
    """Thin client over a LangChain scanner HTTP endpoint."""

    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint or os.getenv("LANGCHAIN_SCANNER_ENDPOINT")
        self.scanner_script_path = os.getenv(
            "LANGCHAIN_SCANNER_SCRIPT_PATH",
            str(
                Path(__file__).resolve().parents[3]
                / "backend"
                / "compute"
                / "langchain"
                / "langchain_scan_cards.py"
            ),
        )

    def scan_image_bytes(self, image_bytes: bytes, filename: str) -> dict[str, Any]:
        if not self.endpoint:
            return self._scan_locally_via_script(image_bytes=image_bytes, filename=filename)

        response = requests.post(
            self.endpoint,
            files={"file": (filename, image_bytes, "image/jpeg")},
            timeout=120,
        )
        if not response.ok:
            raise GoogleDriveIntegrationError(
                f"LangChain scanner request failed: {response.status_code}"
            )

        payload = response.json() or {}
        return payload

    def _scan_locally_via_script(self, *, image_bytes: bytes, filename: str) -> dict[str, Any]:
        script_path = Path(self.scanner_script_path)
        if not script_path.exists():
            raise GoogleDriveIntegrationError(
                "LANGCHAIN_SCANNER_ENDPOINT is not configured and local scanner script was not found"
            )

        with tempfile.TemporaryDirectory(prefix="live_scan_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            image_path = tmp_path / filename
            output_csv = tmp_path / "scan_output.csv"
            image_path.write_bytes(image_bytes)

            cmd = [
                os.getenv("PYTHON_EXECUTABLE", "python"),
                str(script_path),
                "--input-dir",
                str(tmp_path),
                "--output-csv",
                str(output_csv),
                "--limit",
                "1",
                "--no-resume",
            ]
            process_env = dict(os.environ)
            process_env.setdefault("PYTHONUTF8", "1")
            process_env.setdefault("PYTHONIOENCODING", "utf-8")
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
                env=process_env,
            )
            if proc.returncode != 0:
                raise GoogleDriveIntegrationError(
                    f"Local LangChain scanner failed with code {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
                )
            if not output_csv.exists():
                raise GoogleDriveIntegrationError("Local LangChain scanner did not produce output CSV")

            scan_df = pd.read_csv(output_csv)
            if scan_df.empty:
                details = (proc.stderr or proc.stdout or "").strip()
                if details:
                    raise GoogleDriveIntegrationError(f"Local LangChain scanner output is empty: {details}")
                raise GoogleDriveIntegrationError("Local LangChain scanner output is empty")

            row = scan_df.iloc[0].to_dict()
            return {
                "status": str(row.get("status") or "").lower() or "error",
                "card_name": row.get("card_name"),
                "set_code": row.get("set_code"),
                "set_name": row.get("set_name"),
                "colors": row.get("colors"),
                "mana_cost": row.get("mana_cost"),
                "type_line": row.get("type_line"),
                "rarity": row.get("rarity"),
                "power_toughness": row.get("power_toughness"),
                "confidence": float(row.get("confidence") or 0.0),
                "error": row.get("error"),
                "timestamp": row.get("timestamp"),
            }


def _build_scanner_dataframe(scan_payload: dict[str, Any], filename: str) -> pd.DataFrame:
    rarity = str(scan_payload.get("rarity") or "").strip()
    if not rarity:
        raise GoogleDriveIntegrationError("Scanner payload missing required 'rarity' value")

    return pd.DataFrame(
        [
            {
                "filename": filename,
                "card_name": scan_payload.get("card_name"),
                "set_name": scan_payload.get("set_name", ""),
                "set_code": scan_payload.get("set_code", ""),
                "colors": scan_payload.get("colors", ""),
                "mana_cost": scan_payload.get("mana_cost", ""),
                "type_line": scan_payload.get("type_line", ""),
                "rarity": rarity,
                "power_toughness": scan_payload.get("power_toughness", ""),
                "confidence": _safe_float(scan_payload.get("confidence"), 0.0),
                "status": scan_payload.get("status", "success"),
                "error": scan_payload.get("error", ""),
                "timestamp": scan_payload.get("timestamp", ""),
            }
        ]
    )


def ingest_drive_upload_scan_and_import(
    db,
    *,
    file_bytes: bytes,
    filename: str,
    folder_url_or_id: str | None = None,
    min_confidence: float | None = None,
    drive_client: GoogleDriveClient | None = None,
    scanner_client: LangChainScannerClient | None = None,
) -> dict[str, Any]:
    """Upload file to Drive, scan with LangChain, and import into inventory DB."""
    if not (folder_url_or_id or DEFAULT_DRIVE_FOLDER_URL):
        raise GoogleDriveIntegrationError("GOOGLE_DRIVE_TARGET_FOLDER_URL environment variable must be set")

    resolved_confidence = DEFAULT_MIN_CONFIDENCE if min_confidence is None else float(min_confidence)
    scan_retries = int(os.getenv("LANGCHAIN_SCAN_RETRIES", "3"))
    scan_retry_delay_seconds = float(os.getenv("LANGCHAIN_SCAN_RETRY_DELAY_SECONDS", "1.5"))
    folder_id = extract_drive_folder_id(folder_url_or_id or DEFAULT_DRIVE_FOLDER_URL)

    drive = drive_client or GoogleDriveClient()
    scanner = scanner_client or LangChainScannerClient()

    drive_file = drive.upload_file_bytes(file_bytes=file_bytes, filename=filename, folder_id=folder_id)
    drive_file_id = drive_file.get("id")
    if not drive_file_id:
        raise GoogleDriveIntegrationError("Google Drive upload succeeded but no file ID was returned")

    scan_payload: dict[str, Any] = {}
    status = ""
    card_name = ""
    confidence = 0.0

    for attempt in range(scan_retries):
        scan_payload = scanner.scan_image_bytes(file_bytes, filename)
        status = str(scan_payload.get("status", "")).lower()
        card_name = str(scan_payload.get("card_name", "")).strip()
        confidence = _safe_float(scan_payload.get("confidence"), 0.0)

        if status == "success" and card_name and confidence >= resolved_confidence:
            break

        if attempt < scan_retries - 1:
            time.sleep(scan_retry_delay_seconds * (attempt + 1))

    if status != "success":
        raise GoogleDriveIntegrationError(
            f"LangChain scan failed with status '{scan_payload.get('status')}'"
        )
    if not card_name:
        raise GoogleDriveIntegrationError("LangChain scan did not identify a card name")
    if confidence < resolved_confidence:
        raise GoogleDriveIntegrationError(
            f"LangChain confidence {confidence:.2f} is below required {resolved_confidence:.2f}"
        )

    df = _build_scanner_dataframe(scan_payload, filename)
    csv_buffer = io.BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    import_result = import_csv(db, csv_buffer)

    return {
        "drive_file_id": drive_file_id,
        "drive_web_view_link": drive_file.get("webViewLink"),
        "scanner": {
            "status": scan_payload.get("status", "success"),
            "card_name": card_name,
            "set_code": scan_payload.get("set_code"),
            "set_name": scan_payload.get("set_name"),
            "confidence": confidence,
            "required_confidence": resolved_confidence,
        },
        "import_result": import_result,
    }
