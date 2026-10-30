"""Unit tests for web/routes/jobs.py (Issue #39).

Covers:
- GET /jobs/new renders the submission form with option selects and placeholder inputs
- POST /jobs with valid fields redirects 303 to /jobs/<id>
- POST /jobs with invalid option value returns 422 with error HTML
- POST /jobs where assemble times out returns 500 with "failed" in body
- GET /jobs/<job_id> returns 200 with job_id and drive_link
- GET /health still returns 200 (no regression)

No live Google API calls; all external dependencies are patched.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import sys
from unittest.mock import MagicMock, patch

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
    # No GOOGLE_APPLICATION_CREDENTIALS — _build_clients returns (None, None, None)
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


def _csrf_token_for(raw_cookie: str) -> str:
    """Derive the CSRF token that the middleware / route expects."""
    key = ("csrf:" + _TEST_SECRET).encode()
    return hmac.new(key, raw_cookie.encode(), hashlib.sha256).hexdigest()


def _authed_client() -> tuple[TestClient, str]:
    """Return (client, raw_session_token) with session cookie already set."""
    client = _make_client(raise_server_exceptions=False)
    token = _make_session_cookie()
    client.cookies.set("session", token)
    return client, token


def _valid_form_data(csrf_token: str) -> dict:
    """Return a minimal valid form payload for the mss_sow recipe."""
    return {
        "_csrf": csrf_token,
        "tier": "elite",
        "channel": "resell",
        "addon_siem": "no",
        "addon_firewall": "no",
        "addon_storage": "no",
        "addon_endpoint_patching": "no",
        "addon_sentinelone": "no",
        "include_slo": "no",
        "customer_name": "Acme Corp",
        "customer_logo": "",
        "customer_contact_name": "Jane Doe",
        "customer_contact_title": "CTO",
        "account_manager_name": "John Smith",
        "sow_date": "2026-01-01",
        "quote_number": "Q-001",
        "revision_number": "1",
        "msa_date": "2025-01-01",
        "order_start_date": "2026-02-01",
        "hot_storage_months": "3",
        "cold_storage_months": "12",
        "poc_fee_monthly": "1000",
        "term_fee_monthly": "5000",
        "remainder_fee_monthly": "500",
        "min_endpoint_count": "100",
        "service_tier_full_name": "Elite MDR",
    }


# ---------------------------------------------------------------------------
# 1. GET /jobs/new renders the form
# ---------------------------------------------------------------------------


class TestGetJobsNew:
    def test_get_jobs_new_renders_form(self):
        """GET /jobs/new with valid session → 200, form contains selects and inputs."""
        client, token = _authed_client()
        response = client.get("/jobs/new", follow_redirects=False)
        assert response.status_code == 200, response.text
        body = response.text
        # Should contain a select for the first option key
        assert "<select" in body
        assert 'name="tier"' in body
        # Should contain inputs for placeholder keys (lowercased)
        assert 'name="customer_name"' in body
        assert "<form" in body

    def test_get_jobs_new_has_csrf_hidden_input(self):
        """Form must include a hidden _csrf field."""
        client, token = _authed_client()
        response = client.get("/jobs/new", follow_redirects=False)
        assert response.status_code == 200
        assert 'name="_csrf"' in response.text

    def test_get_jobs_new_unauthenticated_redirects(self):
        """Without session cookie, GET /jobs/new redirects to login."""
        client = _make_client(raise_server_exceptions=False)
        response = client.get("/jobs/new", follow_redirects=False)
        assert response.status_code in (302, 307)


# ---------------------------------------------------------------------------
# 2. POST /jobs with valid fields redirects 303 to /jobs/<id>
# ---------------------------------------------------------------------------


class TestPostJobsValid:
    def test_post_jobs_valid_redirects(self):
        """POST /jobs with valid data → 303 redirect to /jobs/<id>."""
        client, token = _authed_client()
        csrf = _csrf_token_for(token)
        form = _valid_form_data(csrf)

        with (
            patch("web.routes.jobs._build_clients", return_value=(None, None, None)),
            patch(
                "web.routes.jobs.validate_request",
                return_value={"valid": True, "errors": []},
            ),
            patch(
                "web.routes.jobs.assemble",
                return_value={
                    "job_id": "abc123",
                    "status": "completed",
                    "output_document_id": "doc456",
                },
            ),
        ):
            response = client.post("/jobs", data=form, follow_redirects=False)

        assert response.status_code == 303, response.text
        location = response.headers.get("location", "")
        assert "/jobs/abc123" in location

    def test_post_jobs_valid_stores_result_in_job_store(self):
        """After a successful POST, _JOB_STORE[job_id] should be populated."""
        import web.routes.jobs as jobs_module

        client, token = _authed_client()
        csrf = _csrf_token_for(token)
        form = _valid_form_data(csrf)

        fake_result = {
            "job_id": "store_test_id",
            "status": "completed",
            "output_document_id": "docXYZ",
        }

        with (
            patch("web.routes.jobs._build_clients", return_value=(None, None, None)),
            patch(
                "web.routes.jobs.validate_request",
                return_value={"valid": True, "errors": []},
            ),
            patch("web.routes.jobs.assemble", return_value=fake_result),
        ):
            client.post("/jobs", data=form, follow_redirects=False)

        assert "store_test_id" in jobs_module._JOB_STORE


# ---------------------------------------------------------------------------
# 3. POST /jobs with invalid option value returns 422
# ---------------------------------------------------------------------------


class TestPostJobsInvalid:
    def test_post_jobs_invalid_option_422(self):
        """POST /jobs with bad option → 422, HTML body contains error message."""
        client, token = _authed_client()
        csrf = _csrf_token_for(token)
        form = _valid_form_data(csrf)
        form["tier"] = "bad_value"

        validation_result = {
            "valid": False,
            "errors": [
                {
                    "field": "options.tier",
                    "code": "invalid_value",
                    "message": "tier must be one of ['elite', 'enterprise', 'premium', 'strategic']",
                }
            ],
        }

        with (
            patch("web.routes.jobs._build_clients", return_value=(None, None, None)),
            patch("web.routes.jobs.validate_request", return_value=validation_result),
        ):
            response = client.post("/jobs", data=form, follow_redirects=False)

        assert response.status_code == 422, response.text
        body = response.text
        assert "tier" in body or "options.tier" in body

    def test_post_jobs_invalid_shows_form_again(self):
        """422 response should re-render the submission form (not a redirect)."""
        client, token = _authed_client()
        csrf = _csrf_token_for(token)
        form = _valid_form_data(csrf)

        validation_result = {
            "valid": False,
            "errors": [
                {
                    "field": "options.channel",
                    "code": "missing_required_option",
                    "message": "required option 'channel' is missing",
                }
            ],
        }

        with (
            patch("web.routes.jobs._build_clients", return_value=(None, None, None)),
            patch("web.routes.jobs.validate_request", return_value=validation_result),
        ):
            response = client.post("/jobs", data=form, follow_redirects=False)

        assert response.status_code == 422
        assert "<form" in response.text


# ---------------------------------------------------------------------------
# 4. POST /jobs where assemble times out returns 500
# ---------------------------------------------------------------------------


class TestPostJobsTimeout:
    def test_post_jobs_timeout_returns_failed(self):
        """POST /jobs where assemble raises TimeoutError → 500, body contains 'failed'."""
        client, token = _authed_client()
        csrf = _csrf_token_for(token)
        form = _valid_form_data(csrf)

        async def _fake_wait_for(coro, timeout):
            raise asyncio.TimeoutError()

        with (
            patch("web.routes.jobs._build_clients", return_value=(None, None, None)),
            patch(
                "web.routes.jobs.validate_request",
                return_value={"valid": True, "errors": []},
            ),
            patch("asyncio.wait_for", side_effect=_fake_wait_for),
        ):
            response = client.post("/jobs", data=form, follow_redirects=False)

        assert response.status_code == 500, response.text
        body = response.text.lower()
        assert "failed" in body or "timeout" in body


# ---------------------------------------------------------------------------
# 5. GET /jobs/{job_id} returns 200 with job_id and drive_link
# ---------------------------------------------------------------------------


class TestGetJobDetail:
    def test_get_job_detail(self):
        """GET /jobs/<id> after result stored → 200, body contains job_id and drive link."""
        import web.routes.jobs as jobs_module

        job_id = "detail_test_abc"
        jobs_module._JOB_STORE[job_id] = {
            "job_id": job_id,
            "status": "completed",
            "output_document_id": "doc_detail_xyz",
        }

        client, token = _authed_client()
        response = client.get(f"/jobs/{job_id}", follow_redirects=False)

        assert response.status_code == 200, response.text
        body = response.text
        assert job_id in body
        # Should contain a link to the output document
        assert "doc_detail_xyz" in body or "drive.google.com" in body or "docs.google.com" in body

    def test_get_job_detail_unknown_id(self):
        """GET /jobs/<unknown> → 200 with 'unknown' status (minimal page)."""
        client, token = _authed_client()
        response = client.get("/jobs/nonexistent_job_id_xyz", follow_redirects=False)

        assert response.status_code == 200
        body = response.text
        assert "nonexistent_job_id_xyz" in body

    def test_get_job_detail_unauthenticated_redirects(self):
        """Without session cookie, GET /jobs/<id> should redirect to login."""
        client = _make_client(raise_server_exceptions=False)
        response = client.get("/jobs/some_job_id", follow_redirects=False)
        assert response.status_code in (302, 307)


# ---------------------------------------------------------------------------
# 6. GET /health still works (regression check)
# ---------------------------------------------------------------------------


class TestHealthRegression:
    def test_public_health_still_works(self):
        """GET /health must return 200 with no auth required (no regression)."""
        client = _make_client()
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
