"""
test_module_imports.py — Verify the importable module API contracts (Issue #38).

Covers (AC-1, AC-2, AC-8):
  - Each of the four functions is importable with zero side effects (no
    stdout/stderr output, no sys.exit, no Google API calls).
  - inspect.signature() shows the required §11.4 parameter names and
    annotations for each function.
  - validate_request({}, {}) returns a dict with keys "valid" and "errors".
  - scan_template("fake_id", {"blocks": []}, fake_docs_client) returns a
    dict with key "summary".

No live Google API calls are made anywhere in this file (SB-05, architecture §9).
No credentials are required (SB-02).

Advances AD-20, TL-15, G-20.
"""

from __future__ import annotations

import inspect
import io
import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Path setup — mirrors the pattern used in every other unit test in this suite.
# ---------------------------------------------------------------------------

SCRIPTS_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "../../.claude/skills/document-assembly/scripts",
    )
)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Minimal fake Google Docs client for scan_template tests.
# ---------------------------------------------------------------------------


class _FakeDocuments:
    """Fake Docs API documents() sub-resource."""

    def __init__(self, document: dict | None = None) -> None:
        self._document = document or {"body": {"content": []}}

    def get(self, documentId=None):  # noqa: N803
        this = self

        class _Exec:
            def execute(self):
                return this._document

        return _Exec()


class _FakeDocsClient:
    """Minimal fake Docs v1 client (no network calls)."""

    def __init__(self, document: dict | None = None) -> None:
        self._docs = _FakeDocuments(document)

    def documents(self):
        return self._docs


# ---------------------------------------------------------------------------
# AC-1 — Import-time side effects
# ---------------------------------------------------------------------------


class TestNoImportSideEffects:
    """Each module must be importable without stdout/stderr output or sys.exit."""

    def _capture_import(self, module_name: str) -> tuple[str, str]:
        """Import *module_name* fresh and return (stdout_captured, stderr_captured)."""
        # Remove cached module so import runs fresh.
        sys.modules.pop(module_name, None)
        captured_out = io.StringIO()
        captured_err = io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = captured_out
        sys.stderr = captured_err
        try:
            __import__(module_name)
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
        return captured_out.getvalue(), captured_err.getvalue()

    def test_assemble_import_no_stdout(self):
        out, _ = self._capture_import("assemble")
        assert out == "", f"assemble produced stdout on import: {out!r}"

    def test_assemble_import_no_stderr(self):
        _, err = self._capture_import("assemble")
        assert err == "", f"assemble produced stderr on import: {err!r}"

    def test_review_import_no_stdout(self):
        out, _ = self._capture_import("review")
        assert out == "", f"review produced stdout on import: {out!r}"

    def test_review_import_no_stderr(self):
        _, err = self._capture_import("review")
        assert err == "", f"review produced stderr on import: {err!r}"

    def test_validate_request_import_no_stdout(self):
        out, _ = self._capture_import("validate_request")
        assert out == "", f"validate_request produced stdout on import: {out!r}"

    def test_validate_request_import_no_stderr(self):
        _, err = self._capture_import("validate_request")
        assert err == "", f"validate_request produced stderr on import: {err!r}"

    def test_scan_template_import_no_stdout(self):
        out, _ = self._capture_import("scan_template")
        assert out == "", f"scan_template produced stdout on import: {out!r}"

    def test_scan_template_import_no_stderr(self):
        _, err = self._capture_import("scan_template")
        assert err == "", f"scan_template produced stderr on import: {err!r}"


# ---------------------------------------------------------------------------
# AC-2 — Typed signatures match §11.4 contracts
# ---------------------------------------------------------------------------


