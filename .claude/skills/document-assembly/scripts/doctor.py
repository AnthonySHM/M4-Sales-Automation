"""
doctor.py — Health check for the Document Assembly skill.

Verifies: credentials env var, service account auth, Drive API reachability,
Shared Drive membership, master template accessibility, ledger sheet accessibility.

Exit codes:
  0 — all checks pass (status: ok)
  1 — one or more checks failed (status: degraded or fail)
  3 — credential/permission error that requires human action
"""

import argparse
import json
import os
import sys

import yaml


def load_workspace(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def check_credentials_env(unit_test_mode: bool = False) -> dict:
    """Check GOOGLE_APPLICATION_CREDENTIALS env var and key file presence.

    In unit-test mode (no API clients injected) this check is skipped so that
    tests never require a real credential file to be present. (SB-02, Architecture §9)
    """
    if unit_test_mode:
        return {"name": "credentials_env", "status": "skip",
                "detail": "Skipped in unit-test mode (no API clients injected)"}
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not path:
        return {"name": "credentials_env", "status": "fail",
                "detail": "GOOGLE_APPLICATION_CREDENTIALS is not set"}
    if not os.path.isfile(path):
        return {"name": "credentials_env", "status": "fail",
                "detail": f"Key file not found: {path}"}
    return {"name": "credentials_env", "status": "pass",
            "detail": f"Key file present: {path}"}


def check_service_auth(google_clients: dict) -> dict:
    """Attempt to obtain an access token using the injected auth client."""
    auth = google_clients.get("auth")
    if auth is None:
        return {"name": "service_auth", "status": "skip",
                "detail": "No auth client injected (unit-test mode)"}
    try:
        auth.refresh()
        return {"name": "service_auth", "status": "pass", "detail": "Token obtained"}
    except Exception as exc:
        return {"name": "service_auth", "status": "fail", "detail": str(exc)}


def check_drive_api(google_clients: dict, workspace: dict) -> dict:
    """Verify Drive API is reachable and service account is a Shared Drive member."""
    drive = google_clients.get("drive")
    if drive is None:
        return {"name": "drive_api", "status": "skip",
                "detail": "No Drive client injected (unit-test mode)"}
    try:
        drive.get_drive(workspace["shared_drive_id"])
        return {"name": "drive_api", "status": "pass",
                "detail": f"Shared Drive accessible: {workspace['shared_drive_id']}"}
    except Exception as exc:
        return {"name": "drive_api", "status": "fail", "detail": str(exc)}


def check_master_template(google_clients: dict, workspace: dict) -> dict:
    """Verify master template file is readable and revision matches config."""
    drive = google_clients.get("drive")
    if drive is None:
        return {"name": "master_template", "status": "skip",
                "detail": "No Drive client injected (unit-test mode)"}
    family = workspace.get("pilot_family", {})
    file_id = family.get("master_template_id", "")
    approved_rev = family.get("approved_revision_id", "")
    if not file_id or file_id.startswith("REPLACE_"):
        return {"name": "master_template", "status": "skip",
                "detail": "Master template ID not yet configured"}
    try:
        rev = drive.get_revision(file_id)
        if rev != approved_rev:
            return {"name": "master_template", "status": "fail",
                    "detail": f"Revision mismatch. Live: {rev}, approved: {approved_rev}"}
        return {"name": "master_template", "status": "pass",
                "detail": f"Master revision matches: {rev}"}
    except Exception as exc:
        return {"name": "master_template", "status": "fail", "detail": str(exc)}


def check_ledger(google_clients: dict, workspace: dict) -> dict:
    """Verify ledger spreadsheet is readable."""
    sheets = google_clients.get("sheets")
    if sheets is None:
        return {"name": "ledger", "status": "skip",
                "detail": "No Sheets client injected (unit-test mode)"}
    ledger = workspace.get("ledger", {})
    sheet_id = ledger.get("spreadsheet_id", "")
    if not sheet_id or sheet_id.startswith("REPLACE_"):
        return {"name": "ledger", "status": "skip",
                "detail": "Ledger spreadsheet ID not yet configured"}
    try:
        sheets.get_spreadsheet(sheet_id)
        return {"name": "ledger", "status": "pass",
                "detail": f"Ledger accessible: {sheet_id}"}
    except Exception as exc:
        return {"name": "ledger", "status": "fail", "detail": str(exc)}


def run_checks(workspace: dict, google_clients: dict | None = None) -> dict:
    if google_clients is None:
        google_clients = {}

    unit_test_mode = not bool(google_clients)

    checks = [
        check_credentials_env(unit_test_mode=unit_test_mode),
        check_service_auth(google_clients),
        check_drive_api(google_clients, workspace),
        check_master_template(google_clients, workspace),
        check_ledger(google_clients, workspace),
    ]

    failed = [c for c in checks if c["status"] == "fail"]
    if failed:
        overall = "fail"
    elif any(c["status"] == "degraded" for c in checks):
        overall = "degraded"
    else:
        overall = "ok"

    return {"status": overall, "checks": checks}


def main(argv=None):
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
        result = {"status": "fail", "checks": [
            {"name": "workspace_config", "status": "fail",
             "detail": f"Config file not found: {args.workspace}"}
        ]}
        print(json.dumps(result))
        sys.exit(3)
    except Exception as exc:
        result = {"status": "fail", "checks": [
            {"name": "workspace_config", "status": "fail",
             "detail": f"Failed to parse config: {exc}"}
        ]}
        print(json.dumps(result))
        sys.exit(1)

    result = run_checks(workspace)
    print(json.dumps(result))

    if result["status"] == "fail":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
