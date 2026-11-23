"""Google Drive integration - syncs posting artefacts to a Drive folder."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models.profile import cv_filenames  # noqa: E402

load_dotenv()

# Scopes required: file creation and metadata reads only.
_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Files to sync per posting (relative to the posting directory).
# Drive is object storage: raw posting, the bespoke CV, and the personal statement.
# Status and detailed analysis live in the repo (applications.yaml + application_review.json)
# and are not synced; Claude Code reads the repo directly.
_SYNC_FILES = [
    "posting.txt",
    "personal_statement.txt",
    cv_filenames()["html"],
    cv_filenames()["pdf"],
]

_MIME_TYPES: dict[str, str] = {
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".yaml": "text/yaml",
}

# Files at the repo root synced to the Drive root folder. applications.yaml is the
# state spine; mirroring it to Drive lets you glance at the index from any device.
_ROOT_FILES = ["applications.yaml"]

_TOKEN_PATH = Path("token.json")
_ROOT_FOLDER_NAME = "job-seeker"


def _authenticate():
    """Return an authorised Google Drive service, handling the OAuth flow."""
    client_id = os.environ.get("GOOGLE_DRIVE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise EnvironmentError(
            "GOOGLE_DRIVE_CLIENT_ID and GOOGLE_DRIVE_CLIENT_SECRET must be set in .env"
        )

    creds: Credentials | None = None

    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, _SCOPES)
            creds = flow.run_local_server(port=0)

        _TOKEN_PATH.write_text(creds.to_json())

    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service, name: str, parent_id: str | None = None) -> str:
    """Return the Drive folder ID for *name*, creating it if absent."""
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def _upload_or_update(service, file_path: Path, folder_id: str) -> None:
    """Upload *file_path* to *folder_id*, updating in place if it already exists."""
    mime_type = _MIME_TYPES.get(file_path.suffix, "application/octet-stream")

    query = (
        f"name='{file_path.name}' and '{folder_id}' in parents and trashed=false"
    )
    existing = service.files().list(q=query, fields="files(id)").execute().get("files", [])

    media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=False)

    if existing:
        service.files().update(fileId=existing[0]["id"], media_body=media).execute()
        print(f"  updated  {file_path.name}")
    else:
        metadata = {"name": file_path.name, "parents": [folder_id]}
        service.files().create(body=metadata, media_body=media, fields="id").execute()
        print(f"  uploaded {file_path.name}")


def sync_postings(postings_dir: Path = Path("postings")) -> None:
    """Sync artefacts for every posting under *postings_dir* to Google Drive.

    Also uploads repo-root files in ``_ROOT_FILES`` (currently ``applications.yaml``)
    so the state spine is mirrored to Drive.
    """
    service = _authenticate()

    root_id = _get_or_create_folder(service, _ROOT_FOLDER_NAME)
    print(f"Drive root folder: {_ROOT_FOLDER_NAME} ({root_id})")

    # Sync root-level files (applications.yaml) to the Drive root folder.
    print("\nroot files:")
    for filename in _ROOT_FILES:
        file_path = Path(filename)
        if file_path.exists():
            _upload_or_update(service, file_path, root_id)
        else:
            print(f"  skipped  {filename} (not found at repo root)")

    postings_folder_id = _get_or_create_folder(service, "postings", parent_id=root_id)

    for posting_dir in sorted(postings_dir.iterdir()):
        if not posting_dir.is_dir():
            continue

        folder_id = _get_or_create_folder(service, posting_dir.name, parent_id=postings_folder_id)
        print(f"\n{posting_dir.name}/")

        for filename in _SYNC_FILES:
            file_path = posting_dir / filename
            if file_path.exists():
                _upload_or_update(service, file_path, folder_id)
            else:
                print(f"  skipped  {filename} (not found)")


# Allow direct invocation: python integrations/google_drive.py
if __name__ == "__main__":
    sync_postings()

