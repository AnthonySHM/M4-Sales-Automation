"""
web/routes/auth.py — OAuth login, callback, and logout routes.

Architecture refs: AD-16, SB-11, SB-13, NF-13.
"""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from web.auth import (
    STATE_COOKIE,
    SESSION_COOKIE,
    build_oauth_flow,
    clear_session_cookie,
    create_session_token,
    generate_state,
    set_session_cookie,
)

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    """Render the login page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "login.html")


@router.get("/auth/google")
async def auth_google(request: Request):
    """Start the Google OAuth flow — redirect to Google's auth endpoint."""
    redirect_uri = str(request.url_for("auth_callback"))
    flow = build_oauth_flow(redirect_uri)

    state = generate_state()
    auth_url, _ = flow.authorization_url(
        access_type="online",
        state=state,
        include_granted_scopes="false",
        prompt="select_account",
    )

    response = RedirectResponse(url=auth_url, status_code=302)
    # Store state in a short-lived cookie to verify on callback (SB-11)
    response.set_cookie(
        key=STATE_COOKIE,
        value=state,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=600,  # 10 minutes to complete the flow
    )
    return response


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    _state_cookie: str = Cookie(default="", alias=STATE_COOKIE),
):
    """Handle Google OAuth callback — exchange code for token, create session."""
    # Error from Google (e.g. user denied)
    if error:
        return RedirectResponse(url="/login?error=access_denied", status_code=302)

    # Validate state to prevent CSRF (SB-11)
    if not state or state != _state_cookie:
        return JSONResponse(
            status_code=400,
            content={
                "error": "state_mismatch",
                "message": "OAuth state mismatch — possible CSRF attempt.",
            },
        )

    # Exchange authorisation code for tokens
    redirect_uri = str(request.url_for("auth_callback"))
    try:
        flow = build_oauth_flow(redirect_uri)
        flow.fetch_token(code=code)
        id_info = flow.credentials.id_token  # dict decoded by google-auth
        if isinstance(id_info, dict):
            email = id_info.get("email", "")
        else:
            # id_token may be a raw JWT string — decode it
            import base64 as _b64
            import json as _json

            parts = str(id_info).split(".")
            payload_b64 = parts[1] + "==" * (4 - len(parts[1]) % 4)
            email = _json.loads(_b64.urlsafe_b64decode(payload_b64)).get("email", "")
    except Exception:
        return RedirectResponse(url="/login?error=token_exchange_failed", status_code=302)

    if not email:
        return RedirectResponse(url="/login?error=no_email", status_code=302)

    token = create_session_token(email)

    # Redirect to originally requested URL or default to /jobs
    next_url = request.query_params.get("next", "/jobs")
    response = RedirectResponse(url=next_url, status_code=302)
    set_session_cookie(response, token)
    # Clear the temporary state cookie
    response.delete_cookie(key=STATE_COOKIE)
    return response


@router.get("/logout")
async def logout():
    """Destroy session and redirect to /login."""
    response = RedirectResponse(url="/login", status_code=302)
    clear_session_cookie(response)
    return response
