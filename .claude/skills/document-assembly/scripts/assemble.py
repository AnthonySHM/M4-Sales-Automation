"""
assemble.py — Core job runner for document assembly.

Steps implemented:
  validate_request → resolve_blocks → copy_master → prune_blocks
  → fill_placeholders → strip_markers → verify_output → submit_for_review

Exit codes:
  0 — job completed (or dry-run complete)
  1 — validation / logic error (non-retryable)
  2 — external / transient error (retryable)
  3 — credential / permission error

Advances AD-03, G-04, G-05, G-07, G-08, G-09, G-10, G-13, TL-01, NF-06.
Full implementation for Issues #13–#15.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from datetime import datetime, timezone


MARKER_RE = re.compile(r"\{\{(BEGIN|END):([a-z0-9_]{3,64})\}\}")


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class RecipeConflictError(Exception):
    """A block_id is both included and excluded by recipe rules."""

    def __init__(self, block_ids: list[str]) -> None:
        self.block_ids = block_ids
        super().__init__(f"Recipe conflict on blocks: {block_ids}")


class MasterRevisionMismatchError(Exception):
    """Live master headRevisionId differs from workspace approved_revision_id."""

    def __init__(self, expected: str, actual: str) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Master revision mismatch: expected {expected!r}, got {actual!r}"
        )


class UnknownOptionError(Exception):
    """Request option not defined in recipe."""


class MissingPlaceholderError(Exception):
    """Required placeholder value absent from request."""


class MarkerError(Exception):
    """Unbalanced, nested, or duplicate markers in master."""


class GoogleApiError(Exception):
    """Transient or permanent Google API failure."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        self.retryable = retryable
        super().__init__(message)


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


