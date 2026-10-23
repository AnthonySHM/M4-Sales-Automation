"""
review.py -- Approve or reject an assembled document (G-07, AD-10).

CLI:
  python review.py --job-id <job_id> --decision approved|rejected
                   --reviewer <email> [--reason <text>]
                   [--workspace config/workspace.yaml]

Exit codes:
  0 -- decision recorded (approved or rejected)
  1 -- validation / logic error (non-retryable)
  2 -- external / transient error (retryable)
  3 -- credential / permission error

Advances G-07, AD-10, Issue #20.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class UnauthorizedReviewerError(Exception):
    """Caller is not in the workspace reviewers list."""


class InvalidJobStateError(Exception):
    """Job is not in awaiting_review state."""


class MissingReasonError(Exception):
    """Rejection requires a reason."""


class JobNotFoundError(Exception):
    """No job with the given job_id exists."""


class GoogleApiError(Exception):
    """Transient or permanent Google API failure."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        self.retryable = retryable
        super().__init__(message)


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


def _emit(event: dict) -> None:
    """Write one newline-delimited JSON event to stdout."""
    print(json.dumps(event), flush=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Identity check
# ---------------------------------------------------------------------------


def _check_reviewer(reviewer: str, workspace: dict) -> None:
    """Raise UnauthorizedReviewerError if reviewer is not authorised.

    When workspace.reviewers is empty or absent, the check is skipped
    (permissive mode for single-user pilot setups).
    """
    reviewers = workspace.get("reviewers", [])
    if reviewers and reviewer not in reviewers:
        raise UnauthorizedReviewerError(
            f"Reviewer {reviewer!r} is not in the authorised reviewers list."
        )


# ---------------------------------------------------------------------------
# Drive move helper
# ---------------------------------------------------------------------------


def _move_to_approved(drive_client, output_doc_id: str, workspace: dict) -> None:
    """Move output document from review/ to approved/ folder."""
    approved_folder: str = workspace["folders"]["approved"]
    review_folder: str = workspace["folders"]["review"]
    drive_client.files().update(
        fileId=output_doc_id,
        addParents=approved_folder,
        removeParents=review_folder,
        supportsAllDrives=True,
        fields="id,parents",
    ).execute()


# ---------------------------------------------------------------------------
# Review orchestration
# ---------------------------------------------------------------------------


def review(
    job_id: str,
    decision: str,
    reviewer: str,
    workspace: dict,
    *,
    reason: str = "",
    drive_client=None,
    ledger=None,
) -> int:
    """Record a review decision. Emits streaming events to stdout. Returns exit code.

    Parameters
    ----------
    job_id:
        ID of the job to review.
    decision:
        "approved" or "rejected".
    reviewer:
        Email / identity of the reviewer (validated against workspace.reviewers).
    workspace:
        Loaded workspace.yaml dict.
    reason:
        Human-readable reason (required on rejection).
    drive_client:
        Injected Drive v3 resource.
    ledger:
        Injected LedgerAdapter.
    """
    # ------------------------------------------------------------------
    # Step: validate_reviewer
    # ------------------------------------------------------------------
    _emit({"event": "step_started", "step": "validate_reviewer", "job_id": job_id, "detail": {}})

    try:
        _check_reviewer(reviewer, workspace)
    except UnauthorizedReviewerError as exc:
        _emit({
            "event": "job_failed",
            "step": "validate_reviewer",
            "job_id": job_id,
            "detail": {
                "error": {
                    "code": "unauthorized_reviewer",
                    "message": str(exc),
                    "retryable": False,
                }
            },
        })
        return 1

    _emit({"event": "step_succeeded", "step": "validate_reviewer", "job_id": job_id, "detail": {}})

    # ------------------------------------------------------------------
    # Step: validate_decision
    # ------------------------------------------------------------------
    _emit({"event": "step_started", "step": "validate_decision", "job_id": job_id, "detail": {}})

    if decision == "rejected" and not reason:
        _emit({
            "event": "job_failed",
            "step": "validate_decision",
            "job_id": job_id,
            "detail": {
                "error": {
                    "code": "missing_reason",
                    "message": "A reason is required when rejecting a job.",
                    "retryable": False,
                }
            },
        })
        return 1

    _emit({
        "event": "step_succeeded",
        "step": "validate_decision",
        "job_id": job_id,
        "detail": {"decision": decision},
    })

    # ------------------------------------------------------------------
    # Step: load_job
    # ------------------------------------------------------------------
    _emit({"event": "step_started", "step": "load_job", "job_id": job_id, "detail": {}})

    output_doc_id: str | None = None
    if ledger is not None:
        try:
            job = ledger.get_job(job_id)
        except Exception as exc:  # noqa: BLE001
            _emit({
                "event": "job_failed",
                "step": "load_job",
                "job_id": job_id,
                "detail": {
                    "error": {
                        "code": "job_not_found",
                        "message": str(exc),
                        "retryable": False,
                    }
                },
            })
            return 1

        current_status = job.get("status", "")
        if current_status != "awaiting_review":
            _emit({
                "event": "job_failed",
                "step": "load_job",
                "job_id": job_id,
                "detail": {
                    "error": {
                        "code": "invalid_job_state",
                        "message": (
                            f"Job {job_id!r} is in state {current_status!r}, "
                            f"expected 'awaiting_review'."
                        ),
                        "retryable": False,
                        "current_status": current_status,
                    }
                },
            })
            return 1

        output_doc_id = job.get("output_document_id")

    _emit({
        "event": "step_succeeded",
        "step": "load_job",
        "job_id": job_id,
        "detail": {"output_document_id": output_doc_id},
    })

    # ------------------------------------------------------------------
    # Step: move_document (approved only)
    # ------------------------------------------------------------------
    if decision == "approved" and output_doc_id and drive_client is not None:
        _emit({"event": "step_started", "step": "move_document", "job_id": job_id, "detail": {}})
        try:
            _move_to_approved(drive_client, output_doc_id, workspace)
        except Exception as exc:  # noqa: BLE001
            _emit({
                "event": "job_failed",
                "step": "move_document",
                "job_id": job_id,
                "detail": {
                    "error": {
                        "code": "api_error",
                        "message": str(exc),
                        "retryable": True,
                    }
                },
            })
            return 2
        _emit({
            "event": "step_succeeded",
            "step": "move_document",
            "job_id": job_id,
            "detail": {
                "output_document_id": output_doc_id,
                "moved_to": workspace["folders"]["approved"],
            },
        })

    # ------------------------------------------------------------------
    # Step: record_decision
    # ------------------------------------------------------------------
    _emit({"event": "step_started", "step": "record_decision", "job_id": job_id, "detail": {}})

    decided_at = _now_iso()
    workspace_id = workspace.get("workspace_id", "")

    review_decision = {
        "event_id": uuid.uuid4().hex,
        "job_id": job_id,
        "workspace_id": workspace_id,
        "event_type": "review_decision",
        "occurred_at": decided_at,
        "actor": reviewer,
        "detail": {
            "decision": decision,
            "reason": reason,
        },
    }

    if ledger is not None:
        try:
            ledger.append_event(review_decision)
            ledger.update_job(job_id, {"status": decision, "finished_at": decided_at})
        except Exception as exc:  # noqa: BLE001
            _emit({
                "event": "job_failed",
                "step": "record_decision",
                "job_id": job_id,
                "detail": {
                    "error": {
                        "code": "api_error",
                        "message": str(exc),
                        "retryable": True,
                    }
                },
            })
            return 2

    _emit({
        "event": "step_succeeded",
        "step": "record_decision",
        "job_id": job_id,
        "detail": {
            "decision": decision,
            "decided_at": decided_at,
        },
    })

    _emit({
        "event": "job_completed",
        "step": "record_decision",
        "job_id": job_id,
        "detail": {
            "job_id": job_id,
            "decision": decision,
            "reviewer": reviewer,
            "decided_at": decided_at,
            "output_document_id": output_doc_id,
        },
    })

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(json.dumps({"error": {"code": "missing_argument", "message": message}}))
        sys.exit(1)


def main(argv=None, drive_client=None, ledger=None) -> None:
    parser = _Parser(description="Approve or reject an assembled document")
    parser.add_argument("--job-id", required=True, help="Job ID to review")
    parser.add_argument(
        "--decision",
        required=True,
        choices=["approved", "rejected"],
        help="Review decision",
    )
    parser.add_argument("--reviewer", required=True, help="Reviewer email / identity")
    parser.add_argument("--reason", default="", help="Required when decision=rejected")
    parser.add_argument(
        "--workspace",
        default="config/workspace.yaml",
        help="Path to workspace.yaml",
    )
    args = parser.parse_args(argv)

    # Load workspace
    try:
        import yaml  # PyYAML

        with open(args.workspace) as f:
            workspace = yaml.safe_load(f)
    except FileNotFoundError:
        _emit({
            "event": "job_failed",
            "step": "validate_reviewer",
            "job_id": args.job_id,
            "detail": {
                "error": {
                    "code": "file_not_found",
                    "message": f"Workspace file not found: {args.workspace}",
                    "retryable": False,
                }
            },
        })
        sys.exit(1)

    # Build real Drive client only when not injected (skipped in unit tests)
    if drive_client is None:  # pragma: no cover
        try:
            import google.auth
            from googleapiclient.discovery import build as _build

            creds, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/drive.file"]
            )
            drive_client = _build("drive", "v3", credentials=creds)
        except Exception as exc:
            _emit({
                "event": "job_failed",
                "step": "validate_reviewer",
                "job_id": args.job_id,
                "detail": {
                    "error": {
                        "code": "api_error",
                        "message": f"Failed to build Drive client: {exc}",
                        "retryable": False,
                    }
                },
            })
            sys.exit(3)

    exit_code = review(
        job_id=args.job_id,
        decision=args.decision,
        reviewer=args.reviewer,
        workspace=workspace,
        reason=args.reason,
        drive_client=drive_client,
        ledger=ledger,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
