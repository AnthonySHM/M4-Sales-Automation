"""Unit tests for the web application skeleton (Issue #34).

Covers:
- GET /health returns HTTP 200 and {"status": "ok"}
- from web.app import create_app has no import-time side effects (TL-15)
- Jinja2 initialises without error on TestClient round-trip to /health

No live Google API calls; no network I/O beyond the in-process TestClient.
"""

import importlib
import sys

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> TestClient:
    """Create a fresh TestClient for each test that needs one."""
    from web.app import create_app

    return TestClient(create_app())


# ---------------------------------------------------------------------------
# AC-1: GET /health returns HTTP 200 and correct JSON body
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_200(self):
        client = _make_client()
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_correct_json(self):
        client = _make_client()
        response = client.get("/health")
        assert response.json() == {"status": "ok"}

    def test_health_content_type_is_json(self):
        client = _make_client()
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]

    def test_health_not_html_error_page(self):
        """Response body must be valid JSON, not an HTML error page (AC-3)."""
        client = _make_client()
        response = client.get("/health")
        # Will raise if body is not valid JSON (e.g. Jinja2 error rendered as HTML)
        body = response.json()
        assert isinstance(body, dict)


# ---------------------------------------------------------------------------
# AC-2: create_app import has no side effects (TL-15)
# ---------------------------------------------------------------------------


class TestCreateAppImportSideEffects:
    def test_import_completes_without_exception(self):
        """Importing web.app must not raise, call sys.exit, or do network I/O."""
        # Remove from cache to force a fresh import (in case prior tests cached it)
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("web"):
                del sys.modules[mod_name]

        # Should not raise
        web_app_mod = importlib.import_module("web.app")
        assert hasattr(web_app_mod, "create_app")

    def test_create_app_returns_fastapi_instance(self):
        from fastapi import FastAPI
        from web.app import create_app

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_create_app_called_twice_returns_independent_instances(self):
        """Factory must be callable multiple times without error (TL-15)."""
        from web.app import create_app

        app1 = create_app()
        app2 = create_app()
        assert app1 is not app2

    def test_module_level_has_no_app_object(self):
        """There must be no module-level FastAPI app instantiation (TL-15)."""
        import web.app as web_app_mod
        from fastapi import FastAPI

        # The module should not expose a top-level `app` variable
        assert not isinstance(getattr(web_app_mod, "app", None), FastAPI), (
            "web.app must not define a module-level FastAPI instance; "
            "use create_app() factory only (TL-15)"
        )


# ---------------------------------------------------------------------------
# AC-3: Jinja2 initialises without error on TestClient round-trip
# ---------------------------------------------------------------------------


class TestJinja2Initialisation:
    def test_templates_initialised_on_app_state(self):
        """app.state.templates must be a Jinja2Templates instance after create_app()."""
        from fastapi.templating import Jinja2Templates
        from web.app import create_app

        app = create_app()
        assert isinstance(app.state.templates, Jinja2Templates)

    def test_health_round_trip_does_not_raise_template_error(self):
        """A round-trip to /health must not produce a Jinja2 / 500 error."""
        client = _make_client()
        response = client.get("/health")
        # Any Jinja2 init error would surface as a 500 with an HTML body
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_base_template_file_exists(self):
        """web/templates/base.html must exist on disk (AC-3 prerequisite)."""
        import pathlib

        templates_dir = (
            pathlib.Path(__file__).parent.parent.parent / "web" / "templates"
        )
        base_html = templates_dir / "base.html"
        assert base_html.exists(), f"base.html not found at {base_html}"

    @pytest.mark.parametrize("path", ["/health"])
    def test_parametrised_endpoints_return_200(self, path):
        """Parametrised smoke test — extend list as new routes are added."""
        client = _make_client()
        response = client.get(path)
        assert response.status_code == 200
