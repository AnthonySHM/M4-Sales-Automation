"""scripts.review — Re-export shim (Issue #38, AC-1).

Delegates to the real implementation in
.claude/skills/document-assembly/scripts/review.py.

Usage:
    from scripts.review import review
"""
from __future__ import annotations

# Ensure _REAL_SCRIPTS_DIR is on sys.path (idempotent).
import scripts  # noqa: F401 — side-effect: sys.path setup

from review import review  # noqa: F401

__all__ = ["review"]
