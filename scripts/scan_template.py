"""scripts.scan_template — Re-export shim (Issue #38, AC-1).

Delegates to the real implementation in
.claude/skills/document-assembly/scripts/scan_template.py.

Usage:
    from scripts.scan_template import scan_template
"""
from __future__ import annotations

# Ensure _REAL_SCRIPTS_DIR is on sys.path (idempotent).
import scripts  # noqa: F401 — side-effect: sys.path setup

from scan_template import scan_template  # noqa: F401

__all__ = ["scan_template"]
