"""scripts.validate_request — Re-export shim (Issue #38, AC-1).

Delegates to the real implementation in
.claude/skills/document-assembly/scripts/validate_request.py.

Usage:
    from scripts.validate_request import validate_request
"""
from __future__ import annotations

# Ensure _REAL_SCRIPTS_DIR is on sys.path (idempotent).
import scripts  # noqa: F401 — side-effect: sys.path setup

from validate_request import validate_request  # noqa: F401

__all__ = ["validate_request"]