def _emit(event: dict) -> None:
    """Write one newline-delimited JSON event to stdout (Architecture §4.4)."""
    print(json.dumps(event), flush=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Retry helper (NF-06)
# ---------------------------------------------------------------------------


def _with_retry(fn, max_attempts: int = 5, base_delay: float = 1.0):
    """Call fn() up to max_attempts times with exponential backoff (NF-06).

    Retries only on GoogleApiError(retryable=True). Propagates immediately on
    non-retryable errors or once max_attempts is exhausted.
    """
    for attempt in range(max_attempts):
        try:
            return fn()
        except GoogleApiError as exc:
            if not exc.retryable or attempt >= max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
    raise RuntimeError("_with_retry: unreachable")  # pragma: no cover


# ---------------------------------------------------------------------------
# Block resolution
# ---------------------------------------------------------------------------


def resolve_blocks(request: dict, recipe: dict) -> list[str]:
    """Apply recipe rules to request options and return sorted block_id list to keep.

    Algorithm:
      1. Collect rule_included and rule_excluded from all matching rules.
      2. Conflict: a block explicitly added by one rule AND excluded by another → RecipeConflictError.
      3. Final set = (defaults.include | rule_included) - rule_excluded.

    Raises RecipeConflictError if any block appears in both rule include and rule exclude sets.
    """
    defaults_included: set[str] = set(recipe.get("defaults", {}).get("include", []))
    rule_included: set[str] = set()
    rule_excluded: set[str] = set()

    options = request.get("options", {})
    for rule in recipe.get("rules", []):
        when = rule.get("when", {})
        if all(options.get(k) == v for k, v in when.items()):
            rule_included.update(rule.get("include", []))
            rule_excluded.update(rule.get("exclude", []))

    # Conflict: a block is explicitly both included and excluded by matching rules
    conflicts = sorted(rule_included & rule_excluded)
    if conflicts:
        raise RecipeConflictError(conflicts)

    return sorted((defaults_included | rule_included) - rule_excluded)


# ---------------------------------------------------------------------------
# Marker extraction
# ---------------------------------------------------------------------------


def _extract_all_markers(document: dict) -> list[dict]:
    """Return ordered list of all marker dicts (BEGIN + END) with character positions."""
    markers = []
    for element in document.get("body", {}).get("content", []):
        paragraph = element.get("paragraph", {})
        for elem in paragraph.get("elements", []):
            text = elem.get("textRun", {}).get("content", "")
            for match in MARKER_RE.finditer(text):
                markers.append(
                    {
                        "kind": match.group(1),
                        "block_id": match.group(2),
                        "start_index": elem.get("startIndex", 0),
                        "end_index": elem.get("endIndex", 0),
                    }
                )
    return markers


def _get_excluded_ranges(
    markers: list[dict], resolved_blocks: list[str]
) -> list[tuple[int, int]]:
    """Return (start_index, end_index) ranges for blocks NOT in resolved_blocks.

    Each range spans from the BEGIN marker's startIndex to the END marker's endIndex.
    """
    resolved_set = set(resolved_blocks)
    begin_map: dict[str, int] = {}
    ranges: list[tuple[int, int]] = []

    for m in markers:
        if m["kind"] == "BEGIN":
            begin_map[m["block_id"]] = m["start_index"]
        elif m["kind"] == "END" and m["block_id"] in begin_map:
            block_id = m["block_id"]
            start = begin_map.pop(block_id)
            if block_id not in resolved_set:
                ranges.append((start, m["end_index"]))

    return ranges


# ---------------------------------------------------------------------------
# copy_master step
# ---------------------------------------------------------------------------


def copy_master(drive_client, workspace: dict) -> dict:
    """Copy master template to review folder. Returns output_document_id + master_revision_id.

    Parameters
    ----------
    drive_client:
        An authenticated Drive v3 resource (injected; never built inside this function).
    workspace:
        Loaded workspace.yaml dict.

    Raises
    ------
    MasterRevisionMismatchError:
        If the live master headRevisionId differs from workspace approved_revision_id.
    """
    family = workspace.get("pilot_family", {})
    master_id: str = family["master_template_id"]
    approved_rev: str = family.get("approved_revision_id", "")
    review_folder: str = workspace["folders"]["review"]

    # Fetch current master metadata
    meta = (
        drive_client.files()
        .get(fileId=master_id, fields="id,name,headRevisionId", supportsAllDrives=True)
        .execute()
    )
    live_rev: str = meta.get("headRevisionId", "")

    # Revision guard (G-08): skip check when approved_rev is empty
    if approved_rev and live_rev != approved_rev:
        raise MasterRevisionMismatchError(approved_rev, live_rev)

    # Copy master to review folder
    suffix = uuid.uuid4().hex[:8]
    copy_name = f"{meta.get('name', 'document')} — draft {suffix}"
    new_file = (
        drive_client.files()
        .copy(
            fileId=master_id,
            supportsAllDrives=True,
            body={"parents": [review_folder], "name": copy_name},
        )
        .execute()
    )

    return {
        "output_document_id": new_file["id"],
        "master_revision_id": live_rev,
    }


# ---------------------------------------------------------------------------
# Quarantine helper (G-10)
# ---------------------------------------------------------------------------


def _quarantine_document(drive_client, output_doc_id: str, workspace: dict) -> None:
    """Move a partial output document from review/ to quarantine/ (G-10).

    Uses Drive files.update with addParents / removeParents (best-effort; caller
    swallows any exception so the original error is never obscured).
    """
    quarantine_folder: str = workspace["folders"]["quarantine"]
    review_folder: str = workspace["folders"]["review"]
    drive_client.files().update(
        fileId=output_doc_id,
        addParents=quarantine_folder,
        removeParents=review_folder,
        supportsAllDrives=True,
        fields="id,parents",
    ).execute()


# ---------------------------------------------------------------------------
# prune_blocks step
# ---------------------------------------------------------------------------


def prune_blocks(
    docs_client, output_doc_id: str, resolved_blocks: list[str]
) -> list[str]:
    """Delete unwanted block ranges from the copied document.

    Ranges are sorted descending by startIndex before deletion (TL-01) so that
    earlier deletions do not shift the character indices of later ones.

    Returns list of pruned block_ids.
    """
    document = docs_client.documents().get(documentId=output_doc_id).execute()
    markers = _extract_all_markers(document)

    resolved_set = set(resolved_blocks)
    doc_block_ids = {m["block_id"] for m in markers if m["kind"] == "BEGIN"}
    pruned = sorted(doc_block_ids - resolved_set)

    if not pruned:
        return []

    ranges = _get_excluded_ranges(markers, resolved_blocks)
    if not ranges:
        return []

    # Sort descending by startIndex (TL-01)
    ranges.sort(key=lambda r: r[0], reverse=True)

    requests = [
        {"deleteContentRange": {"range": {"startIndex": si, "endIndex": ei}}}
        for si, ei in ranges
    ]

    docs_client.documents().batchUpdate(
        documentId=output_doc_id,
        body={"requests": requests},
    ).execute()

    return pruned


# ---------------------------------------------------------------------------
# fill_placeholders step
# ---------------------------------------------------------------------------

PLACEHOLDER_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")


def fill_placeholders(
    docs_client, output_doc_id: str, placeholder_map: dict, placeholder_values: dict
) -> list[str]:
    """Replace all placeholder strings in the document.

    Parameters
    ----------
    docs_client:
        Injected Docs v1 resource.
    output_doc_id:
        ID of the copied (not master) document to mutate.
    placeholder_map:
        From recipe: {PLACEHOLDER_KEY: request_field_name}.
    placeholder_values:
        From request: {PLACEHOLDER_KEY: replacement_value}.

    Returns list of replaced placeholder keys.

    Raises MissingPlaceholderError if any key in placeholder_map is absent
    from placeholder_values.

    Security: replacement values are never written to stdout (SB-06).
    """
    missing = [k for k in placeholder_map if k not in placeholder_values]
    if missing:
        raise MissingPlaceholderError(sorted(missing))

    if not placeholder_map:
        return []

    requests = []
    replaced_keys = []
    for ph_key in placeholder_map:
        value = placeholder_values[ph_key]
        requests.append(
            {
                "replaceAllText": {
                    "containsText": {"text": "{{" + ph_key + "}}", "matchCase": True},
                    "replaceText": value,
                }
            }
        )
        replaced_keys.append(ph_key)

    docs_client.documents().batchUpdate(
        documentId=output_doc_id,
        body={"requests": requests},
    ).execute()

    return sorted(replaced_keys)


# ---------------------------------------------------------------------------
# strip_markers step
# ---------------------------------------------------------------------------


def strip_markers(docs_client, output_doc_id: str) -> list[str]:
    """Remove any remaining {{BEGIN:*}} and {{END:*}} marker strings from the document.

    Uses replaceAllText with an empty replacement string.
    Returns list of unique marker patterns that were present (e.g. "{{BEGIN:foo}}").
    """
    document = docs_client.documents().get(documentId=output_doc_id).execute()
    markers = _extract_all_markers(document)

    if not markers:
        return []

    # Collect unique marker strings
    unique_patterns: set[str] = set()
    for m in markers:
        unique_patterns.add("{{" + m["kind"] + ":" + m["block_id"] + "}}")

    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": pattern, "matchCase": True},
                "replaceText": "",
            }
        }
        for pattern in sorted(unique_patterns)
    ]

    docs_client.documents().batchUpdate(
        documentId=output_doc_id,
        body={"requests": requests},
    ).execute()

    return sorted(unique_patterns)


