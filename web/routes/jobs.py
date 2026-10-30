"""
web/routes/jobs.py — Job submission form and assemble pipeline integration.

Routes:
  GET  /jobs/new        — render the submission form
  POST /jobs            — validate + assemble, redirect to /jobs/<id>
  GET  /jobs/{job_id}   — job detail page

Architecture refs: AD-15 (FastAPI), AD-19 (Jinja2), AD-20 (importable assemble),
AD-22 (CSRF via middleware), G-04 (job runner), NF-06 (130 s timeout), SB-02.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import pathlib
import sys
import uuid

import yaml
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from web.auth import SESSION_COOKIE, require_auth

# ---------------------------------------------------------------------------
# Scripts import — leading dot in directory name requires sys.path insertion
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "../../.claude/skills/document-assembly/scripts",
    )
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from assemble import assemble  # noqa: E402
from validate_request import validate_request  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent  # web/routes/ → repo root

# ---------------------------------------------------------------------------
# Config caching
# ---------------------------------------------------------------------------

_workspace_cfg: dict | None = None
_recipe_cfg: dict | None = None


def _get_workspace() -> dict:
    global _workspace_cfg
    if _workspace_cfg is None:
        with open(_REPO_ROOT / "config" / "workspace.yaml") as f:
            _workspace_cfg = yaml.safe_load(f)
    return _workspace_cfg


def _get_recipe(workspace_cfg: dict) -> dict:
    global _recipe_cfg
    if _recipe_cfg is None:
        key = workspace_cfg["pilot_family"]["key"]
        version = workspace_cfg["pilot_family"]["active_recipe_version"]
        path = _REPO_ROOT / "config" / "recipes" / f"{key}_v{version}.json"
        with open(path) as f:
            _recipe_cfg = json.load(f)
    return _recipe_cfg


# ---------------------------------------------------------------------------
# In-memory job store (MVP cache for detail page)
# ---------------------------------------------------------------------------

_JOB_STORE: dict = {}

# ---------------------------------------------------------------------------
# CSRF helpers
# ---------------------------------------------------------------------------


def _compute_csrf(request: Request) -> str:
    """Derive CSRF token from the raw session cookie using HMAC-SHA256."""
    raw_cookie = request.cookies.get(SESSION_COOKIE, "")
    secret_key = os.environ.get("SESSION_SECRET_KEY", "")
    key = ("csrf:" + secret_key).encode()
    return hmac.new(key, raw_cookie.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Google clients builder
# ---------------------------------------------------------------------------


def _build_clients(workspace_cfg: dict):
    """Build real Google API clients from GOOGLE_APPLICATION_CREDENTIALS.

    Returns (drive_client, docs_client, ledger) or (None, None, None) if the
    env var is not set or credential loading fails.
    """
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        return None, None, None
    try:
        with open(creds_path) as f:
            creds_data = json.load(f)

        if creds_data.get("type") == "authorized_user":
            from google.oauth2.credentials import Credentials

            creds = Credentials(
                token=creds_data.get("token"),
                refresh_token=creds_data.get("refresh_token"),
                token_uri=creds_data.get("token_uri"),
                client_id=creds_data.get("client_id"),
                client_secret=creds_data.get("client_secret"),
            )
        else:
            from google.oauth2.service_account import Credentials

            creds = Credentials.from_service_account_file(
                creds_path,
                scopes=[
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/documents",
                ],
            )

        from googleapiclient.discovery import build

        drive_client = build("drive", "v3", credentials=creds)
        docs_client = build("docs", "v1", credentials=creds)
        sheets_client = build("sheets", "v4", credentials=creds)

        from ledger import SheetsLedgerAdapter  # noqa: E402 (scripts on sys.path)

        ledger = SheetsLedgerAdapter(
            service=sheets_client,
            spreadsheet_id=workspace_cfg["ledger"]["spreadsheet_id"],
            jobs_tab=workspace_cfg["ledger"]["jobs_tab"],
            events_tab=workspace_cfg["ledger"]["events_tab"],
        )
        return drive_client, docs_client, ledger
    except Exception:
        return None, None, None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()


@router.get("/jobs/new")
async def get_jobs_new(request: Request, email: str = Depends(require_auth)):
    """Render the job submission form."""
    templates = request.app.state.templates
    workspace_cfg = _get_workspace()
    recipe = _get_recipe(workspace_cfg)

    option_keys = [o["option_key"] for o in recipe["options"]]
    placeholder_keys = list(recipe["placeholder_map"].keys())
    csrf_token = _compute_csrf(request)

    return templates.TemplateResponse(
        request,
        "submit.html",
        {
            "options": recipe["options"],
            "placeholder_keys": placeholder_keys,
            "errors": [],
            "csrf_token": csrf_token,
            "form_values": {},
        },
    )


@router.post("/jobs")
async def post_jobs(request: Request, email: str = Depends(require_auth)):
    """Validate form data, run assembly pipeline, redirect to job detail."""
    templates = request.app.state.templates
    form = await request.form()

    workspace_cfg = _get_workspace()
    recipe = _get_recipe(workspace_cfg)

    option_keys = [o["option_key"] for o in recipe["options"]]
    placeholder_keys = list(recipe["placeholder_map"].keys())

    options = {k: form.get(k, "") for k in option_keys}
    placeholder_values = {k.lower(): form.get(k.lower(), "") for k in placeholder_keys}

    request_dict = {
        "family_key": workspace_cfg["pilot_family"]["key"],
        "workspace_id": workspace_cfg["workspace_id"],
        "options": options,
        "placeholder_values": placeholder_values,
    }

    # Validate
    validation = validate_request(request_dict, recipe)
    if not validation["valid"]:
        csrf_token = _compute_csrf(request)
        return templates.TemplateResponse(
            request,
            "submit.html",
            {
                "options": recipe["options"],
                "placeholder_keys": placeholder_keys,
                "errors": validation["errors"],
                "csrf_token": csrf_token,
                "form_values": dict(form),
            },
            status_code=422,
        )

    # Assemble with timeout
    job_id = uuid.uuid4().hex
    drive_client, docs_client, ledger = _build_clients(workspace_cfg)

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                assemble,
                request_dict,
                workspace_cfg,
                drive_client=drive_client,
                docs_client=docs_client,
                ledger=ledger,
                job_id=job_id,
            ),
            timeout=130.0,
        )
    except asyncio.TimeoutError:
        if ledger:
            try:
                ledger.update_job(job_id, {"status": "failed"})
            except Exception:
                pass
        result = {
            "job_id": job_id,
            "status": "failed",
            "error": {
                "code": "timeout",
                "message": "Assembly exceeded 130 s time limit.",
                "retryable": True,
            },
        }

    # Cache result for detail page
    job_id_final = result.get("job_id", job_id)
    _JOB_STORE[job_id_final] = result

    if result.get("status") == "failed":
        drive_link = (
            f"https://drive.google.com/drive/folders/"
            f"{workspace_cfg['folders']['review']}"
        )
        return templates.TemplateResponse(
            request,
            "job_detail.html",
            {
                "job_id": job_id_final,
                "status": "failed",
                "drive_link": drive_link,
                "error": result.get("error"),
            },
            status_code=500,
        )

    return RedirectResponse(url=f"/jobs/{job_id_final}", status_code=303)


@router.get("/jobs/{job_id}")
async def get_job_detail(
    job_id: str, request: Request, email: str = Depends(require_auth)
):
    """Render job detail page from in-memory store."""
    templates = request.app.state.templates
    result = _JOB_STORE.get(job_id)

    workspace_cfg = _get_workspace()

    if result is None:
        # Job not in store (e.g. after restart); show minimal page
        drive_link = (
            f"https://drive.google.com/drive/folders/"
            f"{workspace_cfg['folders']['review']}"
        )
        return templates.TemplateResponse(
            request,
            "job_detail.html",
            {
                "job_id": job_id,
                "status": "unknown",
                "drive_link": drive_link,
                "error": None,
            },
        )

    # Build drive_link from output_document_id if available, else review folder
    output_doc_id = result.get("output_document_id")
    if output_doc_id:
        drive_link = f"https://docs.google.com/document/d/{output_doc_id}/edit"
    else:
        drive_link = (
            f"https://drive.google.com/drive/folders/"
            f"{workspace_cfg['folders']['review']}"
        )

    return templates.TemplateResponse(
        request,
        "job_detail.html",
        {
            "job_id": job_id,
            "status": result.get("status", "unknown"),
            "drive_link": drive_link,
            "error": result.get("error"),
        },
    )
