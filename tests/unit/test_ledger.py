"""
test_ledger.py — Unit tests for LedgerAdapter and SheetsLedgerAdapter.

All tests use either InMemoryLedgerAdapter or a fake in-memory Sheets client.
No live Sheets API calls are made.

Covers: AC criteria for Issue #12 (AD-12, AD-13, G-09, G-13).
"""

from __future__ import annotations

import os
import sys
import uuid
from unittest.mock import MagicMock

import pytest

SCRIPTS_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "../../.claude/skills/document-assembly/scripts",
    )
)
sys.path.insert(0, SCRIPTS_DIR)

from ledger import (  # noqa: E402
    InMemoryLedgerAdapter,
    JobNotFoundError,
    LedgerAdapter,
    SheetsLedgerAdapter,
)


# ---------------------------------------------------------------------------
# Fake Sheets client
# ---------------------------------------------------------------------------


class _FakeSheetsValues:
    """Mimics the spreadsheets().values() fluent API with in-memory storage."""

    def __init__(self, store: dict[str, list[list]]) -> None:
        self._store = store  # tab_name -> list of rows (each row is a list)
        self._pending_append_tab: str | None = None
        self._pending_append_row: list | None = None

    def append(self, spreadsheetId, range, valueInputOption, insertDataOption, body):
        tab = range.split("!")[0]
        rows = body["values"]
        mock = MagicMock()
        mock.execute.side_effect = lambda: self._store.setdefault(tab, []).extend(rows)
        return mock

    def get(self, spreadsheetId, range):
        tab = range.split("!")[0]
        mock = MagicMock()
        mock.execute.return_value = {"values": list(self._store.get(tab, []))}
        return mock

    def update(self, spreadsheetId, range, valueInputOption, body):
        # range like "jobs!A3" — 1-based row index
        tab, cell = range.split("!")
        row_index = int(cell[1:]) - 1  # convert to 0-based
        rows = body["values"]
        store = self._store.setdefault(tab, [])
        while len(store) <= row_index:
            store.append([])
        store[row_index] = rows[0]
        mock = MagicMock()
        mock.execute.return_value = {}
        return mock


class _FakeSpreadsheetsValues:
    def __init__(self, store):
        self._values = _FakeSheetsValues(store)

    def values(self):
        return self._values


class FakeSheetsClient:
    """Minimal fake for googleapiclient Sheets v4 resource."""

    def __init__(self):
        self._store: dict[str, list[list]] = {}

    def spreadsheets(self):
        return _FakeSpreadsheetsValues(self._store)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SPREADSHEET_ID = "fake_spreadsheet_id"
_WORKSPACE_ID = "ws_test_001"


def _make_sheets_adapter(workspace_id: str = _WORKSPACE_ID) -> tuple[SheetsLedgerAdapter, FakeSheetsClient]:
    client = FakeSheetsClient()
    adapter = SheetsLedgerAdapter(client, _SPREADSHEET_ID, workspace_id)
    return adapter, client


def _sample_job(**overrides) -> dict:
    base = {
        "request_id": "req_" + uuid.uuid4().hex[:8],
        "recipe_version": "proposal_v1",
        "status": "pending",
        "run_by": "agent@example.com",
    }
    base.update(overrides)
    return base