# ---------------------------------------------------------------------------
# verify_output step
# ---------------------------------------------------------------------------


def verify_output(docs_client, output_doc_id: str) -> None:
    """Re-read the document and assert zero leftover markers and placeholders.

    Raises MarkerError if any {{BEGIN:*}} or {{END:*}} strings remain.
    Raises MissingPlaceholderError if any {{[A-Z0-9_]+}} strings remain.
    """
    document = docs_client.documents().get(documentId=output_doc_id).execute()

    # Collect all text from document
    all_text = []
    for element in document.get("body", {}).get("content", []):
        paragraph = element.get("paragraph", {})
        for elem in paragraph.get("elements", []):
            text = elem.get("textRun", {}).get("content", "")
            all_text.append(text)
    full_text = "".join(all_text)

    # Check for leftover markers
    leftover_markers = MARKER_RE.findall(full_text)
    if leftover_markers:
        found = sorted({f"{{{{{k}:{v}}}}}" for k, v in leftover_markers})
        raise MarkerError(f"Leftover markers after strip: {found}")

    # Check for leftover placeholders
    leftover_placeholders = PLACEHOLDER_RE.findall(full_text)
    if leftover_placeholders:
        found = sorted(set(leftover_placeholders))
        raise MissingPlaceholderError(found)


# ---------------------------------------------------------------------------
# submit_for_review step (G-07, AD-10)
# ---------------------------------------------------------------------------