class TestSignatureContracts:
    """inspect.signature() must expose the required parameter names and kinds."""

    def _get_params(self, fn) -> dict:
        """Return {name: Parameter} mapping from inspect.signature."""
        return dict(inspect.signature(fn).parameters)

    def _annotation_is(self, annotation, expected_type) -> bool:
        """Return True if *annotation* represents *expected_type*.

        Handles both actual type objects (e.g. ``dict``) and forward-reference
        strings (e.g. ``'dict'``) produced by ``from __future__ import
        annotations``.
        """
        if annotation is expected_type:
            return True
        if annotation is inspect.Parameter.empty:
            return False
        if isinstance(annotation, str):
            return annotation == expected_type.__name__
        return False

    # ---- assemble ----

    def test_assemble_has_request_param(self):
        from assemble import assemble  # noqa: PLC0415

        params = self._get_params(assemble)
        assert "request" in params, "assemble is missing 'request' parameter"

    def test_assemble_request_annotated_dict(self):
        from assemble import assemble  # noqa: PLC0415

        params = self._get_params(assemble)
        assert self._annotation_is(params["request"].annotation, dict)

    def test_assemble_has_workspace_cfg_param(self):
        from assemble import assemble  # noqa: PLC0415

        params = self._get_params(assemble)
        assert "workspace_cfg" in params, "assemble is missing 'workspace_cfg' parameter"

    def test_assemble_workspace_cfg_annotated_dict(self):
        from assemble import assemble  # noqa: PLC0415

        params = self._get_params(assemble)
        assert self._annotation_is(params["workspace_cfg"].annotation, dict)

    def test_assemble_has_dry_run_param_default_false(self):
        from assemble import assemble  # noqa: PLC0415

        params = self._get_params(assemble)
        assert "dry_run" in params, "assemble is missing 'dry_run' parameter"
        assert params["dry_run"].default is False

    def test_assemble_return_annotation_is_dict(self):
        from assemble import assemble  # noqa: PLC0415

        ret = inspect.signature(assemble).return_annotation
        assert self._annotation_is(ret, dict), (
            f"assemble return annotation is {ret!r}, expected dict"
        )

    # ---- review ----

    def test_review_has_job_id_param(self):
        from review import review  # noqa: PLC0415

        params = self._get_params(review)
        assert "job_id" in params, "review is missing 'job_id' parameter"

    def test_review_job_id_annotated_str(self):
        from review import review  # noqa: PLC0415

        params = self._get_params(review)
        assert self._annotation_is(params["job_id"].annotation, str)

    def test_review_has_decision_param(self):
        from review import review  # noqa: PLC0415

        params = self._get_params(review)
        assert "decision" in params, "review is missing 'decision' parameter"

    def test_review_decision_annotated_str(self):
        from review import review  # noqa: PLC0415

        params = self._get_params(review)
        assert self._annotation_is(params["decision"].annotation, str)

    def test_review_has_reason_param(self):
        from review import review  # noqa: PLC0415

        params = self._get_params(review)
        assert "reason" in params, "review is missing 'reason' parameter"

    def test_review_has_workspace_cfg_param(self):
        from review import review  # noqa: PLC0415

        params = self._get_params(review)
        assert "workspace_cfg" in params, "review is missing 'workspace_cfg' parameter"

    def test_review_workspace_cfg_annotated_dict(self):
        from review import review  # noqa: PLC0415

        params = self._get_params(review)
        assert self._annotation_is(params["workspace_cfg"].annotation, dict)

    def test_review_return_annotation_is_dict(self):
        from review import review  # noqa: PLC0415

        ret = inspect.signature(review).return_annotation
        assert self._annotation_is(ret, dict), (
            f"review return annotation is {ret!r}, expected dict"
        )

    # ---- validate_request ----

    def test_validate_request_has_request_param(self):
        from validate_request import validate_request  # noqa: PLC0415

        params = self._get_params(validate_request)
        assert "request" in params

    def test_validate_request_request_annotated_dict(self):
        from validate_request import validate_request  # noqa: PLC0415

        params = self._get_params(validate_request)
        assert self._annotation_is(params["request"].annotation, dict)

    def test_validate_request_has_recipe_param(self):
        from validate_request import validate_request  # noqa: PLC0415

        params = self._get_params(validate_request)
        assert "recipe" in params

    def test_validate_request_recipe_annotated_dict(self):
        from validate_request import validate_request  # noqa: PLC0415

        params = self._get_params(validate_request)
        assert self._annotation_is(params["recipe"].annotation, dict)

    def test_validate_request_return_annotation_is_dict(self):
        from validate_request import validate_request  # noqa: PLC0415

        ret = inspect.signature(validate_request).return_annotation
        assert self._annotation_is(ret, dict), (
            f"validate_request return annotation is {ret!r}, expected dict"
        )

    # ---- scan_template ----

    def test_scan_template_has_file_id_param(self):
        from scan_template import scan_template  # noqa: PLC0415

        params = self._get_params(scan_template)
        assert "file_id" in params

    def test_scan_template_file_id_annotated_str(self):
        from scan_template import scan_template  # noqa: PLC0415

        params = self._get_params(scan_template)
        assert self._annotation_is(params["file_id"].annotation, str)

    def test_scan_template_has_registry_param(self):
        from scan_template import scan_template  # noqa: PLC0415

        params = self._get_params(scan_template)
        assert "registry" in params

    def test_scan_template_registry_annotated_dict(self):
        from scan_template import scan_template  # noqa: PLC0415

        params = self._get_params(scan_template)
        assert self._annotation_is(params["registry"].annotation, dict)

    def test_scan_template_has_docs_client_param(self):
        from scan_template import scan_template  # noqa: PLC0415

        params = self._get_params(scan_template)
        assert "docs_client" in params

    def test_scan_template_return_annotation_is_dict(self):
        from scan_template import scan_template  # noqa: PLC0415

        ret = inspect.signature(scan_template).return_annotation
        assert self._annotation_is(ret, dict), (
            f"scan_template return annotation is {ret!r}, expected dict"
        )


# ---------------------------------------------------------------------------
# AC-8 — Callable function returns correct type
# ---------------------------------------------------------------------------


