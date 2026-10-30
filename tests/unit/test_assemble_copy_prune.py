"""
test_assemble_copy_prune.py — Unit tests for assemble.py copy/prune steps (Issue #13).

All Google Drive and Docs API interactions use injected fakes.
No live API calls are made (SB-05).

Covers: resolve_blocks, dry-run, copy_master, prune_blocks (TL-01),
MasterRevisionMismatchError, RecipeConflictError, streaming events.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
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
    MasterRevisionMismatchError,
    RecipeConflictError,
    _extract_all_markers,
    _get_excluded_ranges,
    assemble,
    copy_master,
    prune_blocks,
    resolve_blocks,
)


# ---------------------------------------------------------------------------
# Fake Google API clients
# ---------------------------------------------------------------------------


class FakeDriveFiles:
    """Fake files() resource for Drive v3."""

    def __init__(self, meta: dict, copy_result: dict) -> None:
        self._meta = meta
        self._copy_result = copy_result
        self.copy_calls: list[dict] = []

    def get(self, fileId, fields=None, supportsAllDrives=False):
        mock = MagicMock()
        mock.execute.return_value = dict(self._meta)
        return mock

    def copy(self, fileId, supportsAllDrives=False, body=None):
        self.copy_calls.append({"fileId": fileId, "body": body})
        mock = MagicMock()
        mock.execute.return_value = dict(self._copy_result)
        return mock


class FakeDriveClient:
    def __init__(self, meta: dict, copy_result: dict) -> None:
        self._files = FakeDriveFiles(meta, copy_result)

    def files(self):
        return self._files


class FakeDocsDocuments:
    """Fake documents() resource for Docs v1."""

    def __init__(self, document: dict) -> None:
        self._document = document
        self.batch_update_calls: list[dict] = []

    def get(self, documentId):
        mock = MagicMock()
        mock.execute.return_value = dict(self._document)
        return mock

    def batchUpdate(self, documentId, body=None):
        self.batch_update_calls.append({"documentId": documentId, "body": body})
        mock = MagicMock()
        mock.execute.return_value = {}
        return mock


class FakeDocsClient:
    def __init__(self, document: dict) -> None:
        self._documents = FakeDocsDocuments(document)

    def documents(self):
        return self._documents


class _FakeDocsDocumentsMulti:
    """Returns different documents per call to support the full pipeline."""

    def __init__(self, *documents: dict) -> None:
        self._docs = list(documents)
        self._call_idx = 0
        self.batch_update_calls: list[dict] = []

    def get(self, documentId):
        mock = MagicMock()
        idx = min(self._call_idx, len(self._docs) - 1)
        mock.execute.return_value = dict(self._docs[idx])
        self._call_idx += 1
        return mock

    def batchUpdate(self, documentId, body=None):
        self.batch_update_calls.append({"documentId": documentId, "body": body})
        mock = MagicMock()
        mock.execute.return_value = {}
        return mock


class FakeDocsClientMulti:
    """Fake Docs client returning different document states per get() call."""

    def __init__(self, *documents: dict) -> None:
        self._documents_obj = _FakeDocsDocumentsMulti(*documents)

    def documents(self):
        return self._documents_obj


def _make_clean_document() -> dict:
    """Document with no markers or placeholders."""
    return {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [
                            {
                                "startIndex": 1,
                                "endIndex": 20,
                                "textRun": {"content": "Clean document text."},
                            }
                        ]
                    }
                }
            ]
        }
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_document(*block_ids: str) -> dict:
    """Build a fake Docs API document containing one paragraph per marker pair."""
    content = []
    idx = 1
    for block_id in block_ids:
        begin_text = "[[BLOCK:" + block_id + "]]"
        end_text = "[[/BLOCK:" + block_id + "]]"
        # BEGIN element
        content.append(
            {
                "paragraph": {
                    "elements": [
                        {
                            "startIndex": idx,
                            "endIndex": idx + len(begin_text),
                            "textRun": {"content": begin_text},
                        }
                    ]
                }
            }
        )
        idx += len(begin_text)
        # Body text element (within block)
        body_text = f"Body of {block_id}. "
        content.append(
            {
                "paragraph": {
                    "elements": [
                        {
                            "startIndex": idx,
                            "endIndex": idx + len(body_text),
                            "textRun": {"content": body_text},
                        }
                    ]
                }
            }
        )
        idx += len(body_text)
        # END element
        content.append(
            {
                "paragraph": {
                    "elements": [
                        {
                            "startIndex": idx,
                            "endIndex": idx + len(end_text),
                            "textRun": {"content": end_text},
                        }
                    ]
                }
            }
        )
        idx += len(end_text)
    return {"body": {"content": content}}


def _sample_request(**overrides) -> dict:
    base = {
        "request_id": "req_test_001",
        "family_key": "family_a",
        "options": {},
        "placeholder_values": {"CLIENT_NAME": "Acme Corp"},
        "requested_by": "agent@example.com",
    }
    base.update(overrides)
    return base


def _sample_recipe(
    defaults_include: list[str] | None = None,
    rules: list[dict] | None = None,
) -> dict:
    return {
        "family_key": "family_a",
        "version": 1,
        "options": [],
        "rules": rules or [],
        "defaults": {"include": defaults_include or []},
        "placeholder_map": {},
        "status": "published",
    }


def _sample_workspace(
    master_id: str = "master_doc_id",
    approved_rev: str = "rev_001",
    review_folder: str = "review_folder_id",
) -> dict:
    return {
        "workspace_id": "ws_test",
        "shared_drive_id": "drive_id",
        "folders": {
            "masters": "masters_folder",
            "review": review_folder,
            "approved": "approved_folder",
            "quarantine": "quarantine_folder",
        },
        "pilot_family": {
            "key": "family_a",
            "master_template_id": master_id,
            "approved_revision_id": approved_rev,
            "active_recipe_version": 1,
        },
    }


def _capture_events(capsys, fn, *args, **kwargs) -> tuple[list[dict], int]:
    """Call fn(*args, **kwargs), capture stdout, return (events_list, return_value)."""
    result = fn(*args, **kwargs)
    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.strip().splitlines() if line.strip()]
    return events, result


# ---------------------------------------------------------------------------
# resolve_blocks tests
# ---------------------------------------------------------------------------


class TestResolveBlocks:
    def test_defaults_only_no_rules(self):
        recipe = _sample_recipe(defaults_include=["intro", "body", "terms"])
        result = resolve_blocks(_sample_request(), recipe)
        assert result == ["body", "intro", "terms"]

    def test_empty_defaults_empty_rules(self):
        recipe = _sample_recipe()
        result = resolve_blocks(_sample_request(), recipe)
        assert result == []

    def test_matching_rule_excludes_block(self):
        recipe = _sample_recipe(
            defaults_include=["intro", "annex"],
            rules=[{"when": {"tier": "basic"}, "exclude": ["annex"]}],
        )
        request = _sample_request(options={"tier": "basic"})
        result = resolve_blocks(request, recipe)
        assert "annex" not in result
        assert "intro" in result

    def test_non_matching_rule_not_applied(self):
        recipe = _sample_recipe(
            defaults_include=["intro", "annex"],
            rules=[{"when": {"tier": "premium"}, "exclude": ["annex"]}],
        )
        request = _sample_request(options={"tier": "basic"})
        result = resolve_blocks(request, recipe)
        assert "annex" in result

    def test_matching_rule_adds_optional_block(self):
        recipe = _sample_recipe(
            defaults_include=["intro"],
            rules=[{"when": {"tier": "premium"}, "include": ["sla_clause"]}],
        )
        request = _sample_request(options={"tier": "premium"})
        result = resolve_blocks(request, recipe)
        assert "sla_clause" in result
        assert "intro" in result

    def test_conflict_raises_error(self):
        # Two rules both matching: one includes a block, another excludes the same block
        recipe = _sample_recipe(
            defaults_include=[],
            rules=[
                {"when": {"tier": "premium"}, "include": ["sla_clause"]},
                {"when": {"region": "eu"}, "exclude": ["sla_clause"]},
            ],
        )
        request = _sample_request(options={"tier": "premium", "region": "eu"})
        with pytest.raises(RecipeConflictError) as exc_info:
            resolve_blocks(request, recipe)
        assert "sla_clause" in exc_info.value.block_ids

    def test_conflict_error_lists_all_conflicting_blocks(self):
        recipe = _sample_recipe(
            defaults_include=[],
            rules=[
                {"when": {"x": "y"}, "include": ["block_a", "block_b"]},
                {"when": {"p": "q"}, "exclude": ["block_a", "block_b"]},
            ],
        )
        request = _sample_request(options={"x": "y", "p": "q"})
        with pytest.raises(RecipeConflictError) as exc_info:
            resolve_blocks(request, recipe)
        assert set(exc_info.value.block_ids) == {"block_a", "block_b"}

    def test_defaults_include_can_be_excluded_by_rule_without_conflict(self):
        """Excluding a defaults block via rule is NOT a conflict — it is the intended behavior."""
        recipe = _sample_recipe(
            defaults_include=["intro", "annex"],
            rules=[{"when": {"tier": "basic"}, "exclude": ["annex"]}],
        )
        request = _sample_request(options={"tier": "basic"})
        result = resolve_blocks(request, recipe)
        assert "annex" not in result
        assert "intro" in result

    def test_result_is_sorted(self):
        recipe = _sample_recipe(defaults_include=["zzz", "aaa", "mmm"])
        result = resolve_blocks(_sample_request(), recipe)
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# Dry-run tests
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_emits_dry_run_complete(self, capsys):
        recipe = _sample_recipe(defaults_include=["intro", "body"])
        workspace = _sample_workspace()
        events, code = _capture_events(
            capsys,
            assemble,
            _sample_request(),
            recipe,
            workspace,
            dry_run=True,
        )
        dry_run_events = [e for e in events if e["event"] == "dry_run_complete"]
        assert len(dry_run_events) == 1

    def test_dry_run_exits_0(self, capsys):
        recipe = _sample_recipe(defaults_include=["intro"])
        workspace = _sample_workspace()
        events, code = _capture_events(
            capsys, assemble, _sample_request(), recipe, workspace, dry_run=True
        )
        assert code == 0

    def test_dry_run_resolved_blocks_in_detail(self, capsys):
        recipe = _sample_recipe(defaults_include=["intro", "body"])
        workspace = _sample_workspace()
        events, _ = _capture_events(
            capsys, assemble, _sample_request(), recipe, workspace, dry_run=True
        )
        dry_event = next(e for e in events if e["event"] == "dry_run_complete")
        assert "resolved_blocks" in dry_event["detail"]
        assert set(dry_event["detail"]["resolved_blocks"]) == {"intro", "body"}

    def test_dry_run_request_id_in_detail(self, capsys):
        recipe = _sample_recipe(defaults_include=["intro"])
        workspace = _sample_workspace()
        request = _sample_request(request_id="req_dry_123")
        events, _ = _capture_events(
            capsys, assemble, request, recipe, workspace, dry_run=True
        )
        dry_event = next(e for e in events if e["event"] == "dry_run_complete")
        assert dry_event["detail"]["request_id"] == "req_dry_123"

    def test_dry_run_does_not_call_drive(self, capsys):
        recipe = _sample_recipe(defaults_include=["intro"])
        workspace = _sample_workspace()
        drive = FakeDriveClient(
            meta={"id": "m", "name": "Master", "headRevisionId": "rev_001"},
            copy_result={"id": "new_doc"},
        )
        _capture_events(
            capsys, assemble, _sample_request(), recipe, workspace, dry_run=True, drive_client=drive
        )
        assert drive.files().copy_calls == []

    def test_dry_run_conflict_emits_job_failed(self, capsys):
        recipe = _sample_recipe(
            defaults_include=[],
            rules=[
                {"when": {"flag": "on"}, "include": ["shared"]},
                {"when": {"mode": "strict"}, "exclude": ["shared"]},
            ],
        )
        request = _sample_request(options={"flag": "on", "mode": "strict"})
        workspace = _sample_workspace()
        events, code = _capture_events(
            capsys, assemble, request, recipe, workspace, dry_run=True
        )
        failed_events = [e for e in events if e["event"] == "job_failed"]
        assert len(failed_events) == 1
        assert failed_events[0]["detail"]["error"]["code"] == "recipe_conflict"
        assert code == 1


# ---------------------------------------------------------------------------
# copy_master tests
# ---------------------------------------------------------------------------


class TestCopyMaster:
    def test_returns_output_document_id(self):
        drive = FakeDriveClient(
            meta={"id": "master_id", "name": "Master", "headRevisionId": "rev_001"},
            copy_result={"id": "new_doc_id"},
        )
        workspace = _sample_workspace(master_id="master_id", approved_rev="rev_001")
        result = copy_master(drive, workspace)
        assert result["output_document_id"] == "new_doc_id"

    def test_returns_master_revision_id(self):
        drive = FakeDriveClient(
            meta={"id": "master_id", "name": "Master", "headRevisionId": "rev_abc"},
            copy_result={"id": "new_doc_id"},
        )
        workspace = _sample_workspace(master_id="master_id", approved_rev="rev_abc")
        result = copy_master(drive, workspace)
        assert result["master_revision_id"] == "rev_abc"

    def test_revision_mismatch_raises_error(self):
        drive = FakeDriveClient(
            meta={"id": "master_id", "name": "Master", "headRevisionId": "rev_NEW"},
            copy_result={"id": "new_doc_id"},
        )
        workspace = _sample_workspace(master_id="master_id", approved_rev="rev_APPROVED")
        with pytest.raises(MasterRevisionMismatchError) as exc_info:
            copy_master(drive, workspace)
        assert exc_info.value.expected == "rev_APPROVED"
        assert exc_info.value.actual == "rev_NEW"

    def test_empty_approved_rev_skips_check(self):
        drive = FakeDriveClient(
            meta={"id": "master_id", "name": "Master", "headRevisionId": "anything"},
            copy_result={"id": "new_doc_id"},
        )
        workspace = _sample_workspace(master_id="master_id", approved_rev="")
        result = copy_master(drive, workspace)  # should not raise
        assert result["output_document_id"] == "new_doc_id"

    def test_copy_called_with_correct_parent(self):
        drive = FakeDriveClient(
            meta={"id": "master_id", "name": "Master", "headRevisionId": "rev_001"},
            copy_result={"id": "new_doc_id"},
        )
        workspace = _sample_workspace(
            master_id="master_id", approved_rev="rev_001", review_folder="review_folder_xyz"
        )
        copy_master(drive, workspace)
        assert drive.files().copy_calls[0]["body"]["parents"] == ["review_folder_xyz"]


# ---------------------------------------------------------------------------
# prune_blocks tests
# ---------------------------------------------------------------------------


class TestPruneBlocks:
    def test_prunes_unrequested_block(self):
        doc = _make_document("intro", "annex")
        docs = FakeDocsClient(doc)
        pruned = prune_blocks(docs, "doc_id", ["intro"])
        assert pruned == ["annex"]

    def test_no_pruning_when_all_blocks_resolved(self):
        doc = _make_document("intro", "body")
        docs = FakeDocsClient(doc)
        pruned = prune_blocks(docs, "doc_id", ["intro", "body"])
        assert pruned == []
        assert docs.documents().batch_update_calls == []

    def test_prune_multiple_blocks(self):
        doc = _make_document("intro", "annex", "sla")
        docs = FakeDocsClient(doc)
        pruned = prune_blocks(docs, "doc_id", ["intro"])
        assert set(pruned) == {"annex", "sla"}

    def test_batchupdate_called_when_pruning(self):
        doc = _make_document("intro", "annex")
        docs = FakeDocsClient(doc)
        prune_blocks(docs, "doc_id", ["intro"])
        assert len(docs.documents().batch_update_calls) == 1

    def test_no_batchupdate_when_nothing_to_prune(self):
        doc = _make_document("intro")
        docs = FakeDocsClient(doc)
        prune_blocks(docs, "doc_id", ["intro"])
        assert docs.documents().batch_update_calls == []

    def test_delete_ranges_sorted_descending(self):
        """Verify deleteContentRange requests are sorted descending by startIndex (TL-01)."""
        doc = _make_document("intro", "annex", "sla")
        docs = FakeDocsClient(doc)
        prune_blocks(docs, "doc_id", ["intro"])  # keep intro, delete annex + sla
        calls = docs.documents().batch_update_calls
        assert len(calls) == 1
        requests = calls[0]["body"]["requests"]
        start_indices = [
            r["deleteContentRange"]["range"]["startIndex"] for r in requests
        ]
        # Must be sorted descending (TL-01)
        assert start_indices == sorted(start_indices, reverse=True)

    def test_empty_document_returns_empty(self):
        doc = {"body": {"content": []}}
        docs = FakeDocsClient(doc)
        pruned = prune_blocks(docs, "doc_id", [])
        assert pruned == []


# ---------------------------------------------------------------------------
# _get_excluded_ranges tests
# ---------------------------------------------------------------------------


class TestGetExcludedRanges:
    def test_excludes_unrequested_block(self):
        markers = [
            {"kind": "BLOCK", "block_id": "intro", "start_index": 1, "end_index": 20},
            {"kind": "/BLOCK", "block_id": "intro", "start_index": 100, "end_index": 120},
            {"kind": "BLOCK", "block_id": "annex", "start_index": 200, "end_index": 220},
            {"kind": "/BLOCK", "block_id": "annex", "start_index": 300, "end_index": 320},
        ]
        ranges = _get_excluded_ranges(markers, ["intro"])
        assert (200, 320) in ranges
        assert (1, 120) not in ranges

    def test_all_resolved_returns_empty(self):
        markers = [
            {"kind": "BLOCK", "block_id": "intro", "start_index": 1, "end_index": 10},
            {"kind": "/BLOCK", "block_id": "intro", "start_index": 50, "end_index": 60},
        ]
        ranges = _get_excluded_ranges(markers, ["intro"])
        assert ranges == []


# ---------------------------------------------------------------------------
# Full assemble pipeline tests
# ---------------------------------------------------------------------------


class TestAssemblePipeline:
    def _make_clients(self, block_ids=None, approved_rev="rev_001"):
        block_ids = block_ids or ["intro", "body"]
        drive = FakeDriveClient(
            meta={"id": "master", "name": "Master", "headRevisionId": approved_rev},
            copy_result={"id": "output_doc_123"},
        )
        # Pipeline calls docs.get() multiple times:
        #   prune_blocks, strip_markers, verify_output
        # Supply a clean document for strip+verify calls so the pipeline exits 0.
        doc_with_markers = _make_document(*block_ids)
        clean_doc = _make_clean_document()
        docs = FakeDocsClientMulti(doc_with_markers, clean_doc, clean_doc)
        return drive, docs

    def test_full_run_exits_0(self, capsys):
        drive, docs = self._make_clients()
        recipe = _sample_recipe(defaults_include=["intro", "body"])
        workspace = _sample_workspace(approved_rev="rev_001")
        events, code = _capture_events(
            capsys, assemble, _sample_request(), recipe, workspace,
            drive_client=drive, docs_client=docs
        )
        assert code == 0

    def test_full_run_emits_job_completed(self, capsys):
        drive, docs = self._make_clients()
        recipe = _sample_recipe(defaults_include=["intro", "body"])
        workspace = _sample_workspace(approved_rev="rev_001")
        events, _ = _capture_events(
            capsys, assemble, _sample_request(), recipe, workspace,
            drive_client=drive, docs_client=docs
        )
        completed = [e for e in events if e["event"] == "job_completed"]
        assert len(completed) == 1

    def test_full_run_events_all_valid_json(self, capsys):
        drive, docs = self._make_clients()
        recipe = _sample_recipe(defaults_include=["intro", "body"])
        workspace = _sample_workspace(approved_rev="rev_001")
        events, _ = _capture_events(
            capsys, assemble, _sample_request(), recipe, workspace,
            drive_client=drive, docs_client=docs
        )
        for event in events:
            assert "event" in event
            assert "step" in event
            assert "job_id" in event
            assert "detail" in event

    def test_revision_mismatch_exits_1(self, capsys):
        drive = FakeDriveClient(
            meta={"id": "master", "name": "Master", "headRevisionId": "rev_NEW"},
            copy_result={"id": "out"},
        )
        docs = FakeDocsClient(_make_document("intro"))
        recipe = _sample_recipe(defaults_include=["intro"])
        workspace = _sample_workspace(approved_rev="rev_OLD")
        events, code = _capture_events(
            capsys, assemble, _sample_request(), recipe, workspace,
            drive_client=drive, docs_client=docs
        )
        assert code == 1
        failed = [e for e in events if e["event"] == "job_failed"]
        assert failed[0]["detail"]["error"]["code"] == "master_revision_mismatch"

    def test_ledger_job_created_on_full_run(self, capsys):
        drive, docs = self._make_clients()
        recipe = _sample_recipe(defaults_include=["intro", "body"])
        workspace = _sample_workspace(approved_rev="rev_001")

        # Import InMemoryLedgerAdapter from ledger module
        ledger_dir = SCRIPTS_DIR
        sys.path.insert(0, ledger_dir)
        from ledger import InMemoryLedgerAdapter
        ledger = InMemoryLedgerAdapter()

        events, code = _capture_events(
            capsys, assemble, _sample_request(), recipe, workspace,
            drive_client=drive, docs_client=docs, ledger=ledger
        )
        assert code == 0
        # Job should be in the ledger
        job_event = next(e for e in events if e["event"] == "job_completed")
        job_id = job_event["job_id"]
        stored = ledger.get_job(job_id)
        assert stored["output_document_id"] == "output_doc_123"


# ---------------------------------------------------------------------------
# Security: no live API calls in this file
# ---------------------------------------------------------------------------


class TestNoLiveApiCalls:
    def test_no_build_drive_call_in_test_file(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_assemble_copy_prune.py")
        with open(test_file) as f:
            source = f.read()
        pattern = "build" + '("drive"'
        assert pattern not in source

    def test_no_build_docs_call_in_test_file(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_assemble_copy_prune.py")
        with open(test_file) as f:
            source = f.read()
        pattern = "build" + '("docs"'
        assert pattern not in source
