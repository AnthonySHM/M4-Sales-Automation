"""
ledger.py — LedgerAdapter interface and SheetsLedgerAdapter implementation.

LedgerAdapter is a storage-agnostic abstract base class. SheetsLedgerAdapter
implements it against Google Sheets (jobs tab + events tab).

In unit tests, inject a fake Sheets client via the constructor — never call
googleapiclient.discovery.build() in tested code paths.

Advances AD-12, AD-13, G-09, G-13. Full implementation for Issue #12.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class JobNotFoundError(KeyError):
    """Raised when a job_id is not present in the ledger."""


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class LedgerAdapter(ABC):
    """Storage-agnostic repository interface for assembly jobs and events."""

    @abstractmethod
    def create_job(self, job: dict) -> str:
        """Persist a new job record and return its job_id."""

    @abstractmethod
    def update_job(self, job_id: str, patch: dict) -> None:
        """Apply patch fields to an existing job. Raises JobNotFoundError if absent.

        workspace_id is immutable and silently ignored in patch.
        updated_at is always refreshed.
        """

    @abstractmethod
    def get_job(self, job_id: str) -> dict:
        """Return the job record. Raises JobNotFoundError if absent."""

    @abstractmethod
    def find_job_by_request_id(self, request_id: str, workspace_id: str) -> dict | None:
        """Return the job matching (request_id, workspace_id), or None."""

    @abstractmethod
    def append_event(self, event: dict) -> None:
        """Append an event record. sequence is auto-assigned (1-based, per job)."""

    @abstractmethod
    def list_events(self, job_id: str) -> list[dict]:
        """Return all events for job_id sorted by sequence ascending."""


# ---------------------------------------------------------------------------
# In-memory fake — used only in tests (not the Sheets implementation)
# ---------------------------------------------------------------------------


class InMemoryLedgerAdapter(LedgerAdapter):
    """Pure in-memory ledger for testing. No external dependencies."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}       # job_id -> job dict
        self._events: list[dict] = []          # append-only

    def create_job(self, job: dict) -> str:
        job_id = job.get("job_id") or "job_" + uuid.uuid4().hex[:12]
        now = _now_iso()
        record = dict(job)
        record["job_id"] = job_id
        record.setdefault("created_at", now)
        record.setdefault("updated_at", now)
        self._jobs[job_id] = record
        return job_id

    def update_job(self, job_id: str, patch: dict) -> None:
        if job_id not in self._jobs:
            raise JobNotFoundError(job_id)
        record = self._jobs[job_id]
        for k, v in patch.items():
            if k == "workspace_id":
                continue  # immutable — silently ignore (AD-13)
            record[k] = v
        record["updated_at"] = _now_iso()

    def get_job(self, job_id: str) -> dict:
        if job_id not in self._jobs:
            raise JobNotFoundError(job_id)
        return dict(self._jobs[job_id])

    def find_job_by_request_id(self, request_id: str, workspace_id: str) -> dict | None:
        for job in self._jobs.values():
            if job.get("request_id") == request_id and job.get("workspace_id") == workspace_id:
                return dict(job)
        return None

    def append_event(self, event: dict) -> None:
        job_id = event["job_id"]
        existing = [e for e in self._events if e["job_id"] == job_id]
        record = dict(event)
        record["sequence"] = len(existing) + 1
        self._events.append(record)

    def list_events(self, job_id: str) -> list[dict]:
        return sorted(
            [dict(e) for e in self._events if e["job_id"] == job_id],
            key=lambda e: e["sequence"],
        )


# ---------------------------------------------------------------------------
# SheetsLedgerAdapter — production implementation
# ---------------------------------------------------------------------------

_JOBS_TAB = "jobs"
_EVENTS_TAB = "events"

# Column order for the jobs sheet
_JOB_COLUMNS = [
    "job_id", "workspace_id", "request_id", "recipe_version",
    "master_revision_id", "resolved_blocks", "output_document_id",
    "status", "error", "run_by", "started_at", "finished_at",
    "created_at", "updated_at",
]

# Column order for the events sheet
_EVENT_COLUMNS = [
    "event_id", "workspace_id", "job_id", "sequence", "event_type",
    "from", "to", "actor", "occurred_at", "detail",
]