class TestCallableReturns:
    """Functions must return the correct type when called with minimal inputs."""

    def test_validate_request_empty_returns_dict(self):
        """AC-8(b): validate_request({}, {}) returns dict with 'valid' and 'errors'."""
        from validate_request import validate_request  # noqa: PLC0415

        result = validate_request({}, {})
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "valid" in result, f"'valid' key missing from result: {result}"
        assert "errors" in result, f"'errors' key missing from result: {result}"

    def test_validate_request_valid_key_is_bool(self):
        from validate_request import validate_request  # noqa: PLC0415

        result = validate_request({}, {})
        assert isinstance(result["valid"], bool)

    def test_validate_request_errors_key_is_list(self):
        from validate_request import validate_request  # noqa: PLC0415

        result = validate_request({}, {})
        assert isinstance(result["errors"], list)

    def test_validate_request_matching_family_key_valid(self):
        """A perfectly matching request+recipe should return valid=True."""
        from validate_request import validate_request  # noqa: PLC0415

        request = {"family_key": "test", "options": {}, "placeholder_values": {}}
        recipe = {
            "family_key": "test",
            "options": [],
            "rules": [],
            "defaults": {"include": []},
            "placeholder_map": {},
        }
        result = validate_request(request, recipe)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_validate_request_mismatched_family_key_invalid(self):
        from validate_request import validate_request  # noqa: PLC0415

        result = validate_request({"family_key": "a"}, {"family_key": "b"})
        assert result["valid"] is False
        assert len(result["errors"]) >= 1

    def test_scan_template_returns_dict_with_summary(self):
        """AC-8(c): scan_template("fake_id", {"blocks": []}, fake_client) has 'summary' key."""
        from scan_template import scan_template  # noqa: PLC0415

        fake_client = _FakeDocsClient({"body": {"content": []}})
        result = scan_template("fake_id", {"blocks": []}, fake_client)
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "summary" in result, f"'summary' key missing from result: {result}"

    def test_scan_template_summary_has_total_markers(self):
        from scan_template import scan_template  # noqa: PLC0415

        fake_client = _FakeDocsClient()
        result = scan_template("fake_id", {"blocks": []}, fake_client)
        assert "total_markers" in result["summary"]

    def test_scan_template_summary_has_issue_count(self):
        from scan_template import scan_template  # noqa: PLC0415

        fake_client = _FakeDocsClient()
        result = scan_template("fake_id", {"blocks": []}, fake_client)
        assert "issue_count" in result["summary"]

    def test_scan_template_empty_doc_no_markers(self):
        from scan_template import scan_template  # noqa: PLC0415

        fake_client = _FakeDocsClient({"body": {"content": []}})
        result = scan_template("doc_id_123", {"blocks": []}, fake_client)
        assert result["summary"]["total_markers"] == 0
        assert result["summary"]["issue_count"] == 0

    def test_scan_template_returns_file_id(self):
        from scan_template import scan_template  # noqa: PLC0415

        fake_client = _FakeDocsClient()
        result = scan_template("my_file_id", {"blocks": []}, fake_client)
        assert result.get("file_id") == "my_file_id"

    def test_assemble_is_callable(self):
        """AC-8(a): assemble is importable and callable with fake clients."""
        from assemble import assemble  # noqa: PLC0415

        assert callable(assemble)

    def test_review_is_callable(self):
        """AC-8(a): review is importable and callable."""
        from review import review  # noqa: PLC0415

        assert callable(review)

    def test_validate_request_is_callable(self):
        from validate_request import validate_request  # noqa: PLC0415

        assert callable(validate_request)

    def test_scan_template_is_callable(self):
        from scan_template import scan_template  # noqa: PLC0415

        assert callable(scan_template)


# ---------------------------------------------------------------------------
# AC-1 / TL-15 — No sys.exit at import time
# ---------------------------------------------------------------------------


class TestNoSysExitAtImport:
    """Importing the modules must not trigger sys.exit."""

    def _import_fresh(self, module_name: str) -> None:
        sys.modules.pop(module_name, None)
        __import__(module_name)

    def test_assemble_no_sys_exit_on_import(self):
        try:
            self._import_fresh("assemble")
        except SystemExit as exc:
            pytest.fail(f"assemble raised SystemExit({exc.code}) on import")

    def test_review_no_sys_exit_on_import(self):
        try:
            self._import_fresh("review")
        except SystemExit as exc:
            pytest.fail(f"review raised SystemExit({exc.code}) on import")

    def test_validate_request_no_sys_exit_on_import(self):
        try:
            self._import_fresh("validate_request")
        except SystemExit as exc:
            pytest.fail(f"validate_request raised SystemExit({exc.code}) on import")

    def test_scan_template_no_sys_exit_on_import(self):
        try:
            self._import_fresh("scan_template")
        except SystemExit as exc:
            pytest.fail(f"scan_template raised SystemExit({exc.code}) on import")
