"""
web/routes/home.py — Landing page route.

Routes:
  GET /   — render home.html (requires auth)

Architecture refs: AD-15 (FastAPI), AD-19 (Jinja2).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from web.auth import require_auth

router = APIRouter()


@router.get("/")
async def get_home(request: Request, email: str = Depends(require_auth)):
    """Render the home landing page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "home.html", {"email": email})
