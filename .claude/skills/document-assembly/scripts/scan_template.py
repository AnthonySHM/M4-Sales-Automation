"""
scan_template.py — Validate block markers in a master template Google Doc.

Reads the document via the Docs API and reports:
  - unregistered_markers: in doc but not in registry
  - registry_without_marker: in registry but not in doc
  - duplicate_ids: block_id appears more than once
  - unbalanced_markers: BEGIN without END or vice versa
  - nested_markers: a BEGIN appears before the previous END

Exit codes:
  0 — no issues found
  1 — one or more marker issues found
  2 — external / transient error (e.g. API failure)
  3 — credential / permission error
"""

import argparse
import json
import sys

# Full implementation in Issue #8. This stub validates CLI contract only.


class UnimplementedError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({"error": {"code": "missing_argument", "message": message}}))
        sys.exit(1)


def main(argv=None):
    parser = _Parser(description="Scan master template for marker issues")
    parser.add_argument("--file-id", required=True, help="Google Doc file ID to scan")
    parser.add_argument(
        "--registry",
        default=None,
        help="Path to block registry JSON (optional)",
    )
    args = parser.parse_args(argv)

    # Stub: returns a valid empty result until Issue #8 is implemented.
    result = {
        "file_id": args.file_id,
        "markers_found": [],
        "issues": {
            "unregistered_markers": [],
            "registry_without_marker": [],
            "duplicate_ids": [],
            "unbalanced_markers": [],
            "nested_markers": [],
        },
        "summary": {"total_markers": 0, "issue_count": 0},
        "note": "Stub implementation — full logic delivered in Issue #8",
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
