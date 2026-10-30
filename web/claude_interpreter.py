"""
web/claude_interpreter.py — Natural language → structured request fields via Claude API.

Architecture refs: AD-25, TL-10, SB-02, SB-06.
"""
from __future__ import annotations

import json
import os


def _build_system_prompt(recipe: dict) -> str:
    """Build a system prompt from recipe structure only — no document content (SB-06)."""
    options_lines = "\n".join(
        f"  {o['option_key']}: one of {o['allowed_values']}"
        for o in recipe.get("options", [])
    )
    # placeholder_map keys are UPPER_CASE; instruct Claude to return LOWERCASE keys
    placeholder_keys_lower = [k.lower() for k in recipe.get("placeholder_map", {}).keys()]
    return (
        "You are a contract request parser. Given a plain-text contract description, "
        "extract structured fields and return ONLY a valid JSON object — no prose, "
        "no markdown, no code fences.\n\n"
        "Available options (use EXACT values only — do not invent new ones):\n"
        f"{options_lines}\n\n"
        "Placeholder fields to extract (use lowercase keys; use empty string if unknown):\n"
        f"  {placeholder_keys_lower}\n\n"
        "Return format (JSON only):\n"
        '{"options": {"tier": "...", "channel": "...", ...}, '
        '"placeholder_values": {"customer_name": "...", ...}}\n\n'
        "Rules:\n"
        "- Option values MUST be from the allowed lists above or empty string.\n"
        "- Placeholder values are free-form strings or empty string.\n"
        "- Never include document content, PII beyond what is stated, or extra keys."
    )


def interpret_request(description: str, recipe: dict) -> dict:
    """Call Claude API to interpret a plain-text description into structured fields.

    Returns a partial dict: {"options": {...}, "placeholder_values": {...}}.
    Returns {} on any error or missing API key (graceful degradation — TL-10).
    Never raises an exception.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {}

    try:
        import anthropic  # lazy import so module loads without SDK if key absent

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=_build_system_prompt(recipe),
            messages=[{"role": "user", "content": description}],
        )
        text = message.content[0].text.strip()
        result = json.loads(text)

        # Sanitise: remove invalid option values (only keep values from allowed_values)
        for opt in recipe.get("options", []):
            key = opt["option_key"]
            val = result.get("options", {}).get(key, "")
            if val and val not in opt["allowed_values"]:
                result.setdefault("options", {})[key] = ""

        return result

    except Exception:
        return {}
