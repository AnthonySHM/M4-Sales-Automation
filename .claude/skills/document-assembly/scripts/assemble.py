"""
assemble.py — Core job runner for document assembly.

Steps: validate_request → resolve_blocks → copy_master → prune_blocks
       → fill_placeholders → strip_markers → verify_output → submit_for_review

Exit codes:
  0 — job completed successfully
  1 — validation / logic error (non-retryable)
  2 — external / transient error (retryable)
  3 — credential / permission error
"""

import argparse
import json
import sys

# Full implementation across Issues #13, #14, #15. Stub validates CLI contract.


def main(argv=None):
    parser = argparse.ArgumentParser(description="Assemble a document from a request")
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

    # Validate request file exists
    try:
        with open(args.request) as f:
            request_data = json.load(f)
    except FileNotFoundError:
        error_out = {
            "event": "job_failed",
            "error": {
                "code": "file_not_found",
                "step": "validate_request",
                "message": f"Request file not found: {args.request}",
                "retryable": False,
            },
        }
        print(json.dumps(error_out))
        sys.exit(1)
    except json.JSONDecodeError as exc:
        error_out = {
            "event": "job_failed",
            "error": {
                "code": "invalid_json",
                "step": "validate_request",
                "message": f"Request is not valid JSON: {exc}",
                "retryable": False,
            },
        }
        print(json.dumps(error_out))
        sys.exit(1)

    # Stub: emit a dry-run or pending event and exit cleanly.
    if args.dry_run:
        event = {
            "event": "dry_run_complete",
            "step": "resolve_blocks",
            "job_id": None,
            "detail": {
                "request_id": request_data.get("request_id"),
                "family_key": request_data.get("family_key"),
                "resolved_blocks": [],
                "note": "Stub — full dry-run logic in Issue #13",
            },
        }
    else:
        event = {
            "event": "job_started",
            "step": "validate_request",
            "job_id": None,
            "detail": {
                "request_id": request_data.get("request_id"),
                "note": "Stub — full assembly logic across Issues #13-15",
            },
        }

    print(json.dumps(event))
    sys.exit(0)


if __name__ == "__main__":
    main()