def submit_for_review(drive_client, output_doc_id: str, workspace: dict) -> dict:
    """Verify the output document is accessible in the review folder.

    The document was already placed in review/ by copy_master. This step
    performs a lightweight files.get to confirm accessibility before handing
    off to the human review gate (AD-10).

    Returns dict with output_document_id and document_name.
    """
    meta = (
        drive_client.files()
        .get(
            fileId=output_doc_id,
            fields="id,name,parents",
            supportsAllDrives=True,
        )
        .execute()
    )
    return {
        "output_document_id": output_doc_id,
        "document_name": meta.get("name", ""),
    }


# ---------------------------------------------------------------------------
# Assembly orchestration
# ---------------------------------------------------------------------------


def assemble(
    request_data: dict,
    recipe_data: dict,
    workspace: dict,
    *,
    dry_run: bool = False,
    drive_client=None,
    docs_client=None,
    ledger=None,
    job_id: str | None = None,
) -> int:
    """Run the assembly pipeline. Emits streaming events to stdout. Returns exit code.

    Parameters
    ----------
    request_data, recipe_data, workspace:
        Pre-loaded dicts from JSON/YAML files.
    dry_run:
        Stop after resolve_blocks without touching Drive/Docs.
    drive_client, docs_client:
        Injected Google API clients; built from credentials only in main().
    ledger:
        Injected LedgerAdapter; created from workspace config only in main().
    job_id:
        Pre-assigned job_id for idempotent retries.
    """
    request_id = request_data.get("request_id")
    workspace_id = workspace.get("workspace_id", "")
    run_by = request_data.get("requested_by", "")

    # ------------------------------------------------------------------
    # Step: resolve_blocks
    # ------------------------------------------------------------------
    _emit({"event": "step_started", "step": "resolve_blocks", "job_id": job_id, "detail": {}})

    try:
        resolved_blocks = resolve_blocks(request_data, recipe_data)
    except RecipeConflictError as exc:
        _emit(
            {
                "event": "job_failed",
                "step": "resolve_blocks",
                "job_id": job_id,
                "detail": {
                    "error": {
                        "code": "recipe_conflict",
                        "message": str(exc),
                        "retryable": False,
                        "block_ids": exc.block_ids,
                    }
                },
            }
        )
        return 1

    _emit(
        {
            "event": "step_succeeded",
            "step": "resolve_blocks",
            "job_id": job_id,
            "detail": {"resolved_blocks": resolved_blocks},
        }
    )

    # ------------------------------------------------------------------
    # Dry-run: stop here
    # ------------------------------------------------------------------
    if dry_run:
        _emit(
            {
                "event": "dry_run_complete",
                "step": "resolve_blocks",
                "job_id": None,
                "detail": {
                    "request_id": request_id,
                    "family_key": request_data.get("family_key"),
                    "resolved_blocks": resolved_blocks,
                },
            }
        )
        return 0

    # ------------------------------------------------------------------
    # Ledger: create or recover job
    # ------------------------------------------------------------------
    if ledger is not None:
        if request_id:
            existing = ledger.find_job_by_request_id(request_id, workspace_id)
            if existing:
                job_id = existing["job_id"]
            else:
                job_id = ledger.create_job(
                    {
                        "request_id": request_id,
                        "workspace_id": workspace_id,
                        "family_key": request_data.get("family_key"),
                        "status": "building",
                        "run_by": run_by,
                        "started_at": _now_iso(),
                        "resolved_blocks": resolved_blocks,
                    }
                )
        else:
            job_id = ledger.create_job(
                {
                    "workspace_id": workspace_id,
                    "status": "building",
                    "run_by": run_by,
                    "started_at": _now_iso(),
                }
            )

    if job_id is None:
        job_id = "job_" + uuid.uuid4().hex[:12]

    # ------------------------------------------------------------------
    # Step: copy_master
    # ------------------------------------------------------------------
    _emit({"event": "step_started", "step": "copy_master", "job_id": job_id, "detail": {}})

    try:
        copy_result = copy_master(drive_client, workspace)
    except MasterRevisionMismatchError as exc:
        _emit(
            {
                "event": "job_failed",
                "step": "copy_master",
                "job_id": job_id,
                "detail": {
                    "error": {
                        "code": "master_revision_mismatch",
                        "message": str(exc),
                        "retryable": False,
                        "expected": exc.expected,
                        "actual": exc.actual,
                    }
                },
            }
        )
        if ledger and job_id:
            try:
                ledger.update_job(job_id, {"status": "failed", "finished_at": _now_iso()})
            except Exception:  # noqa: BLE001
                pass
        return 1
    except Exception as exc:  # noqa: BLE001
        _emit(
            {
                "event": "job_failed",
                "step": "copy_master",
                "job_id": job_id,
                "detail": {
                    "error": {"code": "api_error", "message": str(exc), "retryable": True}
                },
            }
        )
        if ledger and job_id:
            try:
                ledger.update_job(job_id, {"status": "failed", "finished_at": _now_iso()})
            except Exception:  # noqa: BLE001
                pass
        return 2

    output_doc_id = copy_result["output_document_id"]
    master_rev = copy_result["master_revision_id"]

    if ledger and job_id:
        ledger.update_job(
            job_id,
            {"output_document_id": output_doc_id, "master_revision_id": master_rev},
        )

    _emit(
        {
            "event": "step_succeeded",
            "step": "copy_master",
            "job_id": job_id,
            "detail": {
                "output_document_id": output_doc_id,
                "master_revision_id": master_rev,
            },
        }
    )

    # ------------------------------------------------------------------
    # Step: prune_blocks
    # ------------------------------------------------------------------
    _emit({"event": "step_started", "step": "prune_blocks", "job_id": job_id, "detail": {}})

    try:
        pruned = prune_blocks(docs_client, output_doc_id, resolved_blocks)
    except Exception as exc:  # noqa: BLE001
        _emit(
            {
                "event": "job_failed",
                "step": "prune_blocks",
                "job_id": job_id,
                "detail": {
                    "error": {"code": "api_error", "message": str(exc), "retryable": True}
                },
            }
        )
        try:
            _quarantine_document(drive_client, output_doc_id, workspace)
        except Exception:  # noqa: BLE001
            pass
        if ledger and job_id:
            try:
                ledger.update_job(job_id, {"status": "failed", "finished_at": _now_iso()})
            except Exception:  # noqa: BLE001
                pass
        return 2

    _emit(
        {
            "event": "step_succeeded",
            "step": "prune_blocks",
            "job_id": job_id,
            "detail": {"pruned_blocks": pruned},
        }
    )

    # ------------------------------------------------------------------
    # Step: fill_placeholders
    # ------------------------------------------------------------------
    _emit({"event": "step_started", "step": "fill_placeholders", "job_id": job_id, "detail": {}})

    try:
        replaced_keys = fill_placeholders(
            docs_client,
            output_doc_id,
            recipe_data.get("placeholder_map", {}),
            request_data.get("placeholder_values", {}),
        )
    except MissingPlaceholderError as exc:
        _emit(
            {
                "event": "job_failed",
                "step": "fill_placeholders",
                "job_id": job_id,
                "detail": {
                    "error": {
                        "code": "missing_placeholder",
                        "message": str(exc),
                        "retryable": False,
                        # Note: do NOT include actual values — SB-06
                        "missing_keys": exc.args[0] if exc.args else [],
                    }
                },
            }
        )
        try:
            _quarantine_document(drive_client, output_doc_id, workspace)
        except Exception:  # noqa: BLE001
            pass
        if ledger and job_id:
            try:
                ledger.update_job(job_id, {"status": "failed", "finished_at": _now_iso()})
            except Exception:  # noqa: BLE001
                pass
        return 1
    except Exception as exc:  # noqa: BLE001
        _emit(
            {
                "event": "job_failed",
                "step": "fill_placeholders",
                "job_id": job_id,
                "detail": {
                    "error": {"code": "api_error", "message": str(exc), "retryable": True}
                },
            }
        )
        try:
            _quarantine_document(drive_client, output_doc_id, workspace)
        except Exception:  # noqa: BLE001
            pass
        if ledger and job_id:
            try:
                ledger.update_job(job_id, {"status": "failed", "finished_at": _now_iso()})
            except Exception:  # noqa: BLE001
                pass
        return 2

    _emit(
        {
            "event": "step_succeeded",
            "step": "fill_placeholders",
            "job_id": job_id,
            "detail": {"replaced_keys": replaced_keys},
        }
    )

    # ------------------------------------------------------------------
    # Step: strip_markers
    # ------------------------------------------------------------------
    _emit({"event": "step_started", "step": "strip_markers", "job_id": job_id, "detail": {}})

    try:
        stripped = strip_markers(docs_client, output_doc_id)
    except Exception as exc:  # noqa: BLE001
        _emit(
            {
                "event": "job_failed",
                "step": "strip_markers",
                "job_id": job_id,
                "detail": {
                    "error": {"code": "api_error", "message": str(exc), "retryable": True}
                },
            }
        )
        try:
            _quarantine_document(drive_client, output_doc_id, workspace)
        except Exception:  # noqa: BLE001
            pass
        if ledger and job_id:
            try:
                ledger.update_job(job_id, {"status": "failed", "finished_at": _now_iso()})
            except Exception:  # noqa: BLE001
                pass
        return 2

    _emit(
        {
            "event": "step_succeeded",
            "step": "strip_markers",
            "job_id": job_id,
            "detail": {"stripped_markers": stripped},
        }
    )

    # ------------------------------------------------------------------
    # Step: verify_output
    # ------------------------------------------------------------------
    _emit({"event": "step_started", "step": "verify_output", "job_id": job_id, "detail": {}})

    try:
        verify_output(docs_client, output_doc_id)
    except MarkerError as exc:
        _emit(
            {
                "event": "job_failed",
                "step": "verify_output",
                "job_id": job_id,
                "detail": {
                    "error": {
                        "code": "marker_error",
                        "message": str(exc),
                        "retryable": False,
                    }
                },
            }
        )
        try:
            _quarantine_document(drive_client, output_doc_id, workspace)
        except Exception:  # noqa: BLE001
            pass
        if ledger and job_id:
            try:
                ledger.update_job(job_id, {"status": "failed", "finished_at": _now_iso()})
            except Exception:  # noqa: BLE001
                pass
        return 1
    except MissingPlaceholderError as exc:
        _emit(
            {
                "event": "job_failed",
                "step": "verify_output",
                "job_id": job_id,
                "detail": {
                    "error": {
                        "code": "missing_placeholder",
                        "message": str(exc),
                        "retryable": False,
                    }
                },
            }
        )
        try:
            _quarantine_document(drive_client, output_doc_id, workspace)
        except Exception:  # noqa: BLE001
            pass
        if ledger and job_id:
            try:
                ledger.update_job(job_id, {"status": "failed", "finished_at": _now_iso()})
            except Exception:  # noqa: BLE001
                pass
        return 1
    except Exception as exc:  # noqa: BLE001
        _emit(
            {
                "event": "job_failed",
                "step": "verify_output",
                "job_id": job_id,
                "detail": {
                    "error": {"code": "api_error", "message": str(exc), "retryable": True}
                },
            }
        )
        try:
            _quarantine_document(drive_client, output_doc_id, workspace)
        except Exception:  # noqa: BLE001
            pass
        if ledger and job_id:
            try:
                ledger.update_job(job_id, {"status": "failed", "finished_at": _now_iso()})
            except Exception:  # noqa: BLE001
                pass
        return 2

    _emit(
        {
            "event": "step_succeeded",
            "step": "verify_output",
            "job_id": job_id,
            "detail": {},
        }
    )

    # ------------------------------------------------------------------
    # Step: submit_for_review
    # ------------------------------------------------------------------
    _emit({"event": "step_started", "step": "submit_for_review", "job_id": job_id, "detail": {}})

    try:
        review_result = submit_for_review(drive_client, output_doc_id, workspace)
    except Exception as exc:  # noqa: BLE001
        _emit(
            {
                "event": "job_failed",
                "step": "submit_for_review",
                "job_id": job_id,
                "detail": {
                    "error": {"code": "api_error", "message": str(exc), "retryable": True}
                },
            }
        )
        try:
            _quarantine_document(drive_client, output_doc_id, workspace)
        except Exception:  # noqa: BLE001
            pass
        if ledger and job_id:
            try:
                ledger.update_job(job_id, {"status": "failed", "finished_at": _now_iso()})
            except Exception:  # noqa: BLE001
                pass
        return 2

    _emit(
        {
            "event": "step_succeeded",
            "step": "submit_for_review",
            "job_id": job_id,
            "detail": review_result,
        }
    )

    _emit(
        {
            "event": "job_completed",
            "step": "submit_for_review",
            "job_id": job_id,
            "detail": {
                "output_document_id": output_doc_id,
                "document_name": review_result.get("document_name", ""),
                "resolved_blocks": resolved_blocks,
                "pruned_blocks": pruned,
                "replaced_keys": replaced_keys,
            },
        }
    )

    if ledger and job_id:
        ledger.update_job(job_id, {"status": "awaiting_review", "finished_at": _now_iso()})

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(json.dumps({"error": {"code": "missing_argument", "message": message}}))
        sys.exit(1)