class SheetsLedgerAdapter(LedgerAdapter):
    """Google Sheets implementation of LedgerAdapter.

    Parameters
    ----------
    sheets_client:
        An authenticated googleapiclient Sheets v4 resource. Injected to
        allow unit tests to pass a fake without live API calls (SB-05).
    spreadsheet_id:
        The Google Sheets spreadsheet ID from config/workspace.yaml.
    workspace_id:
        Immutable workspace identifier written to every record (AD-13).
    """

    def __init__(self, sheets_client, spreadsheet_id: str, workspace_id: str) -> None:
        self._sheets = sheets_client
        self._spreadsheet_id = spreadsheet_id
        self._workspace_id = workspace_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append_row(self, tab: str, row: list) -> None:
        self._sheets.spreadsheets().values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

    def _get_all_rows(self, tab: str) -> list[list]:
        result = (
            self._sheets.spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, range=f"{tab}!A1:ZZ")
            .execute()
        )
        return result.get("values", [])

    def _update_row(self, tab: str, row_index: int, row: list) -> None:
        """Update a specific 1-based row (row 1 = header)."""
        range_notation = f"{tab}!A{row_index}"
        self._sheets.spreadsheets().values().update(
            spreadsheetId=self._spreadsheet_id,
            range=range_notation,
            valueInputOption="RAW",
            body={"values": [row]},
        ).execute()

    @staticmethod
    def _row_to_dict(columns: list[str], row: list) -> dict:
        """Convert a sheet row to a dict, padding short rows with empty strings."""
        padded = row + [""] * (len(columns) - len(row))
        return {col: padded[i] for i, col in enumerate(columns)}

    @staticmethod
    def _job_to_row(job: dict) -> list:
        import json as _json
        row = []
        for col in _JOB_COLUMNS:
            val = job.get(col, "")
            if isinstance(val, (list, dict)):
                val = _json.dumps(val)
            elif val is None:
                val = ""
            row.append(str(val) if val != "" else "")
        return row

    @staticmethod
    def _event_to_row(event: dict) -> list:
        import json as _json
        row = []
        for col in _EVENT_COLUMNS:
            val = event.get(col, "")
            if isinstance(val, (list, dict)):
                val = _json.dumps(val)
            elif val is None:
                val = ""
            row.append(str(val) if val != "" else "")
        return row

    # ------------------------------------------------------------------
    # Interface implementation
    # ------------------------------------------------------------------

    def create_job(self, job: dict) -> str:
        import json as _json
        job_id = job.get("job_id") or "job_" + uuid.uuid4().hex[:12]
        now = _now_iso()
        record = dict(job)
        record["job_id"] = job_id
        record["workspace_id"] = self._workspace_id  # always set from adapter (AD-13)
        record.setdefault("created_at", now)
        record.setdefault("updated_at", now)
        self._append_row(_JOBS_TAB, self._job_to_row(record))
        return job_id

    def get_job(self, job_id: str) -> dict:
        import json as _json
        rows = self._get_all_rows(_JOBS_TAB)
        for row in rows:
            d = self._row_to_dict(_JOB_COLUMNS, row)
            if d.get("job_id") == job_id:
                # Deserialise JSON fields
                for field in ("resolved_blocks", "error"):
                    if d.get(field) and d[field] not in ("", "null"):
                        try:
                            d[field] = _json.loads(d[field])
                        except (ValueError, TypeError):
                            pass
                    elif d.get(field) in ("", "null"):
                        d[field] = None if field == "error" else []
                return d
        raise JobNotFoundError(job_id)

    def update_job(self, job_id: str, patch: dict) -> None:
        import json as _json
        rows = self._get_all_rows(_JOBS_TAB)
        for i, row in enumerate(rows):
            d = self._row_to_dict(_JOB_COLUMNS, row)
            if d.get("job_id") == job_id:
                for k, v in patch.items():
                    if k == "workspace_id":
                        continue  # immutable (AD-13)
                    d[k] = v
                d["updated_at"] = _now_iso()
                self._update_row(_JOBS_TAB, i + 1, self._job_to_row(d))
                return
        raise JobNotFoundError(job_id)

    def find_job_by_request_id(self, request_id: str, workspace_id: str) -> dict | None:
        rows = self._get_all_rows(_JOBS_TAB)
        for row in rows:
            d = self._row_to_dict(_JOB_COLUMNS, row)
            if d.get("request_id") == request_id and d.get("workspace_id") == workspace_id:
                return d
        return None

    def append_event(self, event: dict) -> None:
        job_id = event["job_id"]
        existing = self.list_events(job_id)
        record = dict(event)
        record["workspace_id"] = self._workspace_id  # AD-13
        record["sequence"] = len(existing) + 1
        self._append_row(_EVENTS_TAB, self._event_to_row(record))

    def list_events(self, job_id: str) -> list[dict]:
        rows = self._get_all_rows(_EVENTS_TAB)
        events = []
        for row in rows:
            d = self._row_to_dict(_EVENT_COLUMNS, row)
            if d.get("job_id") == job_id:
                try:
                    d["sequence"] = int(d["sequence"])
                except (ValueError, TypeError):
                    d["sequence"] = 0
                events.append(d)
        return sorted(events, key=lambda e: e["sequence"])


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
