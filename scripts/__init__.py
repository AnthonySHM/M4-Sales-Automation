"""scripts — Thin re-export shim for the document-assembly scripts package.

Allows ``from scripts.assemble import assemble`` (and equivalents for the
other three modules) to work from the repository root without modifying the
canonical scripts directory (.claude/skills/document-assembly/scripts/).

The real implementations live in:
    .claude/skills/document-assembly/scripts/

This package adds that directory to sys.path on first import so every
sub-module can delegate directly to the real module.  No business logic lives
here (AD-20, TL-15).
"""
from __future__ import annotations

import os
import sys

_REAL_SCRIPTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../.claude/skills/document-assembly/scripts")
)
if _REAL_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _REAL_SCRIPTS_DIR)
