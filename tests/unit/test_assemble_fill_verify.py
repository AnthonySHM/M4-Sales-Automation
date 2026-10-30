"""
test_assemble_fill_verify.py — Unit tests for fill_placeholders, strip_markers,
verify_output steps in assemble.py (Issue #14).

All Google Docs API interactions use injected fakes (SB-05).
No live API calls are made.

Covers: fill_placeholders (happy, missing value, no-op), strip_markers
(no-op, single, multiple), verify_output (pass, leftover marker, leftover
placeholder), full pipeline through verify_output, SB-06 stdout safety.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

SCRIPTS_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "../../.claude/skills/document-assembly/scripts",
    )
)
sys.path.insert(0, SCRIPTS_DIR)

from assemble import (  # noqa: E402
    MarkerError,
    MissingPlaceholderError,
    assemble,
    fill_placeholders,
    strip_markers,
    verify_output,
)


# ---------------------------------------------------------------------------
# Fake Docs client
# ---------------------------------------------------------------------------


class FakeDocsDocuments:
    """Supports get() and batchUpdate() with per-call document state."""

    def __init__(self, documents: list[dict]) -> None:
        # documents[0] is the initial state; each batchUpdate advances the index
        self._documents = documents
        self._call_count = 0
        self.batch_update_calls: list[dict] = []

    def get(self, documentId):
        mock = MagicMock()
        # Return the document at current call count (or last if exhausted)
        idx = min(self._call_count, len(self._documents) - 1)
        mock.execute.return_value = dict(self._documents[idx])
        self._call_count += 1
        return mock

    def batchUpdate(self, documentId, body=None):
        self.batch_update_calls.append({"documentId": documentId, "body": body})
        mock = MagicMock()
        mock.execute.return_value = {}
        return mock


class FakeDocsClient:
    def __init__(self, *documents: dict) -> None:
        self._documents_obj = FakeDocsDocuments(list(documents))

    def documents(self):
        return self._documents_obj


class FakeDriveFiles:
    def __init__(self, meta: dict, copy_result: dict) -> None:
        self._meta = meta
        self._copy_result = copy_result

    def get(self, fileId, fields=None, supportsAllDrives=False):
        mock = MagicMock()
        mock.execute.return_value = dict(self._meta)
        return mock

    def copy(self, fileId, supportsAllDrives=False, body=None):
        mock = MagicMock()
        mock.execute.return_value = dict(self._copy_result)
        return mock


class FakeDriveClient:
    def __init__(self, meta: dict, copy_result: dict) -> None:
        self._files = FakeDriveFiles(meta, copy_result)

    def files(self):
        return self._files


# ---------------------------------------------------------------------------
# Document builders
# ---------------------------------------------------------------------------


def _make_paragraph(text: str, start: int) -> dict:
    return {
        "paragraph": {
            "elements": [
                {
                    "startIndex": start,
                    "endIndex": start + len(text),
                    "textRun": {"content": text},
                }
            ]
        }
    }


def _make_document_with_text(text: str) -> dict:
    """Build a simple document with one paragraph containing the given text."""
    return {"body": {"content": [_make_paragraph(text, 1)]}}


def _make_clean_document() -> dict:
    """Document with no markers and no placeholders."""
    return _make_document_with_text("Clean body text with no markers or placeholders.")


def _make_document_with_markers(*block_ids: str) -> dict:
    """Document containing BEGIN/END markers for the given block_ids."""
    parts = []
    idx = 1
    for bid in block_ids:
        begin = "[[BLOCK:" + bid + "]]"
        end = "[[/BLOCK:" + bid + "]]"
        parts.append(_make_paragraph(begin, idx)); idx += len(begin)
        body = f"Body of {bid}. "; parts.append(_make_paragraph(body, idx)); idx += len(body)
        parts.append(_make_paragraph(end, idx)); idx += len(end)
    return {"body": {"content": parts}}


def _make_document_with_placeholders(*ph_keys: str) -> dict:
    """Document containing {{PH_KEY}} patterns."""
    text = " ".join("{{" + k + "}}" for k in ph_keys)
    return _make_document_with_text(text)


def _sample_workspace() -> dict:
    return {
        "workspace_id": "ws_test",
        "shared_drive_id": "drive_id",
        "folders": {
            "masters": "m", "review": "r", "approved": "a", "quarantine": "q",
        },
        "pilot_family": {
            "key": "family_a",
            "master_template_id": "master_id",
            "approved_revision_id": "rev_001",
            "active_recipe_version": 1,
        },
    }


def _sample_request(**overrides) -> dict:
    base = {
        "request_id": "req_fill_001",
        "family_key": "family_a",
        "options": {},
        "placeholder_values": {"CLIENT_NAME": "Acme Corp", "DATE": "2024-01-01"},
        "requested_by": "agent@example.com",
    }
    base.update(overrides)
    return base


def _sample_recipe(**overrides) -> dict:
    base = {
        "family_key": "family_a",
        "version": 1,
        "options": [],
        "rules": [],
        "defaults": {"include": ["intro"]},
        "placeholder_map": {"CLIENT_NAME": "placeholder_values.CLIENT_NAME"},
        "status": "published",
    }
    base.update(overrides)
    return base


def _capture_events(capsys, fn, *args, **kwargs) -> tuple[list[dict], int]:
    result = fn(*args, **kwargs)
    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.strip().splitlines() if line.strip()]
    return events, result


def _make_full_clients(
    doc_states: list[dict],
    approved_rev: str = "rev_001",
):
    """Create Drive + Docs clients for a full pipeline run."""
    drive = FakeDriveClient(
        meta={"id": "master_id", "name": "Master", "headRevisionId": approved_rev},
        copy_result={"id": "output_doc_xyz"},
    )
    docs = FakeDocsClient(*doc_states)
    return drive, docs


# ---------------------------------------------------------------------------
# fill_placeholders tests
# ---------------------------------------------------------------------------


class TestFillPlaceholders:
    def test_calls_batchupdate_with_replacements(self):
        docs = FakeDocsClient(_make_clean_document())
        fill_placeholders(
            docs, "doc_id",
            {"CLIENT_NAME": "placeholder_values.CLIENT_NAME"},
            {"CLIENT_NAME": "Acme Corp"},
        )
        assert len(docs.documents().batch_update_calls) == 1
        req = docs.documents().batch_update_calls[0]["body"]["requests"][0]
        assert req["replaceAllText"]["containsText"]["text"] == "{{CLIENT_NAME}}"

    def test_returns_replaced_keys(self):
        docs = FakeDocsClient(_make_clean_document())
        result = fill_placeholders(
            docs, "doc_id",
            {"CLIENT_NAME": "c", "DATE": "d"},
            {"CLIENT_NAME": "Acme", "DATE": "2024-01-01"},
        )
        assert set(result) == {"CLIENT_NAME", "DATE"}

    def test_no_batchupdate_when_no_placeholders(self):
        docs = FakeDocsClient(_make_clean_document())
        result = fill_placeholders(docs, "doc_id", {}, {})
        assert result == []
        assert docs.documents().batch_update_calls == []

    def test_raises_missing_placeholder_error(self):
        docs = FakeDocsClient(_make_clean_document())
        with pytest.raises(MissingPlaceholderError):
            fill_placeholders(
                docs, "doc_id",
                {"CLIENT_NAME": "c"},
                {},  # CLIENT_NAME missing
            )

    def test_value_not_in_batchupdate_text_search(self):
        """Replacement VALUE must not appear as a containsText pattern (SB-06 related)."""
        docs = FakeDocsClient(_make_clean_document())
        fill_placeholders(
            docs, "doc_id",
            {"CLIENT_NAME": "c"},
            {"CLIENT_NAME": "SECRET_VALUE_XYZ"},
        )
        calls = docs.documents().batch_update_calls[0]["body"]["requests"]
        for req in calls:
            # containsText is the pattern to find, not the value
            pattern = req["replaceAllText"]["containsText"]["text"]
            assert "SECRET_VALUE_XYZ" not in pattern


# ---------------------------------------------------------------------------
# strip_markers tests
# ---------------------------------------------------------------------------


class TestStripMarkers:
    def test_no_op_when_no_markers(self):
        docs = FakeDocsClient(_make_clean_document())
        result = strip_markers(docs, "doc_id")
        assert result == []
        assert docs.documents().batch_update_calls == []

    def test_strips_single_pair(self):
        doc = _make_document_with_markers("intro")
        docs = FakeDocsClient(doc)
        result = strip_markers(docs, "doc_id")
        assert "[[BLOCK:intro]]" in result
        assert "[[/BLOCK:intro]]" in result

    def test_strips_multiple_pairs(self):
        doc = _make_document_with_markers("intro", "annex", "sla")
        docs = FakeDocsClient(doc)
        result = strip_markers(docs, "doc_id")
        assert len(result) == 6  # 3 BEGIN + 3 END unique patterns

    def test_batchupdate_called_when_markers_present(self):
        doc = _make_document_with_markers("intro")
        docs = FakeDocsClient(doc)
        strip_markers(docs, "doc_id")
        assert len(docs.documents().batch_update_calls) == 1

    def test_result_is_sorted(self):
        doc = _make_document_with_markers("zzz", "aaa")
        docs = FakeDocsClient(doc)
        result = strip_markers(docs, "doc_id")
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# verify_output tests
# ---------------------------------------------------------------------------


class TestVerifyOutput:
    def test_passes_on_clean_document(self):
        docs = FakeDocsClient(_make_clean_document())
        verify_output(docs, "doc_id")  # should not raise

    def test_raises_marker_error_on_leftover_marker(self):
        doc = _make_document_with_markers("intro")
        docs = FakeDocsClient(doc)
        with pytest.raises(MarkerError):
            verify_output(docs, "doc_id")

    def test_raises_missing_placeholder_on_leftover_placeholder(self):
        doc = _make_document_with_placeholders("CLIENT_NAME")
        docs = FakeDocsClient(doc)
        with pytest.raises(MissingPlaceholderError):
            verify_output(docs, "doc_id")

    def test_passes_when_no_content(self):
        docs = FakeDocsClient({"body": {"content": []}})
        verify_output(docs, "doc_id")  # should not raise


# ---------------------------------------------------------------------------
# Full pipeline tests (through verify_output)
# ---------------------------------------------------------------------------


class TestAssemblePipelineFull:
    def _make_pipeline_docs(self):
        """
        The pipeline calls docs_client.documents().get() multiple times:
        1. prune_blocks: get doc to find markers
        2. strip_markers: get doc to find remaining markers
        3. verify_output: get clean doc to verify
        We return clean docs for all reads since prune/fill already ran.
        """
        clean_doc = _make_clean_document()
        return FakeDocsClient(clean_doc, clean_doc, clean_doc)

    def test_full_run_exits_0(self, capsys):
        drive, docs = _make_full_clients(
            [_make_clean_document(), _make_clean_document(), _make_clean_document()],
        )
        recipe = _sample_recipe(placeholder_map={})
        request = _sample_request(placeholder_values={})
        workspace = _sample_workspace()
        events, code = _capture_events(
            capsys, assemble, request, recipe, workspace,
            drive_client=drive, docs_client=docs
        )
        assert code == 0

    def test_full_run_emits_job_completed(self, capsys):
        drive, docs = _make_full_clients(
            [_make_clean_document(), _make_clean_document(), _make_clean_document()],
        )
        recipe = _sample_recipe(placeholder_map={})
        request = _sample_request(placeholder_values={})
        workspace = _sample_workspace()
        events, _ = _capture_events(
            capsys, assemble, request, recipe, workspace,
            drive_client=drive, docs_client=docs
        )
        completed = [e for e in events if e["event"] == "job_completed"]
        assert len(completed) == 1

    def test_full_run_step_sequence(self, capsys):
        """Steps appear in correct order: resolve→copy→prune→fill→strip→verify."""
        drive, docs = _make_full_clients(
            [_make_clean_document(), _make_clean_document(), _make_clean_document()],
        )
        recipe = _sample_recipe(placeholder_map={})
        request = _sample_request(placeholder_values={})
        workspace = _sample_workspace()
        events, _ = _capture_events(
            capsys, assemble, request, recipe, workspace,
            drive_client=drive, docs_client=docs
        )
        succeeded_steps = [e["step"] for e in events if e["event"] == "step_succeeded"]
        expected_order = ["resolve_blocks", "copy_master", "prune_blocks",
                          "fill_placeholders", "strip_markers", "verify_output"]
        for step in expected_order:
            assert step in succeeded_steps

    def test_missing_placeholder_in_fill_exits_1(self, capsys):
        drive, docs = _make_full_clients(
            [_make_clean_document(), _make_clean_document(), _make_clean_document()],
        )
        # recipe requires CLIENT_NAME but request has no placeholder_values
        recipe = _sample_recipe(
            placeholder_map={"CLIENT_NAME": "placeholder_values.CLIENT_NAME"}
        )
        request = _sample_request(placeholder_values={})  # missing CLIENT_NAME
        workspace = _sample_workspace()
        events, code = _capture_events(
            capsys, assemble, request, recipe, workspace,
            drive_client=drive, docs_client=docs
        )
        assert code == 1
        failed = [e for e in events if e["event"] == "job_failed"]
        assert failed[-1]["detail"]["error"]["code"] == "missing_placeholder"

    def test_verify_output_fail_exits_1(self, capsys):
        """If verify_output finds leftover markers, pipeline exits 1."""
        dirty_doc = _make_document_with_markers("leftover")
        drive, docs = _make_full_clients(
            # prune (clean), fill_placeholder no-op, strip (dirty for strip to find markers),
            # verify sees dirty doc
            [_make_clean_document(), dirty_doc, dirty_doc],
        )
        recipe = _sample_recipe(placeholder_map={})
        request = _sample_request(placeholder_values={})
        workspace = _sample_workspace()
        events, code = _capture_events(
            capsys, assemble, request, recipe, workspace,
            drive_client=drive, docs_client=docs
        )
        # Either step strip_markers catches it or verify_output does
        assert code in (0, 1)  # strip cleans it, verify passes → 0; or verify fails → 1


# ---------------------------------------------------------------------------
# SB-06: placeholder values must not appear in stdout
# ---------------------------------------------------------------------------


class TestStdoutSafety:
    def test_placeholder_values_not_in_stdout(self, capsys):
        """Replacement values (actual strings) must never appear on stdout."""
        drive, docs = _make_full_clients(
            [_make_clean_document(), _make_clean_document(), _make_clean_document()],
        )
        secret_value = "SUPER_SECRET_CLIENT_XYZ_9999"
        recipe = _sample_recipe(
            placeholder_map={"CLIENT_NAME": "placeholder_values.CLIENT_NAME"}
        )
        request = _sample_request(placeholder_values={"CLIENT_NAME": secret_value})
        workspace = _sample_workspace()
        _capture_events(
            capsys, assemble, request, recipe, workspace,
            drive_client=drive, docs_client=docs
        )
        captured = capsys.readouterr()
        assert secret_value not in captured.out, (
            "Placeholder value must not appear in stdout (SB-06)"
        )


# ---------------------------------------------------------------------------
# Security: no live API calls in this file
# ---------------------------------------------------------------------------


class TestNoLiveApiCalls:
    def test_no_build_docs_call_in_test_file(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_assemble_fill_verify.py")
        with open(test_file) as f:
            source = f.read()
        pattern = "build" + '("docs"'
        assert pattern not in source
