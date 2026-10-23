"""
test_assemble_submit_review.py -- Unit tests for submit_for_review,
_quarantine_document, _with_retry, and the quarantine failure path in assemble()
(Issue #15).

All Google API interactions use injected fakes (SB-05).
No live API calls are made.

Covers:
  - _with_retry: success, retryable errors, non-retryable, exhausted, backoff
  - _quarantine_document: Drive files.update args, folder IDs
  - submit_for_review: happy path, name extraction, API failure
  - assemble() full pipeline: submit_for_review step emitted, job_completed step
  - assemble() ledger updated to awaiting_review on success
  - assemble() quarantine attempted on post-copy_master failures
  - quarantine failures are swallowed (never obscure original error)
  - no live API calls (source scan)
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "../../.claude/skills/document-assembly/scripts",
    )
)
sys.path.insert(0, SCRIPTS_DIR)

from assemble import (  # noqa: E402
    GoogleApiError,
    _quarantine_document,
    _with_retry,
    assemble,
    submit_for_review,
)


# ---------------------------------------------------------------------------
# Shared fake clients
# ---------------------------------------------------------------------------


class FakeDriveFiles:
    def __init__(self, meta: dict, copy_result: dict) -> None:
        self._meta = meta
        self._copy_result = copy_result
        self.update_calls: list[dict] = []

    def get(self, fileId=None, fields=None, supportsAllDrives=False):
        mock = MagicMock()
        mock.execute.return_value = dict(self._meta)
        return mock

    def copy(self, fileId=None, supportsAllDrives=False, body=None):
        mock = MagicMock()
        mock.execute.return_value = dict(self._copy_result)
        return mock

    def update(self, fileId=None, addParents=None, removeParents=None,
               supportsAllDrives=False, fields=None, body=None):
        self.update_calls.append({
            "fileId": fileId,
            "addParents": addParents,
            "removeParents": removeParents,
            "supportsAllDrives": supportsAllDrives,
        })
        mock = MagicMock()
        mock.execute.return_value = {"id": fileId}
        return mock


class FakeDriveClient:
    def __init__(self, meta: dict, copy_result: dict) -> None:
        self._files = FakeDriveFiles(meta, copy_result)

    def files(self):
        return self._files


class FakeDocsDocumentsMulti:
    """Returns different documents per get() call (call-count indexed)."""

    def __init__(self, documents: list[dict]) -> None:
        self._documents = documents
        self._call_count = 0
        self.batch_update_calls: list[dict] = []

    def get(self, documentId=None):
        idx = min(self._call_count, len(self._documents) - 1)
        doc = self._documents[idx]
        self._call_count += 1
        mock = MagicMock()
        mock.execute.return_value = dict(doc)
        return mock

    def batchUpdate(self, documentId=None, body=None):
        self.batch_update_calls.append({"documentId": documentId, "body": body})
        mock = MagicMock()
        mock.execute.return_value = {}
        return mock


class FakeDocsClientMulti:
    def __init__(self, *documents: dict) -> None:
        self._docs = FakeDocsDocumentsMulti(list(documents))

    def documents(self):
        return self._docs


# ---------------------------------------------------------------------------
# Document builders
# ---------------------------------------------------------------------------


def _clean_doc() -> dict:
    return {"body": {"content": [
        {"paragraph": {"elements": [
            {"startIndex": 1, "endIndex": 20,
             "textRun": {"content": "Clean body text here."}}
        ]}}
    ]}}


def _sample_workspace() -> dict:
    return {
        "workspace_id": "ws_test",
        "shared_drive_id": "drive_id",
        "folders": {
            "masters": "m_folder",
            "review": "r_folder",
            "approved": "a_folder",
            "quarantine": "q_folder",
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
        "request_id": "req_submit_001",
        "family_key": "family_a",
        "options": {},
        "placeholder_values": {},
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
        "placeholder_map": {},
        "status": "published",
    }
    base.update(overrides)
    return base


def _make_full_clients(approved_rev: str = "rev_001"):
    drive = FakeDriveClient(
        meta={"id": "master_id", "name": "Master", "headRevisionId": approved_rev},
        copy_result={"id": "output_doc_xyz"},
    )
    # Pipeline calls get() for: prune, strip, verify, submit_for_review
    docs = FakeDocsClientMulti(_clean_doc(), _clean_doc(), _clean_doc(), _clean_doc())
    return drive, docs


def _capture_events(capsys, fn, *args, **kwargs) -> tuple[list[dict], int]:
    result = fn(*args, **kwargs)
    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.strip().splitlines() if line.strip()]
    return events, result


# ---------------------------------------------------------------------------
# _with_retry tests
# ---------------------------------------------------------------------------


class TestWithRetry:
    def test_returns_value_on_first_success(self):
        result = _with_retry(lambda: 42)
        assert result == 42

    def test_retries_on_retryable_google_api_error(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise GoogleApiError("transient", retryable=True)
            return "ok"

        with patch("assemble.time.sleep"):
            result = _with_retry(flaky, max_attempts=5, base_delay=0.001)
        assert result == "ok"
        assert len(calls) == 3

    def test_propagates_immediately_on_non_retryable(self):
        def fn():
            raise GoogleApiError("permanent", retryable=False)

        with patch("assemble.time.sleep"):
            with pytest.raises(GoogleApiError, match="permanent"):
                _with_retry(fn, max_attempts=5)

    def test_raises_after_max_attempts_exhausted(self):
        attempts = []

        def always_fail():
            attempts.append(1)
            raise GoogleApiError("always fails", retryable=True)

        with patch("assemble.time.sleep"):
            with pytest.raises(GoogleApiError):
                _with_retry(always_fail, max_attempts=3)
        assert len(attempts) == 3

    def test_sleeps_with_exponential_backoff(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise GoogleApiError("transient", retryable=True)
            return "done"

        with patch("assemble.time.sleep") as mock_sleep:
            _with_retry(flaky, max_attempts=5, base_delay=2.0)
        sleep_args = [c.args[0] for c in mock_sleep.call_args_list]
        # attempt 0: sleep 2.0*2^0=2.0; attempt 1: sleep 2.0*2^1=4.0
        assert sleep_args[0] == 2.0
        assert sleep_args[1] == 4.0

    def test_does_not_retry_non_google_exceptions(self):
        calls = []

        def fn():
            calls.append(1)
            raise ValueError("not a google error")

        with pytest.raises(ValueError):
            _with_retry(fn, max_attempts=5)
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# _quarantine_document tests
# ---------------------------------------------------------------------------


class TestQuarantineDocument:
    def test_calls_files_update_with_correct_parents(self):
        drive = FakeDriveClient(meta={}, copy_result={})
        _quarantine_document(drive, "doc_id", _sample_workspace())
        calls = drive.files().update_calls
        assert len(calls) == 1
        assert calls[0]["fileId"] == "doc_id"
        assert calls[0]["addParents"] == "q_folder"
        assert calls[0]["removeParents"] == "r_folder"

    def test_calls_with_supports_all_drives(self):
        drive = FakeDriveClient(meta={}, copy_result={})
        _quarantine_document(drive, "doc_id", _sample_workspace())
        calls = drive.files().update_calls
        assert calls[0]["supportsAllDrives"] is True

    def test_uses_workspace_folder_ids(self):
        drive = FakeDriveClient(meta={}, copy_result={})
        workspace = _sample_workspace()
        workspace["folders"]["quarantine"] = "q_custom"
        workspace["folders"]["review"] = "r_custom"
        _quarantine_document(drive, "doc_xyz", workspace)
        calls = drive.files().update_calls
        assert calls[0]["addParents"] == "q_custom"
        assert calls[0]["removeParents"] == "r_custom"


# ---------------------------------------------------------------------------
# submit_for_review tests
# ---------------------------------------------------------------------------


class TestSubmitForReview:
    def test_returns_output_document_id(self):
        drive = FakeDriveClient(
            meta={"id": "output_doc_xyz", "name": "Draft Doc"},
            copy_result={"id": "output_doc_xyz"},
        )
        result = submit_for_review(drive, "output_doc_xyz", _sample_workspace())
        assert result["output_document_id"] == "output_doc_xyz"

    def test_returns_document_name_from_drive(self):
        drive = FakeDriveClient(
            meta={"id": "output_doc_xyz", "name": "Master draft abc12345"},
            copy_result={"id": "output_doc_xyz"},
        )
        result = submit_for_review(drive, "output_doc_xyz", _sample_workspace())
        assert result["document_name"] == "Master draft abc12345"

    def test_missing_name_returns_empty_string(self):
        drive = FakeDriveClient(
            meta={"id": "output_doc_xyz"},
            copy_result={"id": "output_doc_xyz"},
        )
        result = submit_for_review(drive, "output_doc_xyz", _sample_workspace())
        assert result["document_name"] == ""

    def test_propagates_api_exception(self):
        mock_drive = MagicMock()
        mock_drive.files().get().execute.side_effect = Exception("API down")
        with pytest.raises(Exception, match="API down"):
            submit_for_review(mock_drive, "doc_id", _sample_workspace())


# ---------------------------------------------------------------------------
# Full pipeline: submit_for_review step in assemble()
# ---------------------------------------------------------------------------


class TestAssemblePipelineSubmitReview:
    def test_full_run_exits_0(self, capsys):
        drive, docs = _make_full_clients()
        events, code = _capture_events(
            capsys, assemble, _sample_request(), _sample_recipe(), _sample_workspace(),
            drive_client=drive, docs_client=docs
        )
        assert code == 0

    def test_full_run_emits_submit_for_review_step_succeeded(self, capsys):
        drive, docs = _make_full_clients()
        events, _ = _capture_events(
            capsys, assemble, _sample_request(), _sample_recipe(), _sample_workspace(),
            drive_client=drive, docs_client=docs
        )
        succeeded = [e["step"] for e in events if e["event"] == "step_succeeded"]
        assert "submit_for_review" in succeeded

    def test_submit_for_review_is_last_succeeded_step(self, capsys):
        drive, docs = _make_full_clients()
        events, _ = _capture_events(
            capsys, assemble, _sample_request(), _sample_recipe(), _sample_workspace(),
            drive_client=drive, docs_client=docs
        )
        succeeded = [e["step"] for e in events if e["event"] == "step_succeeded"]
        assert succeeded[-1] == "submit_for_review"

    def test_job_completed_step_is_submit_for_review(self, capsys):
        drive, docs = _make_full_clients()
        events, _ = _capture_events(
            capsys, assemble, _sample_request(), _sample_recipe(), _sample_workspace(),
            drive_client=drive, docs_client=docs
        )
        completed = [e for e in events if e["event"] == "job_completed"]
        assert len(completed) == 1
        assert completed[0]["step"] == "submit_for_review"

    def test_job_completed_includes_output_document_id(self, capsys):
        drive, docs = _make_full_clients()
        events, _ = _capture_events(
            capsys, assemble, _sample_request(), _sample_recipe(), _sample_workspace(),
            drive_client=drive, docs_client=docs
        )
        completed = [e for e in events if e["event"] == "job_completed"][0]
        assert completed["detail"]["output_document_id"] == "output_doc_xyz"

    def test_ledger_status_set_to_awaiting_review(self, capsys):
        drive, docs = _make_full_clients()
        ledger = MagicMock()
        ledger.find_job_by_request_id.return_value = None
        ledger.create_job.return_value = "job_abc"
        _capture_events(
            capsys, assemble, _sample_request(), _sample_recipe(), _sample_workspace(),
            drive_client=drive, docs_client=docs, ledger=ledger
        )
        all_patches = [c[0][1] for c in ledger.update_job.call_args_list if c[0]]
        assert any(p.get("status") == "awaiting_review" for p in all_patches)

    def test_no_quarantine_on_success(self, capsys):
        drive, docs = _make_full_clients()
        _, code = _capture_events(
            capsys, assemble, _sample_request(), _sample_recipe(), _sample_workspace(),
            drive_client=drive, docs_client=docs
        )
        assert code == 0
        assert len(drive.files().update_calls) == 0


# ---------------------------------------------------------------------------
# Quarantine on failure path
# ---------------------------------------------------------------------------


class TestQuarantineOnFailure:
    def test_quarantine_called_on_prune_failure(self, capsys):
        drive = FakeDriveClient(
            meta={"id": "master_id", "name": "M", "headRevisionId": "rev_001"},
            copy_result={"id": "out_doc"},
        )
        docs = MagicMock()
        docs.documents().get().execute.side_effect = Exception("Docs API down")

        events, code = _capture_events(
            capsys, assemble, _sample_request(), _sample_recipe(), _sample_workspace(),
            drive_client=drive, docs_client=docs
        )
        assert code == 2
        assert len(drive.files().update_calls) >= 1
        assert drive.files().update_calls[0]["addParents"] == "q_folder"

    def test_quarantine_called_on_fill_placeholders_failure(self, capsys):
        drive = FakeDriveClient(
            meta={"id": "master_id", "name": "M", "headRevisionId": "rev_001"},
            copy_result={"id": "out_doc"},
        )
        docs = FakeDocsClientMulti(_clean_doc(), _clean_doc(), _clean_doc(), _clean_doc())
        recipe = _sample_recipe(
            placeholder_map={"CLIENT_NAME": "placeholder_values.CLIENT_NAME"}
        )
        request = _sample_request(placeholder_values={})  # missing CLIENT_NAME

        events, code = _capture_events(
            capsys, assemble, request, recipe, _sample_workspace(),
            drive_client=drive, docs_client=docs
        )
        assert code == 1
        assert len(drive.files().update_calls) >= 1
        assert drive.files().update_calls[0]["addParents"] == "q_folder"

    def test_quarantine_failure_does_not_obscure_original_error(self, capsys):
        class FailingUpdateFiles(FakeDriveFiles):
            def update(self, **kwargs):
                raise Exception("Quarantine API failure")

        drive = FakeDriveClient(
            meta={"id": "master_id", "name": "M", "headRevisionId": "rev_001"},
            copy_result={"id": "out_doc"},
        )
        drive._files = FailingUpdateFiles(
            meta={"id": "master_id", "name": "M", "headRevisionId": "rev_001"},
            copy_result={"id": "out_doc"},
        )

        docs = MagicMock()
        docs.documents().get().execute.side_effect = Exception("Docs API down")

        events, code = _capture_events(
            capsys, assemble, _sample_request(), _sample_recipe(), _sample_workspace(),
            drive_client=drive, docs_client=docs
        )
        assert code == 2
        failed = [e for e in events if e["event"] == "job_failed"]
        assert len(failed) >= 1

    def test_quarantine_not_called_before_copy_master(self, capsys):
        drive = FakeDriveClient(meta={}, copy_result={})
        docs = FakeDocsClientMulti(_clean_doc())
        # Force recipe_conflict: two rules both matching, one includes/one excludes same block
        recipe = _sample_recipe(
            rules=[
                {"when": {}, "include": ["intro"]},
                {"when": {}, "exclude": ["intro"]},
            ]
        )
        events, code = _capture_events(
            capsys, assemble, _sample_request(), recipe, _sample_workspace(),
            drive_client=drive, docs_client=docs
        )
        assert code == 1
        assert len(drive.files().update_calls) == 0


# ---------------------------------------------------------------------------
# Security: no live API calls in this file
# ---------------------------------------------------------------------------


class TestNoLiveApiCalls:
    def test_no_build_call_in_test_file(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_assemble_submit_review.py")
        with open(test_file) as f:
            source = f.read()
        # Verify no googleapiclient.discovery.build calls
        pattern = "build" + '("docs"'
        pattern2 = "build" + '("drive"'
        assert pattern not in source
        assert pattern2 not in source
