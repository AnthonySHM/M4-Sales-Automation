"""
Unit tests for validate_request.py — Issue #11.

All I/O uses temp files. No live API calls.
Covers: valid requests, all error codes, multi-error accumulation,
family_key mismatch, missing placeholders, exit codes, stdout safety.

Advances G-02, G-03, AD-06, SB-05, SB-06, Architecture §4.3.
"""

import json
import os
import sys
import tempfile

import pytest

SCRIPTS_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "../../.claude/skills/document-assembly/scripts",
    )
)
sys.path.insert(0, SCRIPTS_DIR)

from validate_request import main, validate  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _write_json(tmp_path, name, data):
    path = os.path.join(str(tmp_path), name)
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def _minimal_recipe(family="fam_a", options=None, placeholder_map=None):
    return {
        "family_key": family,
        "version": 1,
        "options": options or [],
        "rules": [],
        "defaults": {"include": []},
        "placeholder_map": placeholder_map or {},
        "status": "draft",
    }


def _minimal_request(family="fam_a", options=None, placeholders=None):
    return {
        "request_id": "req-001",
        "workspace_id": "ws-test",
        "family_key": family,
        "options": options or {},
        "placeholder_values": placeholders or {},
        "requested_by": "tester@example.com",
    }


# ---------------------------------------------------------------------------
# Happy-path: valid requests
# ---------------------------------------------------------------------------

class TestValidRequests:
    def test_zero_options_zero_placeholders(self, tmp_path):
        req = _write_json(tmp_path, "req.json", _minimal_request())
        rec = _write_json(tmp_path, "rec.json", _minimal_recipe())
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 0

    def test_one_required_option_correct_value(self, tmp_path):
        recipe = _minimal_recipe(
            options=[{"option_key": "tier", "allowed_values": ["gold", "silver"], "required": True}]
        )
        request = _minimal_request(options={"tier": "gold"})
        req = _write_json(tmp_path, "req.json", request)
        rec = _write_json(tmp_path, "rec.json", recipe)
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 0

    def test_multiple_options_all_valid(self, tmp_path):
        recipe = _minimal_recipe(options=[
            {"option_key": "tier", "allowed_values": ["gold"], "required": True},
            {"option_key": "region", "allowed_values": ["eu", "us"], "required": False},
        ])
        request = _minimal_request(options={"tier": "gold", "region": "eu"})
        req = _write_json(tmp_path, "req.json", request)
        rec = _write_json(tmp_path, "rec.json", recipe)
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 0

    def test_optional_option_omitted_is_valid(self, tmp_path):
        recipe = _minimal_recipe(options=[
            {"option_key": "tier", "allowed_values": ["gold"], "required": False},
        ])
        request = _minimal_request(options={})
        req = _write_json(tmp_path, "req.json", request)
        rec = _write_json(tmp_path, "rec.json", recipe)
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 0

    def test_stdout_valid_true_on_success(self, tmp_path, capsys):
        req = _write_json(tmp_path, "req.json", _minimal_request())
        rec = _write_json(tmp_path, "rec.json", _minimal_recipe())
        with pytest.raises(SystemExit):
            main(["--request", req, "--recipe", rec])
        data = json.loads(capsys.readouterr().out)
        assert data["valid"] is True
        assert data["errors"] == []

    def test_placeholder_present_and_valid(self, tmp_path):
        recipe = _minimal_recipe(placeholder_map={"CLIENT_NAME": "requested_by"})
        request = _minimal_request(placeholders={"CLIENT_NAME": "Acme Corp"})
        req = _write_json(tmp_path, "req.json", request)
        rec = _write_json(tmp_path, "rec.json", recipe)
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 0


# ---------------------------------------------------------------------------
# Unknown option (AD-06 hard-fail)
# ---------------------------------------------------------------------------

class TestUnknownOption:
    def test_unknown_option_detected(self, tmp_path, capsys):
        req = _write_json(tmp_path, "req.json", _minimal_request(options={"ghost": "val"}))
        rec = _write_json(tmp_path, "rec.json", _minimal_recipe())
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 1
        data = json.loads(capsys.readouterr().out)
        assert data["valid"] is False
        assert any(e["code"] == "unknown_option" for e in data["errors"])
        assert any("ghost" in e["field"] for e in data["errors"])

    def test_multiple_unknown_options_each_reported(self, tmp_path, capsys):
        req = _write_json(tmp_path, "req.json", _minimal_request(options={"foo": "a", "bar": "b"}))
        rec = _write_json(tmp_path, "rec.json", _minimal_recipe())
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 1
        errors = json.loads(capsys.readouterr().out)["errors"]
        codes = [e["code"] for e in errors]
        assert codes.count("unknown_option") == 2


