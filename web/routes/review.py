"""
web/routes/review.py — Browser-based review UI (approve / reject).

Routes:
  GET  /jobs/{job_id}/review  — render approve/reject form (awaiting_review only)
  POST /jobs/{job_id}/review  — submit decision

Architecture refs: G-16, G-07, AD-22, SB-16.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, HTMLResponse

from web.auth import require_auth

# ---------------------------------------------------------------------------
# Import the review script without name collision.
# web/routes/review.py is itself named "review", so we alias the import.
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../../.claude/skills/document-assembly/scripts")
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from review import _review_public_api as _script_review  # noqa: E402

# Re-use helpers and shared state from the jobs module
from web.routes.jobs import _JOB_STORE, _build_clients, _get_workspace, _compute_csrf

router = APIRouter()


@router.get("/jobs/{job_id}/review")
async def get_review(
    job_id: str,
    request: Request,
    email: str = Depends(require_auth),
):
    if job_id not in _JOB_STORE:
        return HTMLResponse("Job not found", status_code=404)

    job = _JOB_STORE[job_id]
    if job.get("status") != "awaiting_review":
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "job_id": job_id,
            "status": job.get("status"),
            "csrf_token": _compute_csrf(request),
            "error": None,
        },
    )


@router.post("/jobs/{job_id}/review")
async def post_review(
    job_id: str,
    request: Request,
    email: str = Depends(require_auth),
):
    if job_id not in _JOB_STORE:
        return HTMLResponse("Job not found", status_code=404)

    form = await request.form()
    decision = form.get("decision", "").strip()
    reason = form.get("reason", "").strip() or None

    # Validate: decision must be one of the accepted values, and reject requires reason
    _valid_decisions = {"approved", "rejected"}
    _error: str | None = None
    if decision not in _valid_decisions:
        _error = "Invalid or missing decision. Please click Approve or Reject."
    elif decision == "rejected" and not reason:
        _error = "Rejection reason is required."

    if _error is not None:
        templates = request.app.state.templates
        return templates.TemplateResponse(
            "review.html",
            {
                "request": request,
                "job_id": job_id,
                "status": _JOB_STORE[job_id].get("status"),
                "csrf_token": _compute_csrf(request),
                "error": _error,
            },
            status_code=422,
        )

    workspace_cfg = _get_workspace()
    drive_client, _, ledger = _build_clients(workspace_cfg)

    result = _script_review(
        job_id,
        decision,
        reason,
        workspace_cfg,
        drive_client=drive_client,
        ledger=ledger,
    )

    if result.get("exit_code") == 0:
        _JOB_STORE[job_id]["status"] = result.get("status", decision)
        # Audit log (SB-16) — no reason, no email, no document content
        print(
            json.dumps({
                "event": "review_decision",
                "job_id": job_id,
                "decision": decision,
                "reviewer_ip": request.client.host if request.client else None,
                "decided_at": datetime.now(timezone.utc).isoformat(),
            }),
            file=sys.stderr,
        )

    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)
