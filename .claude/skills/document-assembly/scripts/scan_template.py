"""
scan_template.py — Validate block markers in a master template Google Doc.

Reads the document via the Docs API and reports:
  - unregistered_markers: in doc but not in registry
  - registry_without_marker: in registry but not in doc
  - duplicate_ids: block_id appears in more than one BEGIN marker
  - unbalanced_markers: BEGIN without END or END without BEGIN
  - nested_markers: a BEGIN appears before the previous END is closed

Exit codes:
  0 — no issues found
  1 — one or more marker issues found, or bad/missing CLI args
  2 — external / transient error (e.g. API 500/503)
  3 — credential / permission error (e.g. API 403)

Advances G-01, AD-05, AD-20. Full implementation for Issue #8.
Importable API added for Issue #38.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

MARKER_RE = re.compile(r"\[\[(/?)BLOCK:([a-z0-9_]{3,64})\]\]")


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({"error": {"code": "missing_argument", "message": message}}))
        sys.exit(1)


def _extract_markers(document):
    """Return ordered list of marker dicts from a Docs API document response.

    Each dict: {kind: "BEGIN"|"END", block_id: str, start_index: int, end_index: int}
    """
    markers = []
    for element in document.get("body", {}).get("content", []):
        paragraph = element.get("paragraph", {})
        for elem in paragraph.get("elements", []):
            text = elem.get("textRun", {}).get("content", "")
            for match in MARKER_RE.finditer(text):
                markers.append(
                    {
                        "kind": "END" if match.group(1) == "/" else "BEGIN",
                        "block_id": match.group(2),
                        "start_index": elem.get("startIndex", 0),
                        "end_index": elem.get("endIndex", 0),
                    }
                )
    return markers


def _find_issues(markers, registry_blocks=None):
    """Analyse markers and return the issues dict.

    registry_blocks: list of block dicts from registry JSON, or None to skip
    cross-check.
    """
    issues = {
        "unregistered_markers": [],
        "registry_without_marker": [],
        "duplicate_ids": [],
        "unbalanced_markers": [],
        "nested_markers": [],
    }

    begin_ids = [m["block_id"] for m in markers if m["kind"] == "BEGIN"]
    end_ids = [m["block_id"] for m in markers if m["kind"] == "END"]

    # Duplicate BEGIN ids
    seen: set = set()
    duplicates: set = set()
    for bid in begin_ids:
        if bid in seen:
            duplicates.add(bid)
        seen.add(bid)
    issues["duplicate_ids"] = sorted(duplicates)

    # Unbalanced
    begin_set = set(begin_ids)
    end_set = set(end_ids)
    for bid in sorted(begin_set - end_set):
        issues["unbalanced_markers"].append({"block_id": bid, "reason": "BEGIN without END"})
    for bid in sorted(end_set - begin_set):
        issues["unbalanced_markers"].append({"block_id": bid, "reason": "END without BEGIN"})

    # Nested: scan markers in order, maintain open stack
    open_stack: list = []
    reported_nested: set = set()
    for m in markers:
        if m["kind"] == "BEGIN":
            if open_stack:
                pair = (open_stack[-1], m["block_id"])
                if pair not in reported_nested:
                    reported_nested.add(pair)
                    issues["nested_markers"].append(
                        {
                            "outer_block_id": open_stack[-1],
                            "inner_block_id": m["block_id"],
                        }
                    )
            open_stack.append(m["block_id"])
        elif m["kind"] == "END":
            if open_stack and open_stack[-1] == m["block_id"]:
                open_stack.pop()

    # Registry cross-check (only when registry supplied)
    if registry_blocks is not None:
        doc_ids = set(begin_ids)
        reg_ids = {b["block_id"] for b in registry_blocks}
        issues["unregistered_markers"] = sorted(doc_ids - reg_ids)
        issues["registry_without_marker"] = sorted(reg_ids - doc_ids)

    return issues


def scan(docs_client, file_id, registry_path=None):
    """Scan a Google Doc for marker issues.

    Returns a result dict matching the architecture §4.2 contract.
    Raises exceptions on API or file errors — caller handles them.
    """
    registry_blocks = None
    if registry_path is not None:
        with open(registry_path) as f:
            registry_data = json.load(f)
        registry_blocks = registry_data.get("blocks", [])

    document = docs_client.documents().get(documentId=file_id).execute()
    raw_markers = _extract_markers(document)

    markers_found = [
        {
            "block_id": m["block_id"],
            "start_index": m["start_index"],
            "end_index": m["end_index"],
        }
        for m in raw_markers
        if m["kind"] == "BEGIN"
    ]

    issues = _find_issues(raw_markers, registry_blocks)
    issue_count = sum(len(v) for v in issues.values())

    return {
        "file_id": file_id,
        "markers_found": markers_found,
        "issues": issues,
        "summary": {
            "total_markers": len(markers_found),
            "issue_count": issue_count,
        },
    }


def scan_template(file_id: str, registry: dict, docs_client) -> dict:
    """Public importable API (AD-20, §11.4). No side effects at import time (TL-15).

    Scan *file_id* for block-marker issues using an already-loaded *registry* dict.

    Parameters
    ----------
    file_id:
        Google Drive file ID of the master template document.
    registry:
        Block registry dict (matches registry.schema.json). Pass ``{"blocks": []}``
        to skip the registry cross-check.
    docs_client:
        An authenticated Docs v1 resource injected by the caller (never built
        inside this function — dependency injection per architecture §9).

    Returns
    -------
    dict
        Scan result matching the §4.2 contract, always containing key ``summary``.
    """
    registry_blocks: list | None = registry.get("blocks") if registry else None

    document = docs_client.documents().get(documentId=file_id).execute()
    raw_markers = _extract_markers(document)

    markers_found = [
        {
            "block_id": m["block_id"],
            "start_index": m["start_index"],
            "end_index": m["end_index"],
        }
        for m in raw_markers
        if m["kind"] == "BEGIN"
    ]

    issues = _find_issues(raw_markers, registry_blocks)
    issue_count = sum(len(v) for v in issues.values())

    return {
        "file_id": file_id,
        "markers_found": markers_found,
        "issues": issues,
        "summary": {
            "total_markers": len(markers_found),
            "issue_count": issue_count,
        },
    }


def main(argv=None, docs_client=None):
    parser = _Parser(description="Scan master template for marker issues")
    parser.add_argument("--file-id", required=True, help="Google Doc file ID to scan")
    parser.add_argument(
        "--registry",
        default=None,
        help="Path to block registry JSON (optional)",
    )
    args = parser.parse_args(argv)

    # Build real Docs client only when not injected (live path — skipped in unit tests)
    if docs_client is None:  # pragma: no cover
        try:
            import google.auth
            from googleapiclient.discovery import build as _build

            creds, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/documents.readonly"]
            )
            docs_client = _build("docs", "v1", credentials=creds)
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "error": {
                            "code": "api_error",
                            "message": f"Failed to build Docs client: {exc}",
                            "retryable": False,
                        }
                    }
                )
            )
            sys.exit(3)

    try:
        result = scan(docs_client, args.file_id, registry_path=args.registry)
    except FileNotFoundError as exc:
        print(
            json.dumps(
                {"error": {"code": "file_not_found", "message": str(exc), "retryable": False}}
            )
        )
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {"error": {"code": "invalid_json", "message": str(exc), "retryable": False}}
            )
        )
        sys.exit(1)
    except Exception as exc:
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status == 403:
            print(
                json.dumps(
                    {"error": {"code": "api_error", "message": str(exc), "retryable": False}}
                )
            )
            sys.exit(3)
        else:
            print(
                json.dumps(
                    {"error": {"code": "api_error", "message": str(exc), "retryable": True}}
                )
            )
            sys.exit(2)

    print(json.dumps(result))
    sys.exit(0 if result["summary"]["issue_count"] == 0 else 1)


if __name__ == "__main__":
    main()
