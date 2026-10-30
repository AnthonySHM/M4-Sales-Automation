"""Unit tests for web/middleware.py (Issue #37).

Covers all 13 ACs:
  AC-01  Unauthenticated request → 302 redirect to /login
  AC-02  Valid cookie, email not in members → 403
  AC-03  R-05 session on review route → 403
  AC-04  R-06 session on review route → 200 (passes)
  AC-05  R-08 session on POST → 403
  AC-06  R-08 session on GET → 200 (passes)
  AC-07  R-05 POST without _csrf → 403
  AC-08  R-05 POST with wrong _csrf → 403
  AC-09  R-05 POST with correct _csrf → 200 (passes)
  AC-10  GET /health with no cookie → not 302/403
  AC-11  GET /login with no cookie → not 302/403
  AC-12  GET /auth/google with no cookie → not 302/403
  AC-13  GET /static/foo.js with no cookie → not 302/403

No live API calls — all Google / session helpers are patched.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

_TEST_SECRET = "test-secret-key-for-middleware-tests"
_COOKIE_NAME = "session"  # must match web.auth.SESSION_COOKIE


# ---------------------------------------------------------------------------
# Helpers — session token fabrication
# ---------------------------------------------------------------------------

def _make_token(email: str) -> str:
    """Create a real signed session token using the test secret key."""
    os.environ["SESSION_SECRET_KEY"] = _TEST_SECRET
    from web.auth import create_session_token
    return create_session_token(email)


# ---------------------------------------------------------------------------
# Helpers — CSRF token
# ---------------------------------------------------------------------------

def _make_csrf(raw_cookie: str) -> str:
    """Derive the expected CSRF token the same way the middleware does."""
    key = ("csrf:" + _TEST_SECRET).encode()
    return hmac.new(key, raw_cookie.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Helpers — members list injection
# ---------------------------------------------------------------------------

def _members(entries: list[dict]) -> list[dict]:
    """Return a members list for monkeypatching web.middleware._MEMBERS."""
    return entries


# ---------------------------------------------------------------------------
# App factory for tests
# ---------------------------------------------------------------------------

def _make_app(members: list[dict]) -> FastAPI:
    """Build a minimal FastAPI app with RoleEnforcementMiddleware registered
    and a stub route at every path needed by the tests.

    Members are injected by monkeypatching web.middleware._MEMBERS before
    the TestClient starts.
    """
    # Patch _MEMBERS before importing middleware so the middleware uses our list.
    import web.middleware as mw_mod
    mw_mod._MEMBERS = members

    app = FastAPI()

    # Stub routes used in tests
    @app.get("/jobs")
    async def jobs_list():
        return PlainTextResponse("jobs-list")

    @app.get("/jobs/{job_id}/review")
    async def job_review(job_id: str):
        return PlainTextResponse("review-page")

    @app.post("/jobs")
    async def jobs_post():
        return PlainTextResponse("jobs-post")

    @app.post("/jobs/{job_id}/review")
    async def job_review_post(job_id: str):
        return PlainTextResponse("review-post")

    @app.get("/health")
    async def health():
        return PlainTextResponse("ok")

    @app.get("/login")
    async def login():
        return PlainTextResponse("login-page")

    @app.get("/auth/google")
    async def auth_google():
        return PlainTextResponse("auth-google")

    @app.get("/static/{path:path}")
    async def static_files(path: str):
        return PlainTextResponse("static-file")

    from web.middleware import RoleEnforcementMiddleware
    app.add_middleware(RoleEnforcementMiddleware)

    return app


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Ensure SESSION_SECRET_KEY is set for every test."""
    monkeypatch.setenv("SESSION_SECRET_KEY", _TEST_SECRET)


# ---------------------------------------------------------------------------
# AC-01: Unauthenticated request → 302 to /login
# ---------------------------------------------------------------------------

class TestUnauthenticatedRedirect:
    def test_unauthenticated_redirect(self):
        """No cookie on GET /jobs → 302 to /login (AC-01)."""
        app = _make_app([])
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/jobs", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# AC-02: Valid cookie, email not in members → 403
# ---------------------------------------------------------------------------

class TestUnknownPrincipal:
    def test_unknown_principal_403(self):
        """Valid cookie but email not in members list → 403 (AC-02)."""
        members = [{"principal": "other@example.com", "roles": ["R-05"]}]
        app = _make_app(members)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token("stranger@example.com")
        client.cookies.set(_COOKIE_NAME, token)
        response = client.get("/jobs", follow_redirects=False)
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# AC-03: R-05 session on review route → 403
# ---------------------------------------------------------------------------

class TestR05ReviewForbidden:
    def test_r05_review_forbidden(self):
        """R-05 principal attempting GET /jobs/abc/review → 403 (AC-03)."""
        members = [{"principal": "rep@example.com", "roles": ["R-05"]}]
        app = _make_app(members)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token("rep@example.com")
        client.cookies.set(_COOKIE_NAME, token)
        response = client.get("/jobs/abc/review", follow_redirects=False)
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# AC-04: R-06 session on review route → 200
# ---------------------------------------------------------------------------

