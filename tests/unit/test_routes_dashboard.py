"""Unit tests for the job dashboard and R-08 access control (Issue #40).

Covers:
- GET /jobs empty state shows "No jobs" message
- GET /jobs with multiple jobs shows all job IDs
- GET /jobs all terminal → no auto-refresh meta tag
- GET /jobs with active job → auto-refresh meta tag present
- R-08 session can access GET /jobs dashboard (read-only allowed)
- R-08 session is blocked from GET /jobs/new (403)
- GET /jobs/{id} with resolved_blocks renders the count

No live Google API calls; all external dependencies are patched.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Ensure scripts directory is on sys.path (same pattern as other unit tests)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../../.claude/skills/document-assembly/scripts")
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

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


@pytest.fixture(autouse=True)
def _clear_job_store():
    """Reset _JOB_STORE before each test to prevent cross-test contamination."""
    import web.routes.jobs as jobs_module

    jobs_module._JOB_STORE.clear()
    yield
    jobs_module._JOB_STORE.clear()


# ---------------------------------------------------------------------------
# Helpers (same pattern as test_routes_jobs.py)
# ---------------------------------------------------------------------------


def _make_client(raise_server_exceptions: bool = True) -> TestClient:
    """Create a fresh TestClient with the full app."""
    from web.app import create_app

    return TestClient(create_app(), raise_server_exceptions=raise_server_exceptions)


def _make_session_cookie() -> str:
    """Create a valid signed session cookie for _TEST_EMAIL."""
    from web.auth import create_session_token

    return create_session_token(_TEST_EMAIL)


def _authed_client() -> tuple[TestClient, str]:
    """Return (client, raw_session_token) with session cookie already set."""
    client = _make_client(raise_server_exceptions=False)
    token = _make_session_cookie()
    client.cookies.set("session", token)
    return client, token


# ---------------------------------------------------------------------------
# 1. GET /jobs empty state
# ---------------------------------------------------------------------------


class TestDashboardEmptyState:
    def test_dashboard_empty_state(self):
        """_JOB_STORE empty → GET /jobs returns 200, body contains 'No jobs'."""
        client, _ = _authed_client()
        response = client.get("/jobs", follow_redirects=False)
        assert response.status_code == 200, response.text
        body = response.text.lower()
        assert "no jobs" in body


# ---------------------------------------------------------------------------
# 2. GET /jobs shows multiple jobs
# ---------------------------------------------------------------------------


class TestDashboardShowsJobs:
    def test_dashboard_shows_jobs(self):
        """_JOB_STORE has 2 entries → GET /jobs returns 200, both job_ids in response."""
        import web.routes.jobs as jobs_module

        jobs_module._JOB_STORE["job_aaa"] = {
            "job_id": "job_aaa",
            "status": "completed",
            "family_key": "mss_sow",
        }
        jobs_module._JOB_STORE["job_bbb"] = {
            "job_id": "job_bbb",
            "status": "failed",
            "family_key": "mss_sow",
        }

        client, _ = _authed_client()
        response = client.get("/jobs", follow_redirects=False)

        assert response.status_code == 200, response.text
        body = response.text
        assert "job_aaa" in body
        assert "job_bbb" in body


# ---------------------------------------------------------------------------
# 3. No auto-refresh when all jobs are terminal
# ---------------------------------------------------------------------------


class TestDashboardNoRefreshWhenAllTerminal:
    def test_dashboard_no_refresh_when_all_terminal(self):
        """All jobs terminal → response HTML does NOT contain meta http-equiv='refresh'."""
        import web.routes.jobs as jobs_module

        jobs_module._JOB_STORE["job_done"] = {
            "job_id": "job_done",
            "status": "completed",
        }

        client, _ = _authed_client()
        response = client.get("/jobs", follow_redirects=False)

        assert response.status_code == 200, response.text
        assert 'http-equiv="refresh"' not in response.text
        assert "http-equiv='refresh'" not in response.text


# ---------------------------------------------------------------------------
# 4. Auto-refresh when an active job exists
# ---------------------------------------------------------------------------


class TestDashboardAutoRefreshWhenActive:
    def test_dashboard_auto_refresh_when_active(self):
        """One job has status='running' → response HTML contains meta refresh content='10'."""
        import web.routes.jobs as jobs_module

        jobs_module._JOB_STORE["job_running"] = {
            "job_id": "job_running",
            "status": "running",
        }

        client, _ = _authed_client()
        response = client.get("/jobs", follow_redirects=False)

        assert response.status_code == 200, response.text
        body = response.text
        assert 'http-equiv="refresh"' in body
        assert 'content="10"' in body


# ---------------------------------------------------------------------------
# 5. R-08 can access GET /jobs dashboard
# ---------------------------------------------------------------------------


class TestR08CanAccessDashboard:
    def test_r08_can_access_dashboard(self):
        """R-08 session → GET /jobs returns 200 (read-only user may view dashboard)."""
        client, _ = _authed_client()

        with patch("web.routes.jobs._lookup_roles", return_value=["R-08"]):
            response = client.get("/jobs", follow_redirects=False)

        assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# 6. R-08 blocked from GET /jobs/new
# ---------------------------------------------------------------------------


class TestR08BlockedFromNew:
    def test_r08_blocked_from_new(self):
        """R-08 session → GET /jobs/new returns 403."""
        client, _ = _authed_client()

        with patch("web.routes.jobs._lookup_roles", return_value=["R-08"]):
            response = client.get("/jobs/new", follow_redirects=False)

        assert response.status_code == 403, response.text


# ---------------------------------------------------------------------------
# 7. GET /jobs/{id} with resolved_blocks renders count
# ---------------------------------------------------------------------------


class TestDashboardEnhancedDetail:
    def test_dashboard_enhanced_detail(self):
        """_JOB_STORE entry with resolved_blocks=['b1','b2'] → GET /jobs/{id} shows count 2."""
        import web.routes.jobs as jobs_module

        job_id = "detail_resolved_test"
        jobs_module._JOB_STORE[job_id] = {
            "job_id": job_id,
            "status": "completed",
            "family_key": "mss_sow",
            "output_document_id": "doc_resolved_xyz",
            "resolved_blocks": ["b1", "b2"],
        }

        client, _ = _authed_client()
        response = client.get(f"/jobs/{job_id}", follow_redirects=False)

        assert response.status_code == 200, response.text
        body = response.text
        # The count is 2
        assert "2" in body
