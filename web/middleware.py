"""
web/middleware.py — Role enforcement and CSRF protection middleware.

Architecture refs: AD-22 (role middleware), SB-02 (no credential logging),
SB-06 (no PII in logs), NF-14 (structured JSON logs to stderr).

Roles enforced:
  R-05  Sales rep  — cannot access review routes
  R-06  Reviewer   — full access including review routes
  R-08  Read-only  — cannot POST

Members list is loaded once at startup from config/workspace.yaml key `members`.
Each entry: {principal: "email@example.com", roles: ["R-05"]}
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import sys
from typing import Optional

import yaml
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SESSION_SECRET_KEY_ENV = "SESSION_SECRET_KEY"

# Public routes — bypass all checks (no cookie required).
_PUBLIC_PREFIXES = ("/static/",)
_PUBLIC_EXACT = frozenset(["/login", "/auth/google", "/auth/callback", "/logout", "/health"])

# ---------------------------------------------------------------------------
# Members loading
# ---------------------------------------------------------------------------

def _load_members() -> list[dict]:
    """Load members list from config/workspace.yaml once at startup.

    Returns a list of dicts: [{principal: str, roles: [str]}].
    Returns empty list if key is absent or file is unreadable.
    """
    config_path = pathlib.Path(__file__).parent.parent / "config" / "workspace.yaml"
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data.get("members") or []
    except Exception:
        return []


# Loaded once at module import (startup).
_MEMBERS: list[dict] = _load_members()


def _lookup_roles(email: str) -> Optional[list[str]]:
    """Return list of role codes for email, or None if not found."""
    for entry in _MEMBERS:
        if entry.get("principal", "").lower() == email.lower():
            return entry.get("roles", [])
    return None


# ---------------------------------------------------------------------------
# Route classification helpers
# ---------------------------------------------------------------------------

def _is_public(path: str) -> bool:
    if path in _PUBLIC_EXACT:
        return True
    for prefix in _PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _is_review_route(path: str) -> bool:
    """True if path matches /jobs/<id>/review pattern."""
    parts = path.strip("/").split("/")
    # e.g. ["jobs", "<id>", "review"]
    return (
        len(parts) == 3
        and parts[0] == "jobs"
        and parts[2] == "review"
    )


# ---------------------------------------------------------------------------
# CSRF helpers
# ---------------------------------------------------------------------------

def _expected_csrf_token(raw_cookie: str) -> str:
    """Derive the expected CSRF token from the raw session cookie value."""
    secret_key = os.environ.get(_SESSION_SECRET_KEY_ENV, "")
    key = ("csrf:" + secret_key).encode()
    return hmac.new(key, raw_cookie.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------

def _log(role: Optional[str], status: int) -> None:
    """Write structured JSON log to stderr. Never logs email or tokens (SB-06)."""
    record = {"role": role, "http_status": status}
    print(json.dumps(record), file=sys.stderr)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

def _redirect_to_login() -> Response:
    return Response(status_code=302, headers={"Location": "/login"})


def _forbidden(role: Optional[str] = None) -> Response:
    _log(role, 403)
    return Response(status_code=403, content="Forbidden")


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RoleEnforcementMiddleware(BaseHTTPMiddleware):
    """Starlette middleware enforcing authentication and role-based access.

    Enforcement order per request:
      1. Public routes pass through immediately.
      2. Session cookie presence and validity — missing/invalid → 302 /login.
      3. Principal must be in members list — unknown → 403.
      4. Role-specific restrictions (R-05 on review; R-08 on POST).
      5. CSRF validation for all non-public POSTs.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method.upper()

        # ------------------------------------------------------------------
        # 1. Public routes bypass all checks
        # ------------------------------------------------------------------
        if _is_public(path):
            return await call_next(request)

        # ------------------------------------------------------------------
        # 2. Session cookie — missing or invalid → 302 /login
        # ------------------------------------------------------------------
        from web.auth import SESSION_COOKIE, decode_session_token  # local import — no side effect

        raw_cookie = request.cookies.get(SESSION_COOKIE)
        if not raw_cookie:
            return _redirect_to_login()

        payload = decode_session_token(raw_cookie)
        if payload is None:
            return _redirect_to_login()

        email: str = payload.get("email", "")

        # ------------------------------------------------------------------
        # 3. Principal must be in members list
        #    When members list is empty, operate in permissive mode (pilot
        #    single-user setup) — consistent with how `reviewers: []` works.
        # ------------------------------------------------------------------
        if _MEMBERS:
            # Enforce membership — unknown principal → 403.
            roles = _lookup_roles(email)
            if roles is None:
                return _forbidden()
        else:
            # Permissive mode: no member list configured; allow all authenticated users.
            roles = []

        # Determine a single "primary" role for logging (first in list, or None).
        primary_role: Optional[str] = roles[0] if roles else None

        # ------------------------------------------------------------------
        # 4. Role-specific restrictions
        # ------------------------------------------------------------------
        is_review = _is_review_route(path)

        # R-05 cannot access review routes
        if "R-05" in roles and is_review:
            return _forbidden("R-05")

        # R-08 cannot POST
        if "R-08" in roles and method == "POST":
            return _forbidden("R-08")

        # ------------------------------------------------------------------
        # 5. CSRF validation for all non-public POSTs
        # ------------------------------------------------------------------
        if method == "POST":
            # Read form data — we must await body consumption
            try:
                form = await request.form()
                submitted_csrf = form.get("_csrf", "")
            except Exception:
                submitted_csrf = ""

            expected = _expected_csrf_token(raw_cookie)
            if not submitted_csrf or not hmac.compare_digest(submitted_csrf, expected):
                return _forbidden(primary_role)

        # ------------------------------------------------------------------
        # 6. Pass through to next handler
        # ------------------------------------------------------------------
        return await call_next(request)