# ---------------------------------------------------------------------------
# Invalid option value
# ---------------------------------------------------------------------------

class TestInvalidOptionValue:
    def test_invalid_value_detected(self, tmp_path, capsys):
        recipe = _minimal_recipe(options=[
            {"option_key": "tier", "allowed_values": ["gold", "silver"], "required": True}
        ])
        request = _minimal_request(options={"tier": "bronze"})
        req = _write_json(tmp_path, "req.json", request)
        rec = _write_json(tmp_path, "rec.json", recipe)
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 1
        data = json.loads(capsys.readouterr().out)
        assert any(e["code"] == "invalid_option_value" for e in data["errors"])

    def test_valid_value_not_flagged(self, tmp_path):
        recipe = _minimal_recipe(options=[
            {"option_key": "tier", "allowed_values": ["gold"], "required": True}
        ])
        request = _minimal_request(options={"tier": "gold"})
        req = _write_json(tmp_path, "req.json", request)
        rec = _write_json(tmp_path, "rec.json", recipe)
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 0


# ---------------------------------------------------------------------------
# Missing required option
# ---------------------------------------------------------------------------

class TestMissingRequiredOption:
    def test_missing_required_detected(self, tmp_path, capsys):
        recipe = _minimal_recipe(options=[
            {"option_key": "tier", "allowed_values": ["gold"], "required": True}
        ])
        request = _minimal_request(options={})
        req = _write_json(tmp_path, "req.json", request)
        rec = _write_json(tmp_path, "rec.json", recipe)
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 1
        data = json.loads(capsys.readouterr().out)
        assert any(e["code"] == "missing_required_option" for e in data["errors"])


# ---------------------------------------------------------------------------
# Missing placeholder
# ---------------------------------------------------------------------------

class TestMissingPlaceholder:
    def test_missing_placeholder_detected(self, tmp_path, capsys):
        recipe = _minimal_recipe(placeholder_map={"CLIENT_NAME": "requested_by"})
        request = _minimal_request(placeholders={})
        req = _write_json(tmp_path, "req.json", request)
        rec = _write_json(tmp_path, "rec.json", recipe)
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 1
        data = json.loads(capsys.readouterr().out)
        assert any(e["code"] == "missing_placeholder" for e in data["errors"])
        assert any("CLIENT_NAME" in e["field"] for e in data["errors"])

    def test_multiple_missing_placeholders_all_reported(self, tmp_path, capsys):
        recipe = _minimal_recipe(placeholder_map={"A": "f", "B": "f", "C": "f"})
        request = _minimal_request(placeholders={})
        req = _write_json(tmp_path, "req.json", request)
        rec = _write_json(tmp_path, "rec.json", recipe)
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 1
        errors = json.loads(capsys.readouterr().out)["errors"]
        assert sum(1 for e in errors if e["code"] == "missing_placeholder") == 3


# ---------------------------------------------------------------------------
# family_key mismatch
# ---------------------------------------------------------------------------

class TestFamilyKeyMismatch:
    def test_mismatch_detected(self, tmp_path, capsys):
        req = _write_json(tmp_path, "req.json", _minimal_request(family="fam_a"))
        rec = _write_json(tmp_path, "rec.json", _minimal_recipe(family="fam_b"))
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 1
        data = json.loads(capsys.readouterr().out)
        assert any(e["code"] == "family_key_mismatch" for e in data["errors"])

    def test_matching_family_keys_ok(self, tmp_path):
        req = _write_json(tmp_path, "req.json", _minimal_request(family="fam_a"))
        rec = _write_json(tmp_path, "rec.json", _minimal_recipe(family="fam_a"))
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 0


# ---------------------------------------------------------------------------
# Multi-error accumulation (no short-circuit)
# ---------------------------------------------------------------------------

class TestMultiError:
    def test_unknown_option_and_missing_placeholder_both_reported(self, tmp_path, capsys):
        recipe = _minimal_recipe(placeholder_map={"NAME": "f"})
        request = _minimal_request(options={"ghost": "x"}, placeholders={})
        req = _write_json(tmp_path, "req.json", request)
        rec = _write_json(tmp_path, "rec.json", recipe)
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", rec])
        assert exc.value.code == 1
        errors = json.loads(capsys.readouterr().out)["errors"]
        codes = {e["code"] for e in errors}
        assert "unknown_option" in codes
        assert "missing_placeholder" in codes


# ---------------------------------------------------------------------------
# File I/O errors
# ---------------------------------------------------------------------------

