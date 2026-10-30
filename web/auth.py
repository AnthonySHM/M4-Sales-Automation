"""
web/auth.py — Google OAuth 2.0 login, signed-cookie sessions, auth dependency.

Architecture refs: AD-16 (OAuth), SB-11 (session cookie), SB-13 (minimal scope),
NF-13 (8-hour expiry), TL-15 (no import side effects).
"""
from __future__ import annotations

import os
import secrets as _secrets
import time
from typing import Optional

from fastapi import Cookie, HTTPException, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCOPES = ["openid", "email"]          # SB-13: minimal scope only
SESSION_COOKIE = "session"
STATE_COOKIE = "_oauth_state"
SESSION_MAX_AGE = 8 * 3600             # 8 hours in seconds (NF-13)


# ---------------------------------------------------------------------------
# Secret key
# ---------------------------------------------------------------------------

def _get_secret_key() -> str:
    """Read SESSION_SECRET_KEY from env. Raises RuntimeError if missing."""
    key = os.environ.get("SESSION_SECRET_KEY", "")
    if not key:
        raise RuntimeError(
            "SESSION_SECRET_KEY environment variable is not set. "
            "Set it to a long random string before starting the server. (SB-02)"
        )
    return key


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_get_secret_key(), salt="session")


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def create_session_token(email: str) -> str:
    """Create a signed session token storing email and created_at."""
    payload = {"email": email, "created_at": time.time()}
    return _serializer().dumps(payload)


def decode_session_token(token: str) -> Optional[dict]:
    """Decode and verify token. Returns payload dict or None if invalid/expired."""
    try:
        return _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except (SignatureExpired, BadSignature):
        return None


def set_session_cookie(response, token: str) -> None:
    """Attach signed session cookie to response (HttpOnly, Secure, SameSite=Lax)."""
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )


def clear_session_cookie(response) -> None:
    """Remove session cookie."""
    response.delete_cookie(key=SESSION_COOKIE, httponly=True, secure=True, samesite="lax")


# ---------------------------------------------------------------------------
# FastAPI dependency — require_auth
# ---------------------------------------------------------------------------

async def require_auth(request: Request) -> str:
    """FastAPI dependency. Returns authenticated user email or redirects to /login.

    Exported for use by Issue #37 (role enforcement) and Issue #39+ (routes).
    """
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    payload = decode_session_token(token)
    if payload is None:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return payload["email"]


# ---------------------------------------------------------------------------
# OAuth flow helpers
# ---------------------------------------------------------------------------

def build_oauth_flow(redirect_uri: str):
    """Build a google_auth_oauthlib Flow from env vars."""
    from google_auth_oauthlib.flow import Flow  # local import — no side effect at module level

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError(
            "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set. (SB-02)"
        )

    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )


def generate_state() -> str:
    return _secrets.token_urlsafe(32)
