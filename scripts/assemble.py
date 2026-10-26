"""scripts.assemble — Re-export shim (Issue #38, AC-1).

Delegates to the real implementation in
.claude/skills/document-assembly/scripts/assemble.py.

Usage:
    from scripts.assemble import assemble
"""
from __future__ import annotations

# Ensure _REAL_SCRIPTS_DIR is on sys.path (idempotent).
import scripts  # noqa: F401 — side-effect: sys.path setup

from assemble import assemble  # noqa: F401

__all__ = ["assemble"]
