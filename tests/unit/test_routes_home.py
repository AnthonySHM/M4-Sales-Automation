"""Unit tests for web/routes/home.py (Issue #49).

Covers:
- GET / with valid session → 200, page contains expected content and links
- GET / without session cookie → 302 redirect to /login
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TEST_SECRET = "test-secret-key-32chars-long-xxxxx"
_TEST_EMAIL = "user@example.com"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set required env vars for every test in this module."""
    monkeypatch.setenv("SESSION_SECRET_KEY", _TEST_SECRET)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(raise_server_exceptions: bool = True) -> TestClient:
    """Create a fresh TestClient with the full app."""
    from web.app import create_app

    return TestClient(create_app(), raise_server_exceptions=raise_server_exceptions)


def _make_session_cookie() -> str:
    """Create a valid signed session cookie for _TEST_EMAIL."""
    from web.auth import create_session_token

    return create_session_token(_TEST_EMAIL)


def _authed_client() -> TestClient:
    """Return a TestClient with a valid session cookie already set."""
    client = _make_client(raise_server_exceptions=False)
    token = _make_session_cookie()
    client.cookies.set("session", token)
    return client


# ---------------------------------------------------------------------------
# 1. Authenticated GET /
# ---------------------------------------------------------------------------


class TestGetHomeAuthenticated:
    def test_get_home_returns_200(self):
        """GET / with valid session → HTTP 200."""
        client = _authed_client()
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200, response.text

    def test_get_home_title(self):
        """GET / response contains the page title 'M4 Sales Automation'."""
        client = _authed_client()
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200
        assert "M4 Sales Automation" in response.text

    def test_get_home_link_to_jobs(self):
        """GET / response contains a link to /jobs."""
        client = _authed_client()
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200
        assert "/jobs" in response.text

    def test_get_home_link_to_jobs_new(self):
        """GET / response contains a link to /jobs/new."""
        client = _authed_client()
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200
        assert "/jobs/new" in response.text


# ---------------------------------------------------------------------------
# 2. Unauthenticated GET /
# ---------------------------------------------------------------------------


class TestGetHomeUnauthenticated:
    def test_get_home_unauthenticated_redirects(self):
        """GET / without session cookie → 302 redirect."""
        client = _make_client(raise_server_exceptions=False)
        response = client.get("/", follow_redirects=False)
        assert response.status_code in (302, 307)

    def test_get_home_unauthenticated_redirects_to_login(self):
        """GET / without session cookie → redirect location contains /login."""
        client = _make_client(raise_server_exceptions=False)
        response = client.get("/", follow_redirects=False)
        assert response.status_code in (302, 307)
        location = response.headers.get("location", "")
        assert "/login" in location


# ---------------------------------------------------------------------------
# 3. Nav bar regression
# ---------------------------------------------------------------------------


class TestNavBarLinks:
    def test_nav_contains_home_link(self):
        """base.html nav must contain a link to / (Home)."""
        client = _authed_client()
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200
        body = response.text
        # The nav should have href="/"
        assert 'href="/"' in body

    def test_nav_contains_dashboard_link(self):
        """base.html nav must contain a link to /jobs (Dashboard)."""
        client = _authed_client()
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200
        assert 'href="/jobs"' in body_of(response)

    def test_nav_contains_submit_job_link(self):
        """base.html nav must contain a link to /jobs/new (Submit Job)."""
        client = _authed_client()
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200
        assert 'href="/jobs/new"' in body_of(response)

    def test_nav_placeholder_comment_removed(self):
        """The old nav placeholder comment must no longer appear in the rendered page."""
        client = _authed_client()
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200
        # Jinja2 strips {# ... #} comments before rendering, so the raw text
        # of the comment will never appear in the output. Verify the nav links
        # are present instead.
        assert "Dashboard" in response.text
        assert "Submit Job" in response.text


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def body_of(response) -> str:
    return response.text
