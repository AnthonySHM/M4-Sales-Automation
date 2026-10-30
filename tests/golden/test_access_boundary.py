"""
Golden-set access boundary test (Issue #18).

Verifies G-12 (access boundaries) and SB-01 (least-privilege Drive access):
  - The service account receives a 403 error when attempting to read a file
    it was not explicitly granted access to.

REQUIRES: `pytest.mark.live` — only runs when --run-live is passed and
GOOGLE_APPLICATION_CREDENTIALS points to a valid sandbox service account key.

These tests MUST NOT run against the production Shared Drive. (SB-05)
"""

from __future__ import annotations

import os
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: mark test as requiring a live sandbox Shared Drive connection "
        "(skipped unless --run-live is passed)",
    )


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--run-live",
            action="store_true",
            default=False,
            help="Run tests that require a live Google API connection (sandbox only)",
        )
    except ValueError:
        pass  # option already added by conftest


@pytest.fixture
def _live_only(request):
    if not request.config.getoption("--run-live", default=False):
        pytest.skip("Skipped: pass --run-live to run live sandbox tests (Issue #3 required)")


@pytest.fixture
def _sandbox_creds(_live_only):
    """Load service account credentials for sandbox Drive (not production)."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not creds_path or not os.path.isfile(creds_path):
        pytest.skip(
            "GOOGLE_APPLICATION_CREDENTIALS not set or file missing. "
            "Set it to the sandbox service account key path (Issue #3 required)."
        )
    creds = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)


@pytest.mark.live
def test_denied_access_returns_403(_sandbox_creds):
    """Service account receives 403 when reading a file it has no access to. (G-12, SB-01)

    SETUP (human, Issue #3):
      1. Create a Google Doc in a Drive the service account is NOT a member of.
      2. Set UNGRANTED_FILE_ID env var to that doc's ID.

    This confirms the service account truly has least-privilege access — it
    cannot read arbitrary Drive files, only those in the designated Shared Drive.
    """
    from googleapiclient.errors import HttpError

    file_id = os.environ.get("UNGRANTED_FILE_ID", "")
    if not file_id:
        pytest.skip(
            "UNGRANTED_FILE_ID not set. "
            "Create a file the service account has no access to and set this env var."
        )

    with pytest.raises(HttpError) as exc_info:
        _sandbox_creds.files().get(fileId=file_id, supportsAllDrives=False).execute()

    # Google Drive returns 404 (not 403) for files the caller has no access to,
    # deliberately hiding their existence. Both 403 and 404 confirm the service
    # account cannot read the file (SB-01).
    assert exc_info.value.resp.status in (403, 404), (
        f"Expected 403 or 404 but got {exc_info.value.resp.status}. "
        "The service account may have broader access than intended (SB-01 violation)."
    )


@pytest.mark.live
def test_sandbox_drive_is_accessible(_sandbox_creds):
    """Service account CAN access the designated sandbox Drive folder. (G-12, SB-01)

    Uses files().get() with supportsAllDrives=True because the pilot uses a
    regular shared folder rather than a Google Shared Drive (AD-08).

    SETUP (human, Issue #3):
      Set SANDBOX_SHARED_DRIVE_ID env var to the sandbox Drive folder ID.
    """
    folder_id = os.environ.get("SANDBOX_SHARED_DRIVE_ID", "")
    if not folder_id:
        pytest.skip(
            "SANDBOX_SHARED_DRIVE_ID not set. "
            "Set it to the sandbox Drive folder ID (Issue #3 required)."
        )

    result = _sandbox_creds.files().get(
        fileId=folder_id, supportsAllDrives=True
    ).execute()
    assert result.get("id") == folder_id, (
        f"Folder ID mismatch: expected {folder_id!r}, got {result.get('id')!r}"
    )