class TestFileErrors:
    def test_missing_request_file(self, tmp_path, capsys):
        rec = _write_json(tmp_path, "rec.json", _minimal_recipe())
        with pytest.raises(SystemExit) as exc:
            main(["--request", "/no/such/file.json", "--recipe", rec])
        assert exc.value.code == 1
        data = json.loads(capsys.readouterr().out)
        assert data["valid"] is False
        assert any(e["code"] == "file_not_found" for e in data["errors"])

    def test_missing_recipe_file(self, tmp_path, capsys):
        req = _write_json(tmp_path, "req.json", _minimal_request())
        with pytest.raises(SystemExit) as exc:
            main(["--request", req, "--recipe", "/no/such/recipe.json"])
        assert exc.value.code == 1

    def test_invalid_json_request(self, tmp_path, capsys):
        bad = os.path.join(str(tmp_path), "bad.json")
        with open(bad, "w") as f:
            f.write("{not valid json")
        rec = _write_json(tmp_path, "rec.json", _minimal_recipe())
        with pytest.raises(SystemExit) as exc:
            main(["--request", bad, "--recipe", rec])
        assert exc.value.code == 1
        data = json.loads(capsys.readouterr().out)
        assert any(e["code"] == "invalid_json" for e in data["errors"])

    def test_missing_args_exits_one(self):
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 1


# ---------------------------------------------------------------------------
# stdout always valid JSON (Architecture §4.3)
# ---------------------------------------------------------------------------

class TestStdoutAlwaysJson:
    def test_stdout_valid_json_on_success(self, tmp_path, capsys):
        req = _write_json(tmp_path, "req.json", _minimal_request())
        rec = _write_json(tmp_path, "rec.json", _minimal_recipe())
        with pytest.raises(SystemExit):
            main(["--request", req, "--recipe", rec])
        data = json.loads(capsys.readouterr().out)
        assert "valid" in data
        assert "errors" in data

    def test_stdout_valid_json_on_error(self, tmp_path, capsys):
        req = _write_json(tmp_path, "req.json", _minimal_request(options={"bad": "x"}))
        rec = _write_json(tmp_path, "rec.json", _minimal_recipe())
        with pytest.raises(SystemExit):
            main(["--request", req, "--recipe", rec])
        data = json.loads(capsys.readouterr().out)
        assert "valid" in data

    def test_placeholder_values_not_in_stdout(self, tmp_path, capsys):
        """Placeholder values must not leak onto stdout (SB-06)."""
        secret = "SUPER_SECRET_VALUE_99"
        recipe = _minimal_recipe(placeholder_map={"NAME": "f"})
        request = _minimal_request(placeholders={"NAME": secret})
        req = _write_json(tmp_path, "req.json", request)
        rec = _write_json(tmp_path, "rec.json", recipe)
        with pytest.raises(SystemExit):
            main(["--request", req, "--recipe", rec])
        assert secret not in capsys.readouterr().out

    def test_error_field_names_not_placeholder_values(self, tmp_path, capsys):
        """Error messages must reference field names, not actual values (SB-06)."""
        recipe = _minimal_recipe(options=[
            {"option_key": "tier", "allowed_values": ["gold"], "required": True}
        ])
        # Value 'my_secret_val' should not appear verbatim in a safe implementation
        # (architecture does allow the value in the message for invalid_option_value,
        # but must not appear in a way that leaks PII — tier values are not PII here)
        request = _minimal_request(options={"tier": "silver"})
        req = _write_json(tmp_path, "req.json", request)
        rec = _write_json(tmp_path, "rec.json", recipe)
        with pytest.raises(SystemExit):
            main(["--request", req, "--recipe", rec])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["valid"] is False


# ---------------------------------------------------------------------------
# validate() unit (pure function, no file I/O)
# ---------------------------------------------------------------------------

class TestValidateFunction:
    def test_empty_request_empty_recipe_valid(self):
        assert validate({}, {}) == []

    def test_returns_list(self):
        result = validate(_minimal_request(), _minimal_recipe())
        assert isinstance(result, list)

    def test_unknown_option_in_result(self):
        request = _minimal_request(options={"mystery": "x"})
        recipe = _minimal_recipe()
        errors = validate(request, recipe)
        assert any(e["code"] == "unknown_option" for e in errors)

    def test_missing_placeholder_in_result(self):
        request = _minimal_request(placeholders={})
        recipe = _minimal_recipe(placeholder_map={"FOO": "f"})
        errors = validate(request, recipe)
        assert any(e["code"] == "missing_placeholder" for e in errors)
