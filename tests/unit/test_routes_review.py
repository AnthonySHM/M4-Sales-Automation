"""Unit tests for web/routes/review.py (Issue #41).

Covers:
- GET /jobs/{id}/review renders form for awaiting_review jobs
- GET /jobs/{id}/review redirects non-awaiting_review jobs
- GET /jobs/nonexistent/review returns 404
- POST approve → 303 redirect
- POST reject with reason → 303 redirect
- POST reject without reason → 422 with error message
- R-05 role → 403 on GET (middleware blocks)
- R-05 role → 403 on POST (middleware blocks)

No live Google API calls; all external dependencies are patched.

Note on Starlette middleware and form body:
  Starlette's BaseHTTPMiddleware reads the request stream (via request.form()) to
  validate the CSRF token.  Because the stream is consumed, the route handler
  receives an empty form when using the full TestClient stack.  The GET and
  role-enforcement tests use the full TestClient stack (they do not depend on
  form field values).  The POST decision tests bypass this constraint by calling
  the route coroutine directly with a mock Request that returns the expected
  FormData.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import FormData

# ---------------------------------------------------------------------------
# Ensure scripts directory is on sys.path
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
_TEST_EMAIL = "reviewer@example.com"
_REP_EMAIL = "rep@test.com"

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


def _make_session_cookie(email: str = _TEST_EMAIL) -> str:
    """Create a valid signed session cookie for the given email."""
    from web.auth import create_session_token

    return create_session_token(email)


def _csrf_token_for(raw_cookie: str) -> str:
    """Derive the CSRF token that the middleware / route expects."""
    key = ("csrf:" + _TEST_SECRET).encode()
    return hmac.new(key, raw_cookie.encode(), hashlib.sha256).hexdigest()


def _authed_client(email: str = _TEST_EMAIL) -> tuple[TestClient, str]:
    """Return (client, raw_session_token) with session cookie already set."""
    client = _make_client(raise_server_exceptions=False)
    token = _make_session_cookie(email)
    client.cookies.set("session", token)
    return client, token


# ---------------------------------------------------------------------------
# 1. GET /jobs/{id}/review renders form for awaiting_review job
# ---------------------------------------------------------------------------


class TestGetReviewForm:
    def test_get_review_renders_form(self):
        """GET /jobs/{id}/review with awaiting_review status → 200, form present."""
        import web.routes.jobs as jobs_module

        job_id = "review_get_test_001"
        jobs_module._JOB_STORE[job_id] = {
            "job_id": job_id,
            "status": "awaiting_review",
        }

        client, token = _authed_client()
        response = client.get(f"/jobs/{job_id}/review", follow_redirects=False)

        assert response.status_code == 200, response.text
        body = response.text
        assert "<form" in body
        assert "textarea" in body
        assert "_csrf" in body

    def test_get_review_wrong_status_redirects(self):
        """GET /jobs/{id}/review for a completed job → 302 to /jobs/{id}."""
        import web.routes.jobs as jobs_module

        job_id = "review_wrong_status_002"
        jobs_module._JOB_STORE[job_id] = {
            "job_id": job_id,
            "status": "completed",
        }

        client, token = _authed_client()
        response = client.get(f"/jobs/{job_id}/review", follow_redirects=False)

        assert response.status_code == 302
        location = response.headers.get("location", "")
        assert f"/jobs/{job_id}" in location

    def test_get_review_unknown_job_404(self):
        """GET /jobs/nonexistent/review → 404."""
        client, token = _authed_client()
        response = client.get("/jobs/nonexistent_job_xyz/review", follow_redirects=False)

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Helper: build a mock Request with a controlled form payload
# ---------------------------------------------------------------------------


def _mock_request_with_form(form_data: dict, job_id: str = "", templates=None) -> MagicMock:
    """Build a mock FastAPI Request whose .form() coroutine returns form_data.

    Starlette's BaseHTTPMiddleware consumes the request body stream to validate
    CSRF tokens, so the route handler always sees an empty form when going through
    the full TestClient stack.  Calling the route coroutine directly with this
    mock bypasses that limitation and lets us test the actual business logic.
    """
    form = FormData(form_data)
    request = MagicMock()
    request.form = AsyncMock(return_value=form)
    request.cookies = {"session": _make_session_cookie()}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"

    # app.state.templates — needed for TemplateResponse calls on 422
    mock_templates = MagicMock()
    mock_app = MagicMock()
    mock_app.state.templates = mock_templates
    request.app = mock_app

    return request


# ---------------------------------------------------------------------------
# 2. POST approve → 303 redirect
# ---------------------------------------------------------------------------


class TestPostReviewApprove:
    def test_post_review_approve(self):
        """POST decision=approved → 303 redirect to /jobs/{id}.

        The route coroutine is called directly with a mock Request to sidestep
        the Starlette middleware body-consumption issue (see module docstring).
        """
        import asyncio
        import web.routes.jobs as jobs_module
        from web.routes.review import post_review

        job_id = "review_approve_test_003"
        jobs_module._JOB_STORE[job_id] = {
            "job_id": job_id,
            "status": "awaiting_review",
        }

        request = _mock_request_with_form({"decision": "approved", "reason": ""}, job_id)

        with (
            patch(
                "web.routes.review._script_review",
                return_value={"exit_code": 0, "status": "approved"},
            ),
            patch(
                "web.routes.review._build_clients",
                return_value=(None, None, None),
            ),
        ):
            response = asyncio.run(
                post_review(job_id=job_id, request=request, email="reviewer@example.com")
            )

        from fastapi.responses import RedirectResponse
        assert isinstance(response, RedirectResponse), f"Expected redirect, got: {response}"
        location = response.headers.get("location", "")
        assert f"/jobs/{job_id}" in location


# ---------------------------------------------------------------------------
# 3. POST reject with reason → 303 redirect
# ---------------------------------------------------------------------------


class TestPostReviewRejectWithReason:
    def test_post_review_reject_with_reason(self):
        """POST decision=rejected with non-empty reason → 303 redirect.

        Called directly to bypass middleware body-consumption (see module docstring).
        """
        import asyncio
        import web.routes.jobs as jobs_module
        from web.routes.review import post_review

        job_id = "review_reject_test_004"
        jobs_module._JOB_STORE[job_id] = {
            "job_id": job_id,
            "status": "awaiting_review",
        }

        request = _mock_request_with_form(
            {"decision": "rejected", "reason": "Needs revision"}, job_id
        )

        with (
            patch(
                "web.routes.review._script_review",
                return_value={"exit_code": 0, "status": "rejected"},
            ),
            patch(
                "web.routes.review._build_clients",
                return_value=(None, None, None),
            ),
        ):
            response = asyncio.run(
                post_review(job_id=job_id, request=request, email="reviewer@example.com")
            )

        from fastapi.responses import RedirectResponse
        assert isinstance(response, RedirectResponse), f"Expected redirect, got: {response}"
        location = response.headers.get("location", "")
        assert f"/jobs/{job_id}" in location


# ---------------------------------------------------------------------------
# 4. POST reject without reason → 422
# ---------------------------------------------------------------------------


class TestPostReviewRejectNoReason:
    def test_post_review_reject_no_reason_422(self):
        """POST decision=rejected with empty reason → 422, body contains 'required'.

        Called directly to bypass middleware body-consumption (see module docstring).
        The route must return a TemplateResponse (not call _script_review) when
        decision is 'rejected' but reason is empty.
        """
        import asyncio
        import web.routes.jobs as jobs_module
        from web.routes.review import post_review

        job_id = "review_no_reason_test_005"
        jobs_module._JOB_STORE[job_id] = {
            "job_id": job_id,
            "status": "awaiting_review",
        }

        request = _mock_request_with_form({"decision": "rejected", "reason": ""}, job_id)

        # Set up mock templates to capture the rendered context
        rendered_context = {}

        def fake_template_response(name, context, status_code=200):
            rendered_context.update(context)
            mock_resp = MagicMock()
            mock_resp.status_code = status_code
            return mock_resp

        request.app.state.templates.TemplateResponse = fake_template_response

        with patch("web.routes.review._script_review") as mock_script:
            response = asyncio.run(
                post_review(job_id=job_id, request=request, email="reviewer@example.com")
            )
            # _script_review must NOT be called when reason is missing
            mock_script.assert_not_called()

        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        error_msg = rendered_context.get("error", "")
        assert error_msg is not None and (
            "required" in error_msg.lower() or "reason" in error_msg.lower()
        ), f"Expected rejection reason error, got: {error_msg}"


# ---------------------------------------------------------------------------
# 5. R-05 role → 403 on GET review route
# ---------------------------------------------------------------------------


class TestR05BlockedOnReview:
    def test_r05_get_review_403(self):
        """R-05 session → GET /jobs/{id}/review → 403 (middleware blocks)."""
        import web.routes.jobs as jobs_module

        job_id = "review_r05_get_006"
        jobs_module._JOB_STORE[job_id] = {
            "job_id": job_id,
            "status": "awaiting_review",
        }

        client, token = _authed_client(email=_REP_EMAIL)

        with patch(
            "web.middleware._MEMBERS",
            [{"principal": _REP_EMAIL, "roles": ["R-05"]}],
        ):
            response = client.get(
                f"/jobs/{job_id}/review",
                follow_redirects=False,
            )

        assert response.status_code == 403, response.text

    def test_r05_post_review_403(self):
        """R-05 session → POST /jobs/{id}/review → 403 (middleware blocks)."""
        import web.routes.jobs as jobs_module

        job_id = "review_r05_post_007"
        jobs_module._JOB_STORE[job_id] = {
            "job_id": job_id,
            "status": "awaiting_review",
        }

        client, token = _authed_client(email=_REP_EMAIL)
        csrf = _csrf_token_for(token)

        with patch(
            "web.middleware._MEMBERS",
            [{"principal": _REP_EMAIL, "roles": ["R-05"]}],
        ):
            response = client.post(
                f"/jobs/{job_id}/review",
                data={"_csrf": csrf, "decision": "approved", "reason": ""},
                follow_redirects=False,
            )

        assert response.status_code == 403, response.text
