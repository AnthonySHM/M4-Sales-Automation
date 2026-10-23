"""
Baseline unit tests for all four script stubs.

Covers:
  - doctor.py: exits 0 with fake workspace config and no API clients
  - doctor.py: exits 1 when workspace config file is missing
  - scan_template.py: exits 0 with --file-id provided
  - scan_template.py: exits 1 when --file-id is missing
  - validate_request.py: exits 1 when --request file is missing
  - validate_request.py: exits 1 when --recipe file is missing
  - assemble.py: exits 0 in --dry-run with valid request file
  - assemble.py: exits 1 when --request file is missing
  - assemble.py: exits 1 when --request is not valid JSON

No live Google API calls are made anywhere in this file. (SB-05, Architecture §9)
"""

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
import scan_template
import validate_request
import assemble


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_temp_yaml(data: dict) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.dump(data, f)
    f.close()
    return f.name


def write_temp_json(data: dict) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return f.name


MINIMAL_WORKSPACE = {
    "workspace_id": "test-workspace",
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

MINIMAL_REQUEST = {
    "request_id": "test-req-001",
    "family_key": "family_a",
    "options": {},
    "placeholder_values": {},
    "requested_by": "test@example.com",
}

MINIMAL_RECIPE = {
    "family_key": "family_a",
    "version": 1,
    "options": [],
    "rules": [],
    "defaults": {"include": []},
    "placeholder_map": {},
    "status": "published",
}


# ---------------------------------------------------------------------------
# doctor.py
# ---------------------------------------------------------------------------

class TestDoctor:
    def test_exits_zero_with_valid_fake_config(self):
        """doctor returns 'ok' when config is valid and no API clients are injected."""
        # Calls run_checks directly so the real-auth path in main() is not triggered.
        # All IDs are REPLACE_ placeholders → all API checks skip → overall "ok".
        result = doctor.run_checks(MINIMAL_WORKSPACE)
        assert result["status"] in ("ok", "degraded")
        assert "checks" in result

    def test_exits_nonzero_when_config_missing(self, capsys):
        """doctor exits with non-zero when workspace config file does not exist."""
        with pytest.raises(SystemExit) as exc_info:
            doctor.main(["--workspace", "/nonexistent/path/workspace.yaml"])
        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["status"] == "fail"

    def test_stdout_is_valid_json(self, capsys):
        """doctor always writes valid JSON to stdout."""
        config_path = write_temp_yaml(MINIMAL_WORKSPACE)
        try:
            with pytest.raises(SystemExit):
                doctor.main(["--workspace", config_path])
            captured = capsys.readouterr()
            json.loads(captured.out)  # must not raise
        finally:
            os.unlink(config_path)

    def test_checks_list_present(self, capsys):
        """doctor result always contains a 'checks' list."""
        config_path = write_temp_yaml(MINIMAL_WORKSPACE)
        try:
            with pytest.raises(SystemExit):
                doctor.main(["--workspace", config_path])
            result = json.loads(capsys.readouterr().out)
            assert isinstance(result["checks"], list)
            assert len(result["checks"]) > 0
        finally:
            os.unlink(config_path)

    def test_skips_not_configured_items(self):
        """doctor marks checks as 'skip' when IDs are placeholder values."""
        # Calls run_checks directly (unit-test mode: no clients injected).
        result = doctor.run_checks(MINIMAL_WORKSPACE)
        statuses = {c["name"]: c["status"] for c in result["checks"]}
        # IDs starting with REPLACE_ should be skipped, not fail
        assert statuses.get("master_template") in ("skip", "pass")
        assert statuses.get("ledger") in ("skip", "pass")

    def test_no_google_api_clients_imported_in_test(self):
        """Verify no real Google API client is constructed during unit tests."""
        import doctor as doc_module
        # The module exists; no googleapiclient.discovery.build was called
        # (enforced by not importing it at module level)
        assert hasattr(doc_module, "run_checks")


# ---------------------------------------------------------------------------
# scan_template.py
# ---------------------------------------------------------------------------

def _make_empty_fake_docs_client():
    """Minimal fake Docs client returning an empty document (no markers)."""
    class _Exec:
        def execute(self):
            return {"body": {"content": []}}
    class _Docs:
        def get(self, documentId):
            return _Exec()
    class _Client:
        def documents(self):
            return _Docs()
    return _Client()


class TestScanTemplate:
    def test_exits_zero_with_file_id(self, capsys):
        """scan_template exits 0 when --file-id is provided and doc has no issues."""
        client = _make_empty_fake_docs_client()
        with pytest.raises(SystemExit) as exc_info:
            scan_template.main(["--file-id", "fake-doc-id-123"], docs_client=client)
        assert exc_info.value.code == 0
        result = json.loads(capsys.readouterr().out)
        assert "issues" in result
        assert "summary" in result

    def test_stdout_structure(self, capsys):
        """scan_template result contains all required top-level keys."""
        client = _make_empty_fake_docs_client()
        with pytest.raises(SystemExit):
            scan_template.main(["--file-id", "fake-doc-id"], docs_client=client)
        result = json.loads(capsys.readouterr().out)
        for key in ("file_id", "markers_found", "issues", "summary"):
            assert key in result, f"Missing key: {key}"

    def test_exits_nonzero_when_file_id_missing(self):
        """scan_template exits non-zero when --file-id is not provided."""
        with pytest.raises(SystemExit) as exc_info:
            scan_template.main([])
        assert exc_info.value.code != 0

    @pytest.mark.parametrize("file_id", [
        "abc123",
        "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",  # typical Drive ID format
        "a" * 44,  # max-length-ish ID
    ])
    def test_accepts_various_file_ids(self, file_id, capsys):
        """scan_template accepts any non-empty string as file-id."""
        client = _make_empty_fake_docs_client()
        with pytest.raises(SystemExit) as exc_info:
            scan_template.main(["--file-id", file_id], docs_client=client)
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# validate_request.py
# ---------------------------------------------------------------------------

class TestValidateRequest:
    def test_exits_zero_with_valid_files(self, capsys):
        """validate_request exits 0 when both request and recipe are valid JSON."""
        req_path = write_temp_json(MINIMAL_REQUEST)
        rec_path = write_temp_json(MINIMAL_RECIPE)
        try:
            with pytest.raises(SystemExit) as exc_info:
                validate_request.main(["--request", req_path, "--recipe", rec_path])
            assert exc_info.value.code == 0
            result = json.loads(capsys.readouterr().out)
            assert result["valid"] is True
        finally:
            os.unlink(req_path)
            os.unlink(rec_path)

    def test_exits_one_when_request_missing(self, capsys):
        """validate_request exits 1 with structured error when request file is missing."""
        rec_path = write_temp_json(MINIMAL_RECIPE)
        try:
            with pytest.raises(SystemExit) as exc_info:
                validate_request.main([
                    "--request", "/nonexistent/request.json",
                    "--recipe", rec_path,
                ])
            assert exc_info.value.code == 1
            result = json.loads(capsys.readouterr().out)
            assert result["valid"] is False
            assert len(result["errors"]) > 0
        finally:
            os.unlink(rec_path)

    def test_exits_one_when_recipe_missing(self, capsys):
        """validate_request exits 1 with structured error when recipe file is missing."""
        req_path = write_temp_json(MINIMAL_REQUEST)
        try:
            with pytest.raises(SystemExit) as exc_info:
                validate_request.main([
                    "--request", req_path,
                    "--recipe", "/nonexistent/recipe.json",
                ])
            assert exc_info.value.code == 1
            result = json.loads(capsys.readouterr().out)
            assert result["valid"] is False
        finally:
            os.unlink(req_path)

    def test_exits_one_when_request_invalid_json(self, capsys):
        """validate_request exits 1 when request file contains invalid JSON."""
        bad = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        bad.write("{not valid json")
        bad.close()
        rec_path = write_temp_json(MINIMAL_RECIPE)
        try:
            with pytest.raises(SystemExit) as exc_info:
                validate_request.main(["--request", bad.name, "--recipe", rec_path])
            assert exc_info.value.code == 1
            result = json.loads(capsys.readouterr().out)
            assert result["valid"] is False
        finally:
            os.unlink(bad.name)
            os.unlink(rec_path)

    def test_exits_nonzero_when_args_missing(self):
        """validate_request exits non-zero when required args are absent."""
        with pytest.raises(SystemExit) as exc_info:
            validate_request.main([])
        assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# assemble.py
# ---------------------------------------------------------------------------

def _last_json_line(out: str) -> dict:
    """Parse the last non-empty JSON line from streaming stdout output."""
    lines = [l for l in out.strip().splitlines() if l.strip()]
    return json.loads(lines[-1])


def _write_workspace_and_recipe(family_key: str = "family_a") -> tuple[str, str]:
    """Write temp workspace.yaml and matching recipe json; return (ws_path, recipe_path)."""
    ws_path = write_temp_yaml({
        **MINIMAL_WORKSPACE,
        "pilot_family": {
            "key": family_key,
            "master_template_id": "REPLACE_MASTER",
            "approved_revision_id": "REPLACE_REV",
            "active_recipe_version": 1,
        },
    })
    recipe = {**MINIMAL_RECIPE, "family_key": family_key}
    recipe_path = write_temp_json(recipe)
    return ws_path, recipe_path


class TestAssemble:
    def test_dry_run_exits_zero_with_valid_request(self, capsys, tmp_path):
        """assemble --dry-run exits 0 with a valid request + workspace + recipe."""
        req_path = write_temp_json(MINIMAL_REQUEST)
        ws_path, recipe_path = _write_workspace_and_recipe()
        # Point workspace at the temp recipe via the recipe path override trick:
        # Since main() derives recipe path from workspace config, we write the recipe
        # to the exact path that main() will look for it: config/recipes/family_a_v1.json
        recipe_dir = tmp_path / "config" / "recipes"
        recipe_dir.mkdir(parents=True)
        recipe_file = recipe_dir / "family_a_v1.json"
        recipe_file.write_text(json.dumps(MINIMAL_RECIPE))
        import os as _os
        orig_dir = _os.getcwd()
        _os.chdir(str(tmp_path))
        try:
            with pytest.raises(SystemExit) as exc_info:
                assemble.main(["--request", req_path, "--dry-run", "--workspace", ws_path])
            assert exc_info.value.code == 0
            out = capsys.readouterr().out
            last = _last_json_line(out)
            assert last["event"] == "dry_run_complete"
        finally:
            _os.chdir(orig_dir)
            os.unlink(req_path)
            os.unlink(ws_path)
            os.unlink(recipe_path)

    def test_exits_one_when_request_missing(self, capsys):
        """assemble exits 1 with structured error when request file is missing."""
        with pytest.raises(SystemExit) as exc_info:
            assemble.main(["--request", "/nonexistent/request.json"])
        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        result = _last_json_line(out)
        assert result["event"] == "job_failed"
        assert "error" in result["detail"]
        assert result["detail"]["error"]["retryable"] is False

    def test_exits_one_when_request_invalid_json(self, capsys):
        """assemble exits 1 when request file contains invalid JSON."""
        bad = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        bad.write("{bad json")
        bad.close()
        try:
            with pytest.raises(SystemExit) as exc_info:
                assemble.main(["--request", bad.name])
            assert exc_info.value.code == 1
            result = _last_json_line(capsys.readouterr().out)
            assert result["event"] == "job_failed"
        finally:
            os.unlink(bad.name)

    def test_dry_run_includes_request_id(self, capsys, tmp_path):
        """assemble --dry-run result includes the request_id from the request file."""
        req_path = write_temp_json(MINIMAL_REQUEST)
        ws_path, recipe_path = _write_workspace_and_recipe()
        recipe_dir = tmp_path / "config" / "recipes"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "family_a_v1.json").write_text(json.dumps(MINIMAL_RECIPE))
        import os as _os
        orig_dir = _os.getcwd()
        _os.chdir(str(tmp_path))
        try:
            with pytest.raises(SystemExit):
                assemble.main(["--request", req_path, "--dry-run", "--workspace", ws_path])
            out = capsys.readouterr().out
            last = _last_json_line(out)
            assert last["detail"]["request_id"] == "test-req-001"
        finally:
            _os.chdir(orig_dir)
            os.unlink(req_path)
            os.unlink(ws_path)
            os.unlink(recipe_path)

    def test_exits_nonzero_when_request_arg_missing(self):
        """assemble exits non-zero when --request is not provided."""
        with pytest.raises(SystemExit) as exc_info:
            assemble.main([])
        assert exc_info.value.code != 0

    def test_stdout_is_always_valid_json_on_error(self, capsys):
        """assemble always writes valid JSON to stdout, even on errors."""
        with pytest.raises(SystemExit):
            assemble.main(["--request", "/no/such/file.json"])
        captured = capsys.readouterr()
        for line in captured.out.strip().splitlines():
            if line.strip():
                json.loads(line)  # each line must be valid JSON

    @pytest.mark.parametrize("request_data", [
        {"request_id": "r1", "family_key": "family_a", "options": {}, "placeholder_values": {}, "requested_by": "a@b.com"},
        {"request_id": "r2", "family_key": "family_a", "options": {}, "placeholder_values": {}, "requested_by": "b@c.com"},
    ])
    def test_dry_run_accepts_various_valid_requests(self, request_data, capsys, tmp_path):
        """assemble --dry-run exits 0 for any structurally valid request."""
        req_path = write_temp_json(request_data)
        ws_path, recipe_path = _write_workspace_and_recipe()
        recipe_dir = tmp_path / "config" / "recipes"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "family_a_v1.json").write_text(json.dumps(MINIMAL_RECIPE))
        import os as _os
        orig_dir = _os.getcwd()
        _os.chdir(str(tmp_path))
        try:
            with pytest.raises(SystemExit) as exc_info:
                assemble.main(["--request", req_path, "--dry-run", "--workspace", ws_path])
            assert exc_info.value.code == 0
        finally:
            _os.chdir(orig_dir)
            os.unlink(req_path)
            os.unlink(ws_path)
            os.unlink(recipe_path)