class TestR06ReviewAllowed:
    def test_r06_review_allowed(self):
        """R-06 principal on GET /jobs/abc/review → 200 (AC-04)."""
        members = [{"principal": "reviewer@example.com", "roles": ["R-06"]}]
        app = _make_app(members)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token("reviewer@example.com")
        client.cookies.set(_COOKIE_NAME, token)
        response = client.get("/jobs/abc/review", follow_redirects=False)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# AC-05: R-08 session on POST → 403
# ---------------------------------------------------------------------------

class TestR08PostForbidden:
    def test_r08_post_forbidden(self):
        """R-08 principal on POST /jobs → 403 (AC-05)."""
        members = [{"principal": "readonly@example.com", "roles": ["R-08"]}]
        app = _make_app(members)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token("readonly@example.com")
        client.cookies.set(_COOKIE_NAME, token)
        response = client.post("/jobs", data={}, follow_redirects=False)
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# AC-06: R-08 session on GET → passes (200)
# ---------------------------------------------------------------------------

class TestR08GetAllowed:
    def test_r08_get_allowed(self):
        """R-08 principal on GET /jobs → 200 (AC-06)."""
        members = [{"principal": "readonly@example.com", "roles": ["R-08"]}]
        app = _make_app(members)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token("readonly@example.com")
        client.cookies.set(_COOKIE_NAME, token)
        response = client.get("/jobs", follow_redirects=False)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# AC-07: R-05 POST without _csrf → 403
# ---------------------------------------------------------------------------

class TestCsrfMissing:
    def test_csrf_missing_403(self):
        """R-05 POST to /jobs without _csrf field → 403 (AC-07)."""
        members = [{"principal": "rep@example.com", "roles": ["R-05"]}]
        app = _make_app(members)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token("rep@example.com")
        client.cookies.set(_COOKIE_NAME, token)
        # POST with no _csrf key in form data
        response = client.post("/jobs", data={"other": "value"}, follow_redirects=False)
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# AC-08: R-05 POST with wrong _csrf → 403
# ---------------------------------------------------------------------------

class TestCsrfMismatch:
    def test_csrf_mismatch_403(self):
        """R-05 POST to /jobs with wrong _csrf value → 403 (AC-08)."""
        members = [{"principal": "rep@example.com", "roles": ["R-05"]}]
        app = _make_app(members)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token("rep@example.com")
        client.cookies.set(_COOKIE_NAME, token)
        response = client.post(
            "/jobs",
            data={"_csrf": "wrong-token-value"},
            follow_redirects=False,
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# AC-09: R-05 POST with correct _csrf → passes (200)
# ---------------------------------------------------------------------------

class TestCsrfValid:
    def test_csrf_valid_passes(self):
        """R-05 POST to /jobs with correct _csrf token → 200 (AC-09)."""
        members = [{"principal": "rep@example.com", "roles": ["R-05"]}]
        app = _make_app(members)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token("rep@example.com")
        client.cookies.set(_COOKIE_NAME, token)
        csrf_token = _make_csrf(token)
        response = client.post(
            "/jobs",
            data={"_csrf": csrf_token},
            follow_redirects=False,
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# AC-10: GET /health with no cookie → passes (not 302/403)
# ---------------------------------------------------------------------------

class TestPublicHealthExempt:
    def test_public_health_exempt(self):
        """GET /health with no session cookie → not 302 or 403 (AC-10)."""
        app = _make_app([])
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/health", follow_redirects=False)
        assert response.status_code not in (302, 403)


# ---------------------------------------------------------------------------
# AC-11: GET /login with no cookie → passes (not 302/403)
# ---------------------------------------------------------------------------

class TestPublicLoginExempt:
    def test_public_login_exempt(self):
        """GET /login with no session cookie → not 302 or 403 (AC-11)."""
        app = _make_app([])
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/login", follow_redirects=False)
        assert response.status_code not in (302, 403)


# ---------------------------------------------------------------------------
# AC-12: GET /auth/google with no cookie → passes (not 302/403)
# ---------------------------------------------------------------------------

class TestPublicAuthExempt:
    def test_public_auth_exempt(self):
        """GET /auth/google with no session cookie → not 302 or 403 (AC-12)."""
        app = _make_app([])
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/auth/google", follow_redirects=False)
        assert response.status_code not in (302, 403)


# ---------------------------------------------------------------------------
# AC-13: GET /static/foo.js with no cookie → passes (not 302/403)
# ---------------------------------------------------------------------------

class TestPublicStaticExempt:
    def test_public_static_exempt(self):
        """GET /static/foo.js with no session cookie → not 302 or 403 (AC-13)."""
        app = _make_app([])
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/static/foo.js", follow_redirects=False)
        assert response.status_code not in (302, 403)
