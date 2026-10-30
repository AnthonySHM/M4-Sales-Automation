"""Shared fixtures and options for golden-set tests (Issue #16)."""
from __future__ import annotations
import json
import os
import pathlib
import pytest
import yaml


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: mark test as requiring live Google API access to sandbox Drive "
        "(skipped unless --run-live is passed)",
    )


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--run-live",
            action="store_true",
            default=False,
            help="Run tests that make live Google API calls against the sandbox Drive",
        )
    except ValueError:
        pass  # already registered


@pytest.fixture(scope="session")
def workspace_cfg():
    """Load workspace.yaml. Patch approved_revision_id to empty to skip revision guard."""
    root = pathlib.Path(__file__).parent.parent.parent
    with open(root / "config" / "workspace.yaml") as f:
        ws = yaml.safe_load(f)
    # Override revision guard for tests — master is never modified by tests (G-08 verified separately)
    ws.setdefault("pilot_family", {})["approved_revision_id"] = ""
    return ws


@pytest.fixture(scope="session")
def recipe():
    root = pathlib.Path(__file__).parent.parent.parent
    return json.loads((root / "config" / "recipes" / "mss_sow_v1.json").read_text())


@pytest.fixture(scope="session")
def live_clients(request):
    """Build real Drive, Docs, Sheets API clients from default credentials.
    Only available when --run-live is passed."""
    if not request.config.getoption("--run-live", default=False):
        pytest.skip("Skipped: pass --run-live to run live sandbox tests")
    try:
        import google.auth
        from googleapiclient.discovery import build
        creds, _ = google.auth.default(scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/spreadsheets",
        ])
        drive = build("drive", "v3", credentials=creds)
        docs = build("docs", "v1", credentials=creds)
        sheets = build("sheets", "v4", credentials=creds)
        return {"drive": drive, "docs": docs, "sheets": sheets}
    except Exception as exc:
        pytest.skip(f"Could not build Google API clients: {exc}")


@pytest.fixture
def created_doc_ids():
    """Accumulator for Drive doc IDs created during a test — for cleanup."""
    ids = []
    yield ids
    # Teardown: delete all created docs
    if ids:
        try:
            import google.auth
            from googleapiclient.discovery import build
            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive"])
            drive = build("drive", "v3", credentials=creds)
            for doc_id in ids:
                try:
                    drive.files().delete(fileId=doc_id, supportsAllDrives=True).execute()
                except Exception:
                    pass  # best-effort cleanup
        except Exception:
            pass