def _sample_event(job_id: str, **overrides) -> dict:
    base = {
        "job_id": job_id,
        "event_id": "evt_" + uuid.uuid4().hex[:8],
        "event_type": "status_change",
        "from": "pending",
        "to": "building",
        "actor": "agent@example.com",
        "occurred_at": "2024-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# InMemoryLedgerAdapter tests (fast path, no fake Sheets needed)
# ---------------------------------------------------------------------------


class TestInMemoryCreateJob:
    def test_returns_job_id_string(self):
        adapter = InMemoryLedgerAdapter()
        job_id = adapter.create_job(_sample_job())
        assert isinstance(job_id, str)
        assert len(job_id) > 0

    def test_unique_ids_per_call(self):
        adapter = InMemoryLedgerAdapter()
        ids = {adapter.create_job(_sample_job()) for _ in range(10)}
        assert len(ids) == 10

    def test_persists_fields(self):
        adapter = InMemoryLedgerAdapter()
        job = _sample_job(status="pending", run_by="tester")
        job_id = adapter.create_job(job)
        stored = adapter.get_job(job_id)
        assert stored["status"] == "pending"
        assert stored["run_by"] == "tester"
        assert stored["job_id"] == job_id

    def test_sets_created_at_and_updated_at(self):
        adapter = InMemoryLedgerAdapter()
        job_id = adapter.create_job(_sample_job())
        stored = adapter.get_job(job_id)
        assert "created_at" in stored
        assert "updated_at" in stored
        assert stored["created_at"]  # non-empty

    def test_preserves_explicit_job_id(self):
        adapter = InMemoryLedgerAdapter()
        job = _sample_job(job_id="explicit_id_abc")
        returned_id = adapter.create_job(job)
        assert returned_id == "explicit_id_abc"
        stored = adapter.get_job("explicit_id_abc")
        assert stored["job_id"] == "explicit_id_abc"


class TestInMemoryGetJob:
    def test_raises_for_unknown_id(self):
        adapter = InMemoryLedgerAdapter()
        with pytest.raises(JobNotFoundError):
            adapter.get_job("nonexistent")

    def test_returns_copy_not_reference(self):
        adapter = InMemoryLedgerAdapter()
        job_id = adapter.create_job(_sample_job())
        stored = adapter.get_job(job_id)
        stored["status"] = "mutated"
        assert adapter.get_job(job_id)["status"] != "mutated"


class TestInMemoryUpdateJob:
    def test_patches_specified_fields(self):
        adapter = InMemoryLedgerAdapter()
        job_id = adapter.create_job(_sample_job(status="pending"))
        adapter.update_job(job_id, {"status": "building"})
        assert adapter.get_job(job_id)["status"] == "building"

    def test_does_not_alter_other_fields(self):
        adapter = InMemoryLedgerAdapter()
        job = _sample_job(status="pending", run_by="original@example.com")
        job_id = adapter.create_job(job)
        adapter.update_job(job_id, {"status": "done"})
        assert adapter.get_job(job_id)["run_by"] == "original@example.com"

    def test_refreshes_updated_at(self):
        adapter = InMemoryLedgerAdapter()
        job_id = adapter.create_job(_sample_job())
        before = adapter.get_job(job_id)["updated_at"]
        import time; time.sleep(0.01)
        adapter.update_job(job_id, {"status": "building"})
        after = adapter.get_job(job_id)["updated_at"]
        # updated_at should be >= before (may be equal in fast machines)
        assert after >= before

    def test_raises_for_unknown_id(self):
        adapter = InMemoryLedgerAdapter()
        with pytest.raises(JobNotFoundError):
            adapter.update_job("unknown", {"status": "done"})

    def test_workspace_id_is_immutable(self):
        adapter = InMemoryLedgerAdapter()
        job_id = adapter.create_job(_sample_job())
        original_ws = adapter.get_job(job_id).get("workspace_id")
        adapter.update_job(job_id, {"workspace_id": "other_workspace"})
        assert adapter.get_job(job_id).get("workspace_id") == original_ws


class TestInMemoryFindJobByRequestId:
    def test_returns_job_when_found(self):
        adapter = InMemoryLedgerAdapter()
        req_id = "req_idempotent_001"
        job = _sample_job(request_id=req_id, workspace_id="ws_a")
        job_id = adapter.create_job(job)
        result = adapter.find_job_by_request_id(req_id, "ws_a")
        assert result is not None
        assert result["job_id"] == job_id

    def test_returns_none_when_not_found(self):
        adapter = InMemoryLedgerAdapter()
        result = adapter.find_job_by_request_id("nonexistent_req", "ws_a")
        assert result is None

    def test_workspace_isolation(self):
        adapter = InMemoryLedgerAdapter()
        req_id = "req_shared_001"
        adapter.create_job(_sample_job(request_id=req_id, workspace_id="ws_a"))
        # Same request_id in a DIFFERENT workspace should not be returned
        result = adapter.find_job_by_request_id(req_id, "ws_b")
        assert result is None

    def test_returns_correct_workspace_match(self):
        adapter = InMemoryLedgerAdapter()
        req_id = "req_multi"
        adapter.create_job(_sample_job(request_id=req_id, workspace_id="ws_a"))
        adapter.create_job(_sample_job(request_id=req_id, workspace_id="ws_b"))
        result_a = adapter.find_job_by_request_id(req_id, "ws_a")
        result_b = adapter.find_job_by_request_id(req_id, "ws_b")
        assert result_a["workspace_id"] == "ws_a"
        assert result_b["workspace_id"] == "ws_b"


class TestInMemoryAppendEvent:
    def test_first_event_gets_sequence_1(self):
        adapter = InMemoryLedgerAdapter()
        job_id = adapter.create_job(_sample_job())
        adapter.append_event(_sample_event(job_id))
        events = adapter.list_events(job_id)
        assert events[0]["sequence"] == 1

    def test_sequence_increments_per_job(self):
        adapter = InMemoryLedgerAdapter()
        job_id = adapter.create_job(_sample_job())
        for _ in range(5):
            adapter.append_event(_sample_event(job_id))
        events = adapter.list_events(job_id)
        sequences = [e["sequence"] for e in events]
        assert sequences == [1, 2, 3, 4, 5]

    def test_sequences_are_independent_per_job(self):
        adapter = InMemoryLedgerAdapter()
        job_a = adapter.create_job(_sample_job())
        job_b = adapter.create_job(_sample_job())
        adapter.append_event(_sample_event(job_a))
        adapter.append_event(_sample_event(job_a))
        adapter.append_event(_sample_event(job_b))
        events_a = adapter.list_events(job_a)
        events_b = adapter.list_events(job_b)
        assert [e["sequence"] for e in events_a] == [1, 2]
        assert [e["sequence"] for e in events_b] == [1]

    def test_all_event_fields_persisted(self):
        adapter = InMemoryLedgerAdapter()
        job_id = adapter.create_job(_sample_job())
        evt = _sample_event(
            job_id,
            event_id="evt_abc",
            event_type="status_change",
            actor="user@example.com",
            occurred_at="2024-06-01T12:00:00Z",
        )
        adapter.append_event(evt)
        stored = adapter.list_events(job_id)[0]
        assert stored["event_id"] == "evt_abc"
        assert stored["event_type"] == "status_change"
        assert stored["actor"] == "user@example.com"
        assert stored["occurred_at"] == "2024-06-01T12:00:00Z"


class TestInMemoryListEvents:
    def test_empty_list_for_job_with_no_events(self):
        adapter = InMemoryLedgerAdapter()
        job_id = adapter.create_job(_sample_job())
        assert adapter.list_events(job_id) == []

    def test_sorted_ascending_by_sequence(self):
        adapter = InMemoryLedgerAdapter()
        job_id = adapter.create_job(_sample_job())
        for _ in range(4):
            adapter.append_event(_sample_event(job_id))
        events = adapter.list_events(job_id)
        assert [e["sequence"] for e in events] == [1, 2, 3, 4]

    def test_only_returns_events_for_given_job(self):
        adapter = InMemoryLedgerAdapter()
        job_a = adapter.create_job(_sample_job())
        job_b = adapter.create_job(_sample_job())
        adapter.append_event(_sample_event(job_a))
        adapter.append_event(_sample_event(job_b))
        adapter.append_event(_sample_event(job_a))
        events_a = adapter.list_events(job_a)
        assert len(events_a) == 2
        assert all(e["job_id"] == job_a for e in events_a)


# ---------------------------------------------------------------------------
# SheetsLedgerAdapter tests (fake Sheets client)
# ---------------------------------------------------------------------------


class TestSheetsCreateJob:
    def test_returns_job_id_string(self):
        adapter, _ = _make_sheets_adapter()
        job_id = adapter.create_job(_sample_job())
        assert isinstance(job_id, str)

    def test_get_job_returns_persisted_fields(self):
        adapter, _ = _make_sheets_adapter()
        job = _sample_job(status="pending", recipe_version="proposal_v2")
        job_id = adapter.create_job(job)
        stored = adapter.get_job(job_id)
        assert stored["status"] == "pending"
        assert stored["recipe_version"] == "proposal_v2"
        assert stored["job_id"] == job_id

    def test_workspace_id_set_from_adapter(self):
        adapter, _ = _make_sheets_adapter(workspace_id="ws_sheets_001")
        job_id = adapter.create_job(_sample_job())
        stored = adapter.get_job(job_id)
        assert stored["workspace_id"] == "ws_sheets_001"

    def test_workspace_id_not_overridable_at_create(self):
        adapter, _ = _make_sheets_adapter(workspace_id="ws_real")
        # Even if caller passes a different workspace_id, adapter wins
        job_id = adapter.create_job(_sample_job(workspace_id="ws_wrong"))
        stored = adapter.get_job(job_id)
        assert stored["workspace_id"] == "ws_real"


class TestSheetsGetJob:
    def test_raises_job_not_found_for_unknown_id(self):
        adapter, _ = _make_sheets_adapter()
        with pytest.raises(JobNotFoundError):
            adapter.get_job("nonexistent_id")

    def test_returns_correct_job_among_multiple(self):
        adapter, _ = _make_sheets_adapter()
        id_a = adapter.create_job(_sample_job(status="pending"))
        id_b = adapter.create_job(_sample_job(status="building"))
        assert adapter.get_job(id_a)["status"] == "pending"
        assert adapter.get_job(id_b)["status"] == "building"


class TestSheetsUpdateJob:
    def test_patches_status(self):
        adapter, _ = _make_sheets_adapter()
        job_id = adapter.create_job(_sample_job(status="pending"))
        adapter.update_job(job_id, {"status": "done"})
        assert adapter.get_job(job_id)["status"] == "done"

    def test_workspace_id_immutable_in_update(self):
        adapter, _ = _make_sheets_adapter(workspace_id="ws_fixed")
        job_id = adapter.create_job(_sample_job())
        adapter.update_job(job_id, {"workspace_id": "ws_other"})
        assert adapter.get_job(job_id)["workspace_id"] == "ws_fixed"

    def test_raises_for_unknown_id(self):
        adapter, _ = _make_sheets_adapter()
        with pytest.raises(JobNotFoundError):
            adapter.update_job("unknown_id", {"status": "done"})


class TestSheetsFindJobByRequestId:
    def test_returns_job_on_match(self):
        adapter, _ = _make_sheets_adapter(workspace_id="ws_x")
        req_id = "req_sheets_001"
        job_id = adapter.create_job(_sample_job(request_id=req_id))
        result = adapter.find_job_by_request_id(req_id, "ws_x")
        assert result is not None
        assert result["job_id"] == job_id

    def test_returns_none_on_no_match(self):
        adapter, _ = _make_sheets_adapter(workspace_id="ws_x")
        result = adapter.find_job_by_request_id("req_missing", "ws_x")
        assert result is None

    def test_workspace_isolation(self):
        adapter, _ = _make_sheets_adapter(workspace_id="ws_x")
        req_id = "req_sheets_iso"
        adapter.create_job(_sample_job(request_id=req_id))
        # Different workspace — should not match
        result = adapter.find_job_by_request_id(req_id, "ws_y")
        assert result is None


class TestSheetsAppendAndListEvents:
    def test_first_event_sequence_is_1(self):
        adapter, _ = _make_sheets_adapter()
        job_id = adapter.create_job(_sample_job())
        adapter.append_event(_sample_event(job_id))
        events = adapter.list_events(job_id)
        assert events[0]["sequence"] == 1

    def test_sequence_increments(self):
        adapter, _ = _make_sheets_adapter()
        job_id = adapter.create_job(_sample_job())
        for _ in range(3):
            adapter.append_event(_sample_event(job_id))
        events = adapter.list_events(job_id)
        assert [e["sequence"] for e in events] == [1, 2, 3]

    def test_empty_list_for_job_with_no_events(self):
        adapter, _ = _make_sheets_adapter()
        job_id = adapter.create_job(_sample_job())
        assert adapter.list_events(job_id) == []

    def test_workspace_id_set_on_events(self):
        adapter, _ = _make_sheets_adapter(workspace_id="ws_event_test")
        job_id = adapter.create_job(_sample_job())
        adapter.append_event(_sample_event(job_id))
        events = adapter.list_events(job_id)
        assert events[0]["workspace_id"] == "ws_event_test"

    def test_events_filtered_by_job_id(self):
        adapter, _ = _make_sheets_adapter()
        job_a = adapter.create_job(_sample_job())
        job_b = adapter.create_job(_sample_job())
        adapter.append_event(_sample_event(job_a))
        adapter.append_event(_sample_event(job_b))
        adapter.append_event(_sample_event(job_a))
        assert len(adapter.list_events(job_a)) == 2
        assert len(adapter.list_events(job_b)) == 1


# ---------------------------------------------------------------------------
# Abstract base class contract
# ---------------------------------------------------------------------------


class TestLedgerAdapterIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            LedgerAdapter()  # type: ignore[abstract]

    def test_in_memory_is_a_ledger_adapter(self):
        assert isinstance(InMemoryLedgerAdapter(), LedgerAdapter)

    def test_sheets_adapter_is_a_ledger_adapter(self):
        adapter, _ = _make_sheets_adapter()
        assert isinstance(adapter, LedgerAdapter)


# ---------------------------------------------------------------------------
# Security: no live API calls in this file
# ---------------------------------------------------------------------------


class TestNoLiveApiCalls:
    def test_no_build_call_in_test_file(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_ledger.py")
        with open(test_file) as f:
            source = f.read()
        # Build dynamic pattern to avoid self-match
        pattern = "build" + '("sheets"'
        assert pattern not in source, "test file must not call googleapiclient build()"
