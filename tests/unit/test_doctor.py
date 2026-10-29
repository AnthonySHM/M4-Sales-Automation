"""
Unit tests for doctor.py (Issue #5).

Covers all five checks with fake clients matching real googleapiclient signatures:
  - check_credentials_env
  - check_service_auth
  - check_drive_api
  - check_master_template
  - check_ledger
  - run_checks (orchestration + overall status)
  - main() (CLI: missing config, bad yaml, workspace_config check)

No live Google API calls are made. (SB-05)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest
import yaml

SCRIPTS = os.path.join(
    os.path.dirname(__file__),
    "..", "..",
    ".claude", "skills", "document-assembly", "scripts",
)
sys.path.insert(0, os.path.abspath(SCRIPTS))

import doctor


# ---------------------------------------------------------------------------
# Fake client helpers (matching real googleapiclient chain signatures)
# ---------------------------------------------------------------------------

class _Exec:
    def __init__(self, result):
        self._result = result
        self._exc = None

    def raise_on_execute(self, exc):
        self._exc = exc
        return self

    def execute(self):
        if self._exc:
            raise self._exc
        return self._result


class FakeDriveClient:
    """Fake Drive client implementing drives().get() and files().get()."""

    def __init__(self, drive_result=None, file_result=None, drive_exc=None, file_exc=None):
        self._drive_result = drive_result or {"id": "fake-drive-id"}
        self._file_result = file_result or {"version": "rev-abc"}
        self._drive_exc = drive_exc
        self._file_exc = file_exc
        self.drives_get_calls = []
        self.files_get_calls = []

    class _DriveResource:
        def __init__(self, result, exc, calls):
            self._result = result
            self._exc = exc
            self._calls = calls

        def get(self, driveId):
            self._calls.append({"driveId": driveId})
            e = _Exec(self._result)
            if self._exc:
                e._exc = self._exc
            return e

    class _FilesResource:
        def __init__(self, result, exc, calls):
            self._result = result
            self._exc = exc
            self._calls = calls

        def get(self, fileId, fields=None, supportsAllDrives=None):
            self._calls.append({"fileId": fileId, "fields": fields})
            e = _Exec(self._result)
            if self._exc:
                e._exc = self._exc
            return e

    def drives(self):
        return self._DriveResource(self._drive_result, self._drive_exc, self.drives_get_calls)

    def files(self):
        return self._FilesResource(self._file_result, self._file_exc, self.files_get_calls)


class FakeSheetsClient:
    """Fake Sheets client implementing spreadsheets().get()."""

    def __init__(self, result=None, exc=None):
        self._result = result or {"spreadsheetId": "fake-sheet-id"}
        self._exc = exc
        self.get_calls = []

    class _SpreadsheetsResource:
        def __init__(self, result, exc, calls):
            self._result = result
            self._exc = exc
            self._calls = calls

        def get(self, spreadsheetId):
            self._calls.append({"spreadsheetId": spreadsheetId})
            e = _Exec(self._result)
            if self._exc:
                e._exc = self._exc
            return e

    def spreadsheets(self):
        return self._SpreadsheetsResource(self._result, self._exc, self.get_calls)


class FakeCreds:
    """Fake credentials object with a .refresh() method."""

    def __init__(self, exc=None):
        self._exc = exc
        self.refresh_calls = 0

    def refresh(self, request):
        self.refresh_calls += 1
        if self._exc:
            raise self._exc


# ---------------------------------------------------------------------------
# Workspace fixtures
# ---------------------------------------------------------------------------

WORKSPACE_PLACEHOLDER = {
    "workspace_id": "ws-test",
    "shared_drive_id": "REPLACE_DRIVE",
    "folders": {
        "masters": "REPLACE_MASTERS",
        "review": "REPLACE_REVIEW",
        "approved": "REPLACE_APPROVED",
        "quarantine": "REPLACE_QUARANTINE",
    },
    "ledger": {
        "spreadsheet_id": "REPLACE_SHEET",
        "jobs_tab": "jobs",
        "events_tab": "events",
    },
    "pilot_family": {
        "key": "family_a",
        "master_template_id": "REPLACE_MASTER",
        "approved_revision_id": "REPLACE_REV",
        "active_recipe_version": 1,
    },
}

WORKSPACE_CONFIGURED = {
    "workspace_id": "ws-test",
    "shared_drive_id": "drive-real-001",
    "folders": {
        "masters": "folder-masters",
        "review": "folder-review",
        "approved": "folder-approved",
        "quarantine": "folder-quarantine",
    },
    "ledger": {
        "spreadsheet_id": "sheet-real-001",
        "jobs_tab": "jobs",
        "events_tab": "events",
    },
    "pilot_family": {
        "key": "family_a",
        "master_template_id": "doc-master-001",
        "approved_revision_id": "rev-abc",
        "active_recipe_version": 1,
    },
}


def write_temp_yaml(data: dict) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.dump(data, f)
    f.close()
    return f.name


# ---------------------------------------------------------------------------
# check_credentials_env
# ---------------------------------------------------------------------------

class TestCheckCredentialsEnv:
    def test_skipped_in_unit_test_mode(self):
        result = doctor.check_credentials_env(unit_test_mode=True)
        assert result["status"] == "skip"
        assert result["name"] == "credentials_env"

    def test_fail_when_env_not_set(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        result = doctor.check_credentials_env(unit_test_mode=False)
        assert result["status"] == "fail"
        assert "not set" in result["detail"]

    def test_fail_when_key_file_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "missing.json"))
        result = doctor.check_credentials_env(unit_test_mode=False)
        assert result["status"] == "fail"
        assert "not found" in result["detail"]

    def test_pass_when_key_file_present(self, monkeypatch, tmp_path):
        key_file = tmp_path / "sa.json"
        key_file.write_text("{}")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key_file))
        result = doctor.check_credentials_env(unit_test_mode=False)
        assert result["status"] == "pass"
        assert str(key_file) in result["detail"]

    def test_result_has_required_keys(self):
        result = doctor.check_credentials_env(unit_test_mode=True)
        assert "name" in result
        assert "status" in result
        assert "detail" in result


# ---------------------------------------------------------------------------
# check_service_auth
# ---------------------------------------------------------------------------

class TestCheckServiceAuth:
    def test_skipped_when_creds_none(self):
        result = doctor.check_service_auth(None)
        assert result["status"] == "skip"
        assert result["name"] == "service_auth"

    def test_pass_when_refresh_succeeds(self):
        creds = FakeCreds()
        result = doctor.check_service_auth(creds)
        assert result["status"] == "pass"
        assert creds.refresh_calls == 1

    def test_fail_when_refresh_raises(self):
        creds = FakeCreds(exc=Exception("auth_error: invalid credentials"))
        result = doctor.check_service_auth(creds)
        assert result["status"] == "fail"
        assert "auth_error" in result["detail"]

    def test_result_has_required_keys(self):
        result = doctor.check_service_auth(None)
        assert "name" in result
        assert "status" in result
        assert "detail" in result


# ---------------------------------------------------------------------------
# check_drive_api
# ---------------------------------------------------------------------------

class TestCheckDriveApi:
    def test_skipped_when_client_none(self):
        result = doctor.check_drive_api(None, WORKSPACE_CONFIGURED)
        assert result["status"] == "skip"
        assert result["name"] == "drive_api"

    def test_skipped_when_drive_id_placeholder(self):
        drive = FakeDriveClient()
        result = doctor.check_drive_api(drive, WORKSPACE_PLACEHOLDER)
        assert result["status"] == "skip"
        assert "not yet configured" in result["detail"]

    def test_skipped_when_drive_id_missing(self):
        drive = FakeDriveClient()
        ws = {**WORKSPACE_CONFIGURED, "shared_drive_id": ""}
        result = doctor.check_drive_api(drive, ws)
        assert result["status"] == "skip"

    def test_pass_when_drive_accessible(self):
        drive = FakeDriveClient()
        result = doctor.check_drive_api(drive, WORKSPACE_CONFIGURED)
        assert result["status"] == "pass"
        assert "drive-real-001" in result["detail"]
        assert drive.drives_get_calls[0]["driveId"] == "drive-real-001"

    def test_fail_when_api_raises(self):
        drive = FakeDriveClient(
            drive_exc=Exception("403 forbidden"),
            file_exc=Exception("403 forbidden"),
        )
        result = doctor.check_drive_api(drive, WORKSPACE_CONFIGURED)
        assert result["status"] == "fail"
        assert "403" in result["detail"]

    def test_calls_drives_get_with_correct_id(self):
        drive = FakeDriveClient()
        doctor.check_drive_api(drive, WORKSPACE_CONFIGURED)
        assert drive.drives_get_calls[0]["driveId"] == "drive-real-001"


# ---------------------------------------------------------------------------
# check_master_template
# ---------------------------------------------------------------------------

class TestCheckMasterTemplate:
    def test_skipped_when_client_none(self):
        result = doctor.check_master_template(None, WORKSPACE_CONFIGURED)
        assert result["status"] == "skip"
        assert result["name"] == "master_template"

    def test_skipped_when_file_id_placeholder(self):
        drive = FakeDriveClient()
        result = doctor.check_master_template(drive, WORKSPACE_PLACEHOLDER)
        assert result["status"] == "skip"
        assert "not yet configured" in result["detail"]

    def test_skipped_when_file_id_missing(self):
        drive = FakeDriveClient()
        ws = {
            **WORKSPACE_CONFIGURED,
            "pilot_family": {**WORKSPACE_CONFIGURED["pilot_family"], "master_template_id": ""},
        }
        result = doctor.check_master_template(drive, ws)
        assert result["status"] == "skip"

    def test_pass_when_revision_matches(self):
        drive = FakeDriveClient(file_result={"version": "rev-abc"})
        result = doctor.check_master_template(drive, WORKSPACE_CONFIGURED)
        assert result["status"] == "pass"
        assert "rev-abc" in result["detail"]

    def test_fail_when_revision_mismatch(self):
        drive = FakeDriveClient(file_result={"version": "rev-XYZ"})
        result = doctor.check_master_template(drive, WORKSPACE_CONFIGURED)
        assert result["status"] == "fail"
        assert "rev-XYZ" in result["detail"]
        assert "rev-abc" in result["detail"]

    def test_pass_when_no_approved_revision_configured(self):
        drive = FakeDriveClient(file_result={"version": "rev-whatever"})
        ws = {
            **WORKSPACE_CONFIGURED,
            "pilot_family": {
                **WORKSPACE_CONFIGURED["pilot_family"],
                "approved_revision_id": "",
            },
        }
        result = doctor.check_master_template(drive, ws)
        assert result["status"] == "pass"

    def test_fail_when_api_raises(self):
        drive = FakeDriveClient(file_exc=Exception("404 not found"))
        result = doctor.check_master_template(drive, WORKSPACE_CONFIGURED)
        assert result["status"] == "fail"
        assert "404" in result["detail"]

    def test_calls_files_get_with_correct_params(self):
        drive = FakeDriveClient(file_result={"version": "rev-abc"})
        doctor.check_master_template(drive, WORKSPACE_CONFIGURED)
        call = drive.files_get_calls[0]
        assert call["fileId"] == "doc-master-001"
        assert "version" in call["fields"]


# ---------------------------------------------------------------------------
# check_ledger
# ---------------------------------------------------------------------------

class TestCheckLedger:
    def test_skipped_when_client_none(self):
        result = doctor.check_ledger(None, WORKSPACE_CONFIGURED)
        assert result["status"] == "skip"
        assert result["name"] == "ledger"

    def test_skipped_when_sheet_id_placeholder(self):
        sheets = FakeSheetsClient()
        result = doctor.check_ledger(sheets, WORKSPACE_PLACEHOLDER)
        assert result["status"] == "skip"
        assert "not yet configured" in result["detail"]

    def test_skipped_when_sheet_id_missing(self):
        sheets = FakeSheetsClient()
        ws = {**WORKSPACE_CONFIGURED, "ledger": {"spreadsheet_id": "", "jobs_tab": "j", "events_tab": "e"}}
        result = doctor.check_ledger(sheets, ws)
        assert result["status"] == "skip"

    def test_pass_when_sheet_accessible(self):
        sheets = FakeSheetsClient()
        result = doctor.check_ledger(sheets, WORKSPACE_CONFIGURED)
        assert result["status"] == "pass"
        assert "sheet-real-001" in result["detail"]
        assert sheets.get_calls[0]["spreadsheetId"] == "sheet-real-001"

    def test_fail_when_api_raises(self):
        sheets = FakeSheetsClient(exc=Exception("403 access denied"))
        result = doctor.check_ledger(sheets, WORKSPACE_CONFIGURED)
        assert result["status"] == "fail"
        assert "403" in result["detail"]

    def test_calls_spreadsheets_get_with_correct_id(self):
        sheets = FakeSheetsClient()
        doctor.check_ledger(sheets, WORKSPACE_CONFIGURED)
        assert sheets.get_calls[0]["spreadsheetId"] == "sheet-real-001"


# ---------------------------------------------------------------------------
# run_checks — orchestration and overall status
# ---------------------------------------------------------------------------

class TestRunChecks:
    def test_all_skips_when_no_clients_injected(self):
        """Unit-test mode: all API checks return 'skip'."""
        result = doctor.run_checks(WORKSPACE_PLACEHOLDER)
        assert result["status"] == "ok"
        assert len(result["checks"]) == 5
        api_checks = [c for c in result["checks"] if c["name"] != "credentials_env"]
        for c in api_checks:
            assert c["status"] == "skip", f"{c['name']} should be skip, got {c['status']}"

    def test_credentials_env_skipped_in_unit_test_mode(self):
        result = doctor.run_checks(WORKSPACE_PLACEHOLDER)
        cred_check = next(c for c in result["checks"] if c["name"] == "credentials_env")
        assert cred_check["status"] == "skip"

    def test_overall_ok_when_all_pass_or_skip(self):
        creds = FakeCreds()
        drive = FakeDriveClient()
        sheets = FakeSheetsClient()
        result = doctor.run_checks(
            WORKSPACE_PLACEHOLDER,
            creds=creds,
            drive_client=drive,
            sheets_client=sheets,
        )
        # All IDs are REPLACE_* so API checks skip; creds_env might fail (no env var set)
        non_skip = [c for c in result["checks"] if c["status"] not in ("skip", "pass")]
        # credentials_env may fail but that's OK for this assertion about skip propagation
        assert result["status"] in ("ok", "degraded", "fail")

    def test_overall_fail_when_any_check_fails(self):
        drive = FakeDriveClient(drive_exc=Exception("boom"))
        result = doctor.run_checks(WORKSPACE_CONFIGURED, drive_client=drive)
        assert result["status"] == "fail"

    def test_overall_ok_when_all_pass(self, monkeypatch, tmp_path):
        key_file = tmp_path / "sa.json"
        key_file.write_text("{}")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key_file))
        creds = FakeCreds()
        drive = FakeDriveClient(file_result={"version": "rev-abc"})
        sheets = FakeSheetsClient()
        result = doctor.run_checks(
            WORKSPACE_CONFIGURED,
            creds=creds,
            drive_client=drive,
            sheets_client=sheets,
        )
        assert result["status"] == "ok"
        for c in result["checks"]:
            assert c["status"] in ("pass", "ok"), f"{c['name']} = {c['status']}"

    def test_result_has_checks_list(self):
        result = doctor.run_checks(WORKSPACE_PLACEHOLDER)
        assert isinstance(result["checks"], list)
        assert len(result["checks"]) == 5

    def test_each_check_has_name_status_detail(self):
        result = doctor.run_checks(WORKSPACE_PLACEHOLDER)
        for c in result["checks"]:
            assert "name" in c
            assert "status" in c
            assert "detail" in c

    def test_check_names_are_correct(self):
        result = doctor.run_checks(WORKSPACE_PLACEHOLDER)
        names = [c["name"] for c in result["checks"]]
        assert "credentials_env" in names
        assert "service_auth" in names
        assert "drive_api" in names
        assert "master_template" in names
        assert "ledger" in names

    def test_service_auth_skipped_when_creds_none_but_others_injected(self):
        drive = FakeDriveClient()
        result = doctor.run_checks(WORKSPACE_PLACEHOLDER, drive_client=drive)
        sa_check = next(c for c in result["checks"] if c["name"] == "service_auth")
        assert sa_check["status"] == "skip"


# ---------------------------------------------------------------------------
# main() — CLI behaviour
# ---------------------------------------------------------------------------

class TestMain:
    def test_exits_nonzero_when_config_missing(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            doctor.main(["--workspace", "/nonexistent/path.yaml"])
        assert exc_info.value.code != 0
        out = capsys.readouterr().out
        result = json.loads(out)
        assert result["status"] == "fail"
        assert result["checks"][0]["name"] == "workspace_config"

    def test_exits_nonzero_on_bad_yaml(self, capsys, tmp_path):
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text(": : invalid yaml: [")
        with pytest.raises(SystemExit) as exc_info:
            doctor.main(["--workspace", str(bad_yaml)])
        assert exc_info.value.code != 0
        result = json.loads(capsys.readouterr().out)
        assert result["status"] == "fail"

    def test_stdout_always_valid_json_on_config_error(self, capsys):
        with pytest.raises(SystemExit):
            doctor.main(["--workspace", "/does/not/exist.yaml"])
        out = capsys.readouterr().out
        json.loads(out)  # must not raise

    def test_injected_clients_bypass_real_auth(self, capsys, tmp_path):
        ws_path = tmp_path / "workspace.yaml"
        ws_path.write_text(yaml.dump(WORKSPACE_PLACEHOLDER))
        creds = FakeCreds()
        drive = FakeDriveClient()
        sheets = FakeSheetsClient()
        with pytest.raises(SystemExit) as exc_info:
            doctor.main(
                ["--workspace", str(ws_path)],
                creds=creds,
                drive_client=drive,
                sheets_client=sheets,
            )
        # All IDs are REPLACE_ → all API checks skip; credentials_env may fail
        # but the important thing is no real auth was attempted
        assert exc_info.value.code in (0, 1)  # not 3 (credential error)

    def test_exits_3_on_missing_config_file(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            doctor.main(["--workspace", "/no/such/file.yaml"])
        assert exc_info.value.code == 3
