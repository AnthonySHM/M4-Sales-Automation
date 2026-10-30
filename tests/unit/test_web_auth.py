"""Unit tests for web/auth.py and web/routes/auth.py (Issue #36).

Covers:
- Login page rendering
- OAuth redirect initiation and state cookie
- Callback CSRF state validation
- Callback creates session cookie on success
- Session cookie security attributes
- Expired token rejected by decode_session_token
- Logout clears session cookie
- Missing SESSION_SECRET_KEY raises RuntimeError
- require_auth dependency redirects when no cookie present

No live Google API calls; google_auth_oauthlib.flow.Flow is fully mocked.
"""
from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_SECRET = "test-secret-key-32chars-long-xxxxx"
_TEST_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
_TEST_CLIENT_SECRET = "test-client-secret"
_TEST_EMAIL = "user@example.com"

_BASE_ENV = {
    "SESSION_SECRET_KEY": _TEST_SECRET,
    "GOOGLE_OAUTH_CLIENT_ID": _TEST_CLIENT_ID,
    "GOOGLE_OAUTH_CLIENT_SECRET": _TEST_CLIENT_SECRET,
}


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Ensure all required env vars are set for every test in this module."""
    for key, value in _BASE_ENV.items():
        monkeypatch.setenv(key, value)


def _make_client(raise_server_exceptions: bool = True) -> TestClient:
    """Create a TestClient; env vars must already be set (via _set_env fixture)."""
    from web.app import create_app
    return TestClient(create_app(), raise_server_exceptions=raise_server_exceptions)


def _make_flow_mock(email: str = _TEST_EMAIL) -> MagicMock:
    """Return a mock Flow whose credentials carry an email in id_token."""
    flow = MagicMock()
    flow.authorization_url.return_value = (
        "https://accounts.google.com/o/oauth2/auth?mock=1",
        "mock-state",
    )
    flow.credentials.id_token = {"email": email, "sub": "12345"}
    flow.fetch_token = MagicMock()
    return flow


# ---------------------------------------------------------------------------
# 1. Login page returns 200 and contains "Sign in with Google"
# ---------------------------------------------------------------------------

class TestLoginPage:
    def test_login_page_returns_200(self):
        client = _make_client()
        response = client.get("/login", follow_redirects=False)
        assert response.status_code == 200

    def test_login_page_contains_sign_in_text(self):
        client = _make_client()
        response = client.get("/login", follow_redirects=False)
        assert "Sign in with Google" in response.text

    def test_login_page_content_type_html(self):
        client = _make_client()
        response = client.get("/login", follow_redirects=False)
        assert "text/html" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# 2. GET /auth/google redirects to Google and sets _oauth_state cookie
# ---------------------------------------------------------------------------

class TestAuthGoogleRedirect:
    def test_auth_google_redirects_302(self):
        client = _make_client()
        with patch("web.routes.auth.build_oauth_flow", return_value=_make_flow_mock()):
            response = client.get("/auth/google", follow_redirects=False)
        assert response.status_code == 302

    def test_auth_google_redirects_to_google_domain(self):
        client = _make_client()
        with patch("web.routes.auth.build_oauth_flow", return_value=_make_flow_mock()):
            response = client.get("/auth/google", follow_redirects=False)
        location = response.headers["location"]
        assert "accounts.google.com" in location

    def test_auth_google_sets_state_cookie(self):
        client = _make_client()
        with patch("web.routes.auth.build_oauth_flow", return_value=_make_flow_mock()):
            response = client.get("/auth/google", follow_redirects=False)
        # The state cookie should be present in Set-Cookie header
        set_cookie = response.headers.get("set-cookie", "")
        assert "_oauth_state" in set_cookie

    def test_auth_google_state_cookie_is_httponly(self):
        client = _make_client()
        with patch("web.routes.auth.build_oauth_flow", return_value=_make_flow_mock()):
            response = client.get("/auth/google", follow_redirects=False)
        set_cookie = response.headers.get("set-cookie", "").lower()
        assert "httponly" in set_cookie


# ---------------------------------------------------------------------------
# 3. Callback state mismatch returns 400
# ---------------------------------------------------------------------------

class TestCallbackStateMismatch:
    def test_state_mismatch_returns_400(self):
        client = _make_client(raise_server_exceptions=False)
        # Send mismatched state: query param != cookie value
        client.cookies.set("_oauth_state", "correct-state")
        response = client.get(
            "/auth/callback?code=abc&state=wrong-state",
            follow_redirects=False,
        )
        assert response.status_code == 400

    def test_state_mismatch_body_has_error_field(self):
        client = _make_client(raise_server_exceptions=False)
        client.cookies.set("_oauth_state", "correct-state")
        response = client.get(
            "/auth/callback?code=abc&state=wrong-state",
            follow_redirects=False,
        )
        body = response.json()
        assert body.get("error") == "state_mismatch"

    def test_missing_state_returns_400(self):
        client = _make_client(raise_server_exceptions=False)
        # No state cookie at all, no state query param
        response = client.get(
            "/auth/callback?code=abc",
            follow_redirects=False,
        )
        assert response.status_code == 400

    def test_error_param_redirects_to_login(self):
        """Google returning error=access_denied should redirect to /login."""
        client = _make_client()
        response = client.get(
            "/auth/callback?error=access_denied",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# 4. Successful callback creates session cookie, redirects to /jobs
# ---------------------------------------------------------------------------

class TestCallbackSuccess:
    def _do_callback(self, client: TestClient, state: str = "valid-state") -> object:
        """Inject matching state cookie and perform callback request."""
        client.cookies.set("_oauth_state", state)
        with patch("web.routes.auth.build_oauth_flow", return_value=_make_flow_mock()):
            response = client.get(
                f"/auth/callback?code=authcode&state={state}",
                follow_redirects=False,
            )
        return response

    def test_successful_callback_redirects_302(self):
        client = _make_client()
        response = self._do_callback(client)
        assert response.status_code == 302

    def test_successful_callback_redirects_to_jobs(self):
        client = _make_client()
        response = self._do_callback(client)
        assert response.headers["location"] == "/jobs"

    def test_successful_callback_sets_session_cookie(self):
        client = _make_client()
        response = self._do_callback(client)
        set_cookie = response.headers.get("set-cookie", "")
        assert "session=" in set_cookie

    def test_successful_callback_session_cookie_not_empty(self):
        client = _make_client()
        response = self._do_callback(client)
        # Extract cookie value — must be non-trivial
        set_cookie = response.headers.get("set-cookie", "")
        # Format: "session=<value>; ..."
        session_part = [p for p in set_cookie.split(";") if p.strip().startswith("session=")]
        assert session_part, "session cookie not found in Set-Cookie"
        value = session_part[0].split("=", 1)[1].strip()
        assert len(value) > 20


# ---------------------------------------------------------------------------
# 5. Session cookie security attributes
# ---------------------------------------------------------------------------

class TestSessionCookieAttributes:
    def _get_session_set_cookie(self, client: TestClient) -> str:
        state = "sec-test-state"
        client.cookies.set("_oauth_state", state)
        with patch("web.routes.auth.build_oauth_flow", return_value=_make_flow_mock()):
            response = client.get(
                f"/auth/callback?code=authcode&state={state}",
                follow_redirects=False,
            )
        # Return the Set-Cookie header for the session cookie
        for header_value in response.headers.get_list("set-cookie"):
            if "session=" in header_value:
                return header_value.lower()
        return ""

    def test_session_cookie_is_httponly(self):
        client = _make_client()
        cookie_header = self._get_session_set_cookie(client)
        assert "httponly" in cookie_header

    def test_session_cookie_is_samesite_lax(self):
        client = _make_client()
        cookie_header = self._get_session_set_cookie(client)
        assert "samesite=lax" in cookie_header

    def test_session_cookie_has_max_age(self):
        client = _make_client()
        cookie_header = self._get_session_set_cookie(client)
        assert "max-age=" in cookie_header


# ---------------------------------------------------------------------------
# 6. Expired session token returns None from decode_session_token
# ---------------------------------------------------------------------------

class TestExpiredSession:
    def test_expired_token_returns_none(self):
        from web.auth import _serializer

        # Build a token whose itsdangerous timestamp is 9 hours in the past.
        # itsdangerous embeds time.time() via its internal Signer; patch it there.
        past_time = time.time() - (9 * 3600)
        with patch("itsdangerous.timed.time") as mock_time:
            mock_time.return_value = past_time
            token = _serializer().dumps({"email": _TEST_EMAIL, "created_at": past_time})

        from web.auth import decode_session_token
        result = decode_session_token(token)
        assert result is None

    def test_valid_token_returns_payload(self):
        from web.auth import create_session_token, decode_session_token

        token = create_session_token(_TEST_EMAIL)
        result = decode_session_token(token)
        assert result is not None
        assert result["email"] == _TEST_EMAIL

    def test_tampered_token_returns_none(self):
        from web.auth import create_session_token, decode_session_token

        token = create_session_token(_TEST_EMAIL)
        tampered = token[:-4] + "xxxx"
        result = decode_session_token(tampered)
        assert result is None


# ---------------------------------------------------------------------------
# 7. Logout clears session cookie and redirects to /login
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_redirects_302(self):
        client = _make_client()
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 302

    def test_logout_redirects_to_login(self):
        client = _make_client()
        response = client.get("/logout", follow_redirects=False)
        assert response.headers["location"] == "/login"

    def test_logout_clears_session_cookie(self):
        client = _make_client()
        response = client.get("/logout", follow_redirects=False)
        # The response should include a Set-Cookie that clears the session
        set_cookie = response.headers.get("set-cookie", "")
        # Cleared cookies are set with max-age=0 or expires in the past
        # FastAPI delete_cookie sets max-age=0
        assert "session=" in set_cookie
        assert "max-age=0" in set_cookie.lower() or 'expires=' in set_cookie.lower()


# ---------------------------------------------------------------------------
# 8. Missing SESSION_SECRET_KEY raises RuntimeError
# ---------------------------------------------------------------------------

class TestMissingSecretKey:
    def test_missing_secret_key_raises(self, monkeypatch):
        # _set_env autouse fixture sets the key; delete it for this test only
        monkeypatch.delenv("SESSION_SECRET_KEY", raising=False)
        from web.auth import _get_secret_key
        with pytest.raises(RuntimeError, match="SESSION_SECRET_KEY"):
            _get_secret_key()

    def test_empty_secret_key_raises(self, monkeypatch):
        monkeypatch.setenv("SESSION_SECRET_KEY", "")
        from web.auth import _get_secret_key
        with pytest.raises(RuntimeError, match="SESSION_SECRET_KEY"):
            _get_secret_key()


# ---------------------------------------------------------------------------
# 9. require_auth dependency redirects to /login when no session cookie
# ---------------------------------------------------------------------------

class TestRequireAuth:
    def _make_protected_client(self) -> TestClient:
        """Create app with a protected test route wired to require_auth."""
        from web.app import create_app
        from web.auth import require_auth

        app = create_app()

        @app.get("/protected-test")
        async def protected(email: str = Depends(require_auth)):
            return {"email": email}

        return TestClient(app, raise_server_exceptions=False)

    def test_no_cookie_redirects_to_login(self):
        client = self._make_protected_client()
        response = client.get("/protected-test", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["location"]

    def test_valid_session_allows_access(self):
        from web.auth import create_session_token

        token = create_session_token(_TEST_EMAIL)
        client = self._make_protected_client()
        # Inject session cookie directly (TestClient/HTTP ignores Secure flag)
        client.cookies.set("session", token)
        response = client.get("/protected-test", follow_redirects=False)
        assert response.status_code == 200
        assert response.json()["email"] == _TEST_EMAIL

    def test_invalid_session_redirects_to_login(self):
        client = self._make_protected_client()
        client.cookies.set("session", "invalid.token.value")
        response = client.get("/protected-test", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["location"]