def main(argv=None, drive_client=None, docs_client=None, ledger=None) -> None:
    parser = _Parser(description="Assemble a document from a request")
    parser.add_argument("--request", required=True, help="Path to request JSON file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve blocks and validate without writing to Drive",
    )
    parser.add_argument(
        "--workspace",
        default="config/workspace.yaml",
        help="Path to workspace.yaml (default: config/workspace.yaml)",
    )
    args = parser.parse_args(argv)

    # Load request
    try:
        with open(args.request) as f:
            request_data = json.load(f)
    except FileNotFoundError:
        _emit(
            {
                "event": "job_failed",
                "step": "validate_request",
                "job_id": None,
                "detail": {
                    "error": {
                        "code": "file_not_found",
                        "message": f"Request file not found: {args.request}",
                        "retryable": False,
                    }
                },
            }
        )
        sys.exit(1)
    except json.JSONDecodeError as exc:
        _emit(
            {
                "event": "job_failed",
                "step": "validate_request",
                "job_id": None,
                "detail": {
                    "error": {
                        "code": "invalid_json",
                        "message": f"Request is not valid JSON: {exc}",
                        "retryable": False,
                    }
                },
            }
        )
        sys.exit(1)

    # Load workspace
    try:
        import yaml  # PyYAML — in requirements.txt

        with open(args.workspace) as f:
            workspace = yaml.safe_load(f)
    except FileNotFoundError:
        _emit(
            {
                "event": "job_failed",
                "step": "validate_request",
                "job_id": None,
                "detail": {
                    "error": {
                        "code": "file_not_found",
                        "message": f"Workspace file not found: {args.workspace}",
                        "retryable": False,
                    }
                },
            }
        )
        sys.exit(1)

    # Derive recipe path from workspace config
    family_key = workspace.get("pilot_family", {}).get("key", "unknown")
    recipe_version = workspace.get("pilot_family", {}).get("active_recipe_version", 1)
    recipe_path = f"config/recipes/{family_key}_v{recipe_version}.json"

    try:
        with open(recipe_path) as f:
            recipe_data = json.load(f)
    except FileNotFoundError:
        _emit(
            {
                "event": "job_failed",
                "step": "validate_request",
                "job_id": None,
                "detail": {
                    "error": {
                        "code": "file_not_found",
                        "message": f"Recipe file not found: {recipe_path}",
                        "retryable": False,
                    }
                },
            }
        )
        sys.exit(1)
    except json.JSONDecodeError as exc:
        _emit(
            {
                "event": "job_failed",
                "step": "validate_request",
                "job_id": None,
                "detail": {
                    "error": {
                        "code": "invalid_json",
                        "message": f"Recipe is not valid JSON: {exc}",
                        "retryable": False,
                    }
                },
            }
        )
        sys.exit(1)

    # Build real API clients only when not injected and not dry-run (skipped in unit tests)
    if not args.dry_run:  # pragma: no cover
        if drive_client is None or docs_client is None:
            try:
                import google.auth
                from googleapiclient.discovery import build as _build

                creds, _ = google.auth.default(
                    scopes=[
                        "https://www.googleapis.com/auth/drive.file",
                        "https://www.googleapis.com/auth/documents",
                    ]
                )
                if drive_client is None:
                    drive_client = _build("drive", "v3", credentials=creds)
                if docs_client is None:
                    docs_client = _build("docs", "v1", credentials=creds)
            except Exception as exc:
                _emit(
                    {
                        "event": "job_failed",
                        "step": "validate_request",
                        "job_id": None,
                        "detail": {
                            "error": {
                                "code": "api_error",
                                "message": f"Failed to build API clients: {exc}",
                                "retryable": False,
                            }
                        },
                    }
                )
                sys.exit(3)

    exit_code = assemble(
        request_data,
        recipe_data,
        workspace,
        dry_run=args.dry_run,
        drive_client=drive_client,
        docs_client=docs_client,
        ledger=ledger,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
