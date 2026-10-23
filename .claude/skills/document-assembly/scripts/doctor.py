"""
doctor.py — Health check for the Document Assembly skill (Issue #5).

Five checks (Architecture §4.1):
  1. credentials_env   — GOOGLE_APPLICATION_CREDENTIALS set and key file exists
  2. service_auth      — injected credentials can be refreshed (token obtained)
  3. drive_api         — drives().get(driveId=shared_drive_id) succeeds
  4. master_template   — files().get(fileId=...) reachable; headRevisionId matches
  5. ledger            — spreadsheets().get(spreadsheetId=...) reachable

Uses real googleapiclient method signatures; unit tests inject fakes (SB-05).

Exit codes:
  0 — all checks pass or skip (status: ok)
  1 — one or more checks failed (status: fail)
  3 — credential/permission error that requires human action
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import yaml


# ---------------------------------------------------------------------------
# Workspace loader
# ---------------------------------------------------------------------------


def load_workspace(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_credentials_env(unit_test_mode: bool = False) -> dict:
    """Check GOOGLE_APPLICATION_CREDENTIALS env var and key file presence (SB-02).

    Skipped in unit-test mode so tests never require a real credential file.
    """
    if unit_test_mode:
        return {
            "name": "credentials_env",
            "status": "skip",
            "detail": "Skipped in unit-test mode (no API clients injected)",
        }
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not path:
        return {
            "name": "credentials_env",
            "status": "fail",
            "detail": "GOOGLE_APPLICATION_CREDENTIALS is not set",
        }
    if not os.path.isfile(path):
        return {
            "name": "credentials_env",
            "status": "fail",
            "detail": f"Key file not found: {path}",
        }
    return {
        "name": "credentials_env",
        "status": "pass",
        "detail": f"Key file present: {path}",
    }


def check_service_auth(creds) -> dict:
    """Attempt to refresh the injected credentials object (token fetch).

    Accepts a google.oauth2.service_account.Credentials or compatible fake.
    Returns skip when creds is None (unit-test mode).
    """
    if creds is None:
        return {
            "name": "service_auth",
            "status": "skip",
            "detail": "No credentials injected (unit-test mode)",
        }
    try:
        import google.auth.transport.requests as _gtr

        creds.refresh(_gtr.Request())
        return {"name": "service_auth", "status": "pass", "detail": "Token refreshed"}
    except Exception as exc:  # noqa: BLE001
        return {"name": "service_auth", "status": "fail", "detail": str(exc)}


def check_drive_api(drive_client, workspace: dict) -> dict:
    """Verify Drive API reachable; service account is a Shared Drive member.

    Uses drives().get(driveId=shared_drive_id).execute() (Architecture §7).
    """
    if drive_client is None:
        return {
            "name": "drive_api",
            "status": "skip",
            "detail": "No Drive client injected (unit-test mode)",
        }
    shared_drive_id: str = workspace.get("shared_drive_id", "")
    if not shared_drive_id or shared_drive_id.startswith("REPLACE_"):
        return {
            "name": "drive_api",
            "status": "skip",
            "detail": "Shared Drive ID not yet configured",
        }
    try:
        drive_client.drives().get(driveId=shared_drive_id).execute()
        return {
            "name": "drive_api",
            "status": "pass",
            "detail": f"Shared Drive accessible: {shared_drive_id}",
        }
    except Exception as exc:  # noqa: BLE001
        return {"name": "drive_api", "status": "fail", "detail": str(exc)}


def check_master_template(drive_client, workspace: dict) -> dict:
    """Verify master template is readable and its headRevisionId matches config (G-08).

    Uses files().get(fileId=..., fields="headRevisionId", supportsAllDrives=True).execute().
    """
    if drive_client is None:
        return {
            "name": "master_template",
            "status": "skip",
            "detail": "No Drive client injected (unit-test mode)",
        }
    family = workspace.get("pilot_family", {})
    file_id: str = family.get("master_template_id", "")
    approved_rev: str = family.get("approved_revision_id", "")
    if not file_id or file_id.startswith("REPLACE_"):
        return {
            "name": "master_template",
            "status": "skip",
            "detail": "Master template ID not yet configured",
        }
    try:
        meta = (
            drive_client.files()
            .get(fileId=file_id, fields="headRevisionId", supportsAllDrives=True)
            .execute()
        )
        live_rev: str = meta.get("headRevisionId", "")
        if approved_rev and live_rev != approved_rev:
            return {
                "name": "master_template",
                "status": "fail",
                "detail": (
                    f"Revision mismatch. Live: {live_rev!r}, approved: {approved_rev!r}"
                ),
            }
        return {
            "name": "master_template",
            "status": "pass",
            "detail": f"Master accessible; revision {live_rev!r}",
        }
    except Exception as exc:  # noqa: BLE001
        return {"name": "master_template", "status": "fail", "detail": str(exc)}


def check_ledger(sheets_client, workspace: dict) -> dict:
    """Verify ledger spreadsheet is readable.

    Uses spreadsheets().get(spreadsheetId=...).execute() (Architecture §7).
    """
    if sheets_client is None:
        return {
            "name": "ledger",
            "status": "skip",
            "detail": "No Sheets client injected (unit-test mode)",
        }
    ledger_cfg = workspace.get("ledger", {})
    sheet_id: str = ledger_cfg.get("spreadsheet_id", "")
    if not sheet_id or sheet_id.startswith("REPLACE_"):
        return {
            "name": "ledger",
            "status": "skip",
            "detail": "Ledger spreadsheet ID not yet configured",
        }
    try:
        sheets_client.spreadsheets().get(spreadsheetId=sheet_id).execute()
        return {
            "name": "ledger",
            "status": "pass",
            "detail": f"Ledger accessible: {sheet_id}",
        }
    except Exception as exc:  # noqa: BLE001
        return {"name": "ledger", "status": "fail", "detail": str(exc)}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_checks(
    workspace: dict,
    *,
    creds=None,
    drive_client=None,
    sheets_client=None,
) -> dict:
    """Run all five health checks and return structured result.

    When no clients are injected (unit-test mode), API-dependent checks return 'skip'.
    """
    unit_test_mode = (creds is None and drive_client is None and sheets_client is None)

    checks = [
        check_credentials_env(unit_test_mode=unit_test_mode),
        check_service_auth(creds),
        check_drive_api(drive_client, workspace),
        check_master_template(drive_client, workspace),
        check_ledger(sheets_client, workspace),
    ]

    if any(c["status"] == "fail" for c in checks):
        overall = "fail"
    elif any(c["status"] == "degraded" for c in checks):
        overall = "degraded"
    else:
        overall = "ok"

    return {"status": overall, "checks": checks}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None, creds=None, drive_client=None, sheets_client=None) -> None:
    parser = argparse.ArgumentParser(description="Document Assembly health check")
    parser.add_argument(
        "--workspace",
        default="config/workspace.yaml",
        help="Path to workspace.yaml (default: config/workspace.yaml)",
    )
    args = parser.parse_args(argv)

    try:
        workspace = load_workspace(args.workspace)
    except FileNotFoundError:
        result = {
            "status": "fail",
            "checks": [{
                "name": "workspace_config",
                "status": "fail",
                "detail": f"Config file not found: {args.workspace}",
            }],
        }
        print(json.dumps(result))
        sys.exit(3)
    except Exception as exc:  # noqa: BLE001
        result = {
            "status": "fail",
            "checks": [{
                "name": "workspace_config",
                "status": "fail",
                "detail": f"Failed to parse config: {exc}",
            }],
        }
        print(json.dumps(result))
        sys.exit(1)

    # Build real API clients when not injected (skipped in unit tests)
    if creds is None and drive_client is None and sheets_client is None:  # pragma: no cover
        try:
            import google.auth
            from googleapiclient.discovery import build as _build

            creds, _ = google.auth.default(
                scopes=[
                    "https://www.googleapis.com/auth/drive.readonly",
                    "https://www.googleapis.com/auth/spreadsheets.readonly",
                ]
            )
            drive_client = _build("drive", "v3", credentials=creds)
            sheets_client = _build("sheets", "v4", credentials=creds)
        except Exception as exc:
            result = {
                "status": "fail",
                "checks": [{
                    "name": "service_auth",
                    "status": "fail",
                    "detail": f"Failed to build API clients: {exc}",
                }],
            }
            print(json.dumps(result))
            sys.exit(3)

    result = run_checks(
        workspace,
        creds=creds,
        drive_client=drive_client,
        sheets_client=sheets_client,
    )
    print(json.dumps(result))

    if result["status"] == "fail":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
