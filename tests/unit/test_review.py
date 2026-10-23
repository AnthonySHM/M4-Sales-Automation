"""
test_review.py -- Unit tests for review.py (Issue #20).

All Google API interactions use injected fakes (SB-05).
No live API calls are made.

Covers:
  - _check_reviewer: authorized, unauthorized, empty list (permissive)
  - _move_to_approved: Drive files.update args
  - review() approve path: move_document step, record_decision, job_completed
  - review() reject path: no move_document, reason recorded
  - review() validation: missing reason on rejection
  - review() state check: non-awaiting_review jobs rejected
  - review() unauthorized reviewer
  - review() API failure on move_document
  - review() API failure on record_decision
  - review() with ledger: job state checked, events appended, status updated
  - no live API calls (source scan)
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

from review import (  # noqa: E402
    UnauthorizedReviewerError,
    _check_reviewer,
    _move_to_approved,
    review,
)


# ---------------------------------------------------------------------------
# Shared fake clients
# ---------------------------------------------------------------------------


class FakeDriveFiles:
    def __init__(self) -> None:
        self.update_calls: list[dict] = []

    def update(self, fileId=None, addParents=None, removeParents=None,
               supportsAllDrives=False, fields=None):
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
    def __init__(self) -> None:
        self._files = FakeDriveFiles()

    def files(self):
        return self._files


class FakeLedger:
    def __init__(self, job: dict | None = None) -> None:
        self._job = job or {}
        self.update_calls: list[tuple] = []
        self.appended_events: list[dict] = []

    def get_job(self, job_id: str) -> dict:
        if not self._job:
            raise KeyError(f"Job not found: {job_id}")
        return dict(self._job)

    def update_job(self, job_id: str, patch: dict) -> None:
        self.update_calls.append((job_id, patch))

    def append_event(self, event: dict) -> None:
        self.appended_events.append(event)


# ---------------------------------------------------------------------------
# Workspace / request builders
# ---------------------------------------------------------------------------


def _sample_workspace(**overrides) -> dict:
    base = {
        "workspace_id": "ws_test",
        "shared_drive_id": "drive_id",
        "folders": {
            "masters": "m_folder",
            "review": "r_folder",
            "approved": "a_folder",
            "quarantine": "q_folder",
        },
        "reviewers": [],
    }
    base.update(overrides)
    return base


def _awaiting_review_job(job_id: str = "job_001") -> dict:
    return {
        "job_id": job_id,
        "status": "awaiting_review",
        "output_document_id": "output_doc_xyz",
        "workspace_id": "ws_test",
    }


def _capture_events(capsys, fn, *args, **kwargs) -> tuple[list[dict], int]:
    result = fn(*args, **kwargs)
    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.strip().splitlines() if line.strip()]
    return events, result


# ---------------------------------------------------------------------------
# _check_reviewer tests
# ---------------------------------------------------------------------------


class TestCheckReviewer:
    def test_authorised_reviewer_passes(self):
        workspace = _sample_workspace(reviewers=["alice@example.com", "bob@example.com"])
        _check_reviewer("alice@example.com", workspace)  # should not raise

    def test_unauthorised_reviewer_raises(self):
        workspace = _sample_workspace(reviewers=["alice@example.com"])
        with pytest.raises(UnauthorizedReviewerError):
            _check_reviewer("eve@example.com", workspace)

    def test_empty_reviewers_list_is_permissive(self):
        workspace = _sample_workspace(reviewers=[])
        _check_reviewer("anyone@example.com", workspace)  # should not raise

    def test_missing_reviewers_key_is_permissive(self):
        workspace = _sample_workspace()
        del workspace["reviewers"]
        _check_reviewer("anyone@example.com", workspace)  # should not raise

    def test_error_message_includes_reviewer_email(self):
        workspace = _sample_workspace(reviewers=["alice@example.com"])
        with pytest.raises(UnauthorizedReviewerError, match="eve@example.com"):
            _check_reviewer("eve@example.com", workspace)


# ---------------------------------------------------------------------------
# _move_to_approved tests
# ---------------------------------------------------------------------------


class TestMoveToApproved:
    def test_calls_files_update_with_correct_parents(self):
        drive = FakeDriveClient()
        _move_to_approved(drive, "doc_id", _sample_workspace())
        calls = drive.files().update_calls
        assert len(calls) == 1
        assert calls[0]["fileId"] == "doc_id"
        assert calls[0]["addParents"] == "a_folder"
        assert calls[0]["removeParents"] == "r_folder"

    def test_calls_with_supports_all_drives(self):
        drive = FakeDriveClient()
        _move_to_approved(drive, "doc_id", _sample_workspace())
        calls = drive.files().update_calls
        assert calls[0]["supportsAllDrives"] is True

    def test_uses_workspace_folder_ids(self):
        drive = FakeDriveClient()
        workspace = _sample_workspace()
        workspace["folders"]["approved"] = "approved_custom"
        workspace["folders"]["review"] = "review_custom"
        _move_to_approved(drive, "doc_xyz", workspace)
        calls = drive.files().update_calls
        assert calls[0]["addParents"] == "approved_custom"
        assert calls[0]["removeParents"] == "review_custom"


# ---------------------------------------------------------------------------
# review() — approve path
# ---------------------------------------------------------------------------


class TestReviewApprove:
    def test_approve_exits_0(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        events, code = _capture_events(
            capsys, review, "job_001", "approved", "alice@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            drive_client=drive, ledger=ledger,
        )
        assert code == 0

    def test_approve_emits_move_document_step(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        events, _ = _capture_events(
            capsys, review, "job_001", "approved", "alice@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            drive_client=drive, ledger=ledger,
        )
        succeeded = [e["step"] for e in events if e["event"] == "step_succeeded"]
        assert "move_document" in succeeded

    def test_approve_moves_file_to_approved_folder(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        _capture_events(
            capsys, review, "job_001", "approved", "alice@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            drive_client=drive, ledger=ledger,
        )
        calls = drive.files().update_calls
        assert len(calls) == 1
        assert calls[0]["addParents"] == "a_folder"
        assert calls[0]["removeParents"] == "r_folder"

    def test_approve_emits_job_completed(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        events, _ = _capture_events(
            capsys, review, "job_001", "approved", "alice@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            drive_client=drive, ledger=ledger,
        )
        completed = [e for e in events if e["event"] == "job_completed"]
        assert len(completed) == 1
        assert completed[0]["detail"]["decision"] == "approved"

    def test_approve_updates_ledger_status_to_approved(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        _capture_events(
            capsys, review, "job_001", "approved", "alice@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            drive_client=drive, ledger=ledger,
        )
        all_patches = [patch for _, patch in ledger.update_calls]
        assert any(p.get("status") == "approved" for p in all_patches)

    def test_approve_appends_review_decision_event(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        _capture_events(
            capsys, review, "job_001", "approved", "alice@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            drive_client=drive, ledger=ledger,
        )
        assert len(ledger.appended_events) == 1
        ev = ledger.appended_events[0]
        assert ev["event_type"] == "review_decision"
        assert ev["detail"]["decision"] == "approved"
        assert ev["actor"] == "alice@example.com"


# ---------------------------------------------------------------------------
# review() — reject path
# ---------------------------------------------------------------------------


class TestReviewReject:
    def test_reject_exits_0(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        events, code = _capture_events(
            capsys, review, "job_001", "rejected", "alice@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            reason="Missing clause 4.2",
            drive_client=drive, ledger=ledger,
        )
        assert code == 0

    def test_reject_does_not_move_file(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        _capture_events(
            capsys, review, "job_001", "rejected", "alice@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            reason="Missing clause 4.2",
            drive_client=drive, ledger=ledger,
        )
        assert len(drive.files().update_calls) == 0

    def test_reject_updates_ledger_status_to_rejected(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        _capture_events(
            capsys, review, "job_001", "rejected", "alice@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            reason="Missing clause 4.2",
            drive_client=drive, ledger=ledger,
        )
        all_patches = [patch for _, patch in ledger.update_calls]
        assert any(p.get("status") == "rejected" for p in all_patches)

    def test_reject_appends_event_with_reason(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        _capture_events(
            capsys, review, "job_001", "rejected", "alice@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            reason="Missing clause 4.2",
            drive_client=drive, ledger=ledger,
        )
        ev = ledger.appended_events[0]
        assert ev["detail"]["decision"] == "rejected"
        assert ev["detail"]["reason"] == "Missing clause 4.2"

    def test_reject_without_reason_exits_1(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        events, code = _capture_events(
            capsys, review, "job_001", "rejected", "alice@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            # no reason
            drive_client=drive, ledger=ledger,
        )
        assert code == 1
        failed = [e for e in events if e["event"] == "job_failed"]
        assert failed[-1]["detail"]["error"]["code"] == "missing_reason"

    def test_reject_without_reason_does_not_move_file_or_append_event(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        _capture_events(
            capsys, review, "job_001", "rejected", "alice@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            drive_client=drive, ledger=ledger,
        )
        assert len(drive.files().update_calls) == 0
        assert len(ledger.appended_events) == 0


# ---------------------------------------------------------------------------
# review() — unauthorized reviewer
# ---------------------------------------------------------------------------


class TestReviewUnauthorized:
    def test_unauthorized_reviewer_exits_1(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        events, code = _capture_events(
            capsys, review, "job_001", "approved", "eve@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            drive_client=drive, ledger=ledger,
        )
        assert code == 1
        failed = [e for e in events if e["event"] == "job_failed"]
        assert failed[-1]["detail"]["error"]["code"] == "unauthorized_reviewer"

    def test_unauthorized_reviewer_does_not_move_or_record(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        _capture_events(
            capsys, review, "job_001", "approved", "eve@example.com",
            _sample_workspace(reviewers=["alice@example.com"]),
            drive_client=drive, ledger=ledger,
        )
        assert len(drive.files().update_calls) == 0
        assert len(ledger.appended_events) == 0

    def test_empty_reviewers_list_allows_any_reviewer(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        events, code = _capture_events(
            capsys, review, "job_001", "approved", "anyone@example.com",
            _sample_workspace(reviewers=[]),
            drive_client=drive, ledger=ledger,
        )
        assert code == 0


# ---------------------------------------------------------------------------
# review() — invalid job state
# ---------------------------------------------------------------------------


class TestReviewInvalidJobState:
    def test_non_awaiting_review_job_exits_1(self, capsys):
        drive = FakeDriveClient()
        job = _awaiting_review_job()
        job["status"] = "building"
        ledger = FakeLedger(job)
        events, code = _capture_events(
            capsys, review, "job_001", "approved", "alice@example.com",
            _sample_workspace(),
            drive_client=drive, ledger=ledger,
        )
        assert code == 1
        failed = [e for e in events if e["event"] == "job_failed"]
        assert failed[-1]["detail"]["error"]["code"] == "invalid_job_state"

    def test_already_approved_job_exits_1(self, capsys):
        drive = FakeDriveClient()
        job = _awaiting_review_job()
        job["status"] = "approved"
        ledger = FakeLedger(job)
        events, code = _capture_events(
            capsys, review, "job_001", "approved", "alice@example.com",
            _sample_workspace(),
            drive_client=drive, ledger=ledger,
        )
        assert code == 1

    def test_job_not_found_exits_1(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger({})  # empty job -> KeyError in get_job
        events, code = _capture_events(
            capsys, review, "job_999", "approved", "alice@example.com",
            _sample_workspace(),
            drive_client=drive, ledger=ledger,
        )
        assert code == 1
        failed = [e for e in events if e["event"] == "job_failed"]
        assert failed[-1]["detail"]["error"]["code"] == "job_not_found"


# ---------------------------------------------------------------------------
# review() — API failure paths
# ---------------------------------------------------------------------------


class TestReviewApiFailures:
    def test_move_document_api_failure_exits_2(self, capsys):
        mock_drive = MagicMock()
        mock_drive.files().update().execute.side_effect = Exception("Drive API down")
        ledger = FakeLedger(_awaiting_review_job())
        events, code = _capture_events(
            capsys, review, "job_001", "approved", "alice@example.com",
            _sample_workspace(),
            drive_client=mock_drive, ledger=ledger,
        )
        assert code == 2
        failed = [e for e in events if e["event"] == "job_failed"]
        assert failed[-1]["step"] == "move_document"

    def test_record_decision_api_failure_exits_2(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        ledger.append_event = MagicMock(side_effect=Exception("Sheets API down"))
        events, code = _capture_events(
            capsys, review, "job_001", "approved", "alice@example.com",
            _sample_workspace(),
            drive_client=drive, ledger=ledger,
        )
        assert code == 2
        failed = [e for e in events if e["event"] == "job_failed"]
        assert failed[-1]["step"] == "record_decision"


# ---------------------------------------------------------------------------
# review() without ledger (no-ledger mode)
# ---------------------------------------------------------------------------


class TestReviewNoLedger:
    def test_approve_without_ledger_exits_0(self, capsys):
        """review() should work without a ledger (skips job state check and recording)."""
        drive = FakeDriveClient()
        events, code = _capture_events(
            capsys, review, "job_001", "approved", "alice@example.com",
            _sample_workspace(),
            drive_client=drive, ledger=None,
        )
        assert code == 0

    def test_reject_without_ledger_still_requires_reason(self, capsys):
        drive = FakeDriveClient()
        events, code = _capture_events(
            capsys, review, "job_001", "rejected", "alice@example.com",
            _sample_workspace(),
            drive_client=drive, ledger=None,
        )
        assert code == 1

    def test_reject_with_reason_no_ledger_exits_0(self, capsys):
        drive = FakeDriveClient()
        events, code = _capture_events(
            capsys, review, "job_001", "rejected", "alice@example.com",
            _sample_workspace(),
            reason="Missing terms",
            drive_client=drive, ledger=None,
        )
        assert code == 0


# ---------------------------------------------------------------------------
# Step sequence verification
# ---------------------------------------------------------------------------


class TestReviewStepSequence:
    def test_approve_step_order(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        events, _ = _capture_events(
            capsys, review, "job_001", "approved", "alice@example.com",
            _sample_workspace(),
            drive_client=drive, ledger=ledger,
        )
        succeeded = [e["step"] for e in events if e["event"] == "step_succeeded"]
        expected = ["validate_reviewer", "validate_decision", "load_job",
                    "move_document", "record_decision"]
        for step in expected:
            assert step in succeeded
        assert succeeded.index("move_document") < succeeded.index("record_decision")

    def test_reject_step_order_no_move(self, capsys):
        drive = FakeDriveClient()
        ledger = FakeLedger(_awaiting_review_job())
        events, _ = _capture_events(
            capsys, review, "job_001", "rejected", "alice@example.com",
            _sample_workspace(),
            reason="Reason",
            drive_client=drive, ledger=ledger,
        )
        succeeded = [e["step"] for e in events if e["event"] == "step_succeeded"]
        assert "move_document" not in succeeded
        assert "record_decision" in succeeded


# ---------------------------------------------------------------------------
# Security: no live API calls in this file
# ---------------------------------------------------------------------------


class TestNoLiveApiCalls:
    def test_no_build_call_in_test_file(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_review.py")
        with open(test_file) as f:
            source = f.read()
        pattern = "build" + '("drive"'
        assert pattern not in source
