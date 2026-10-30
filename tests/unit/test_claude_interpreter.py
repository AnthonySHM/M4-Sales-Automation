"""Unit tests for web.claude_interpreter — Issue #42.

All tests use a fake Anthropic client. No live API calls (SB-05).
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest


def _fake_message(text: str):
    """Build a fake anthropic.types.Message-like object."""
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


RECIPE = {
    "options": [
        {"option_key": "tier", "allowed_values": ["elite", "enterprise", "premium", "strategic"]},
        {"option_key": "channel", "allowed_values": ["resell", "refer"]},
    ],
    "placeholder_map": {
        "CUSTOMER_NAME": "placeholder_values.customer_name",
        "SOW_DATE": "placeholder_values.sow_date",
    },
}

VALID_RESPONSE = json.dumps({
    "options": {"tier": "elite", "channel": "resell"},
    "placeholder_values": {"customer_name": "Acme Corp", "sow_date": "2027-02-01"},
})


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-abc")


def test_valid_description_returns_parsed_dict():
    with patch("anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _fake_message(VALID_RESPONSE)

        from web.claude_interpreter import interpret_request
        result = interpret_request("Elite resell SOW for Acme Corp", RECIPE)

    assert result["options"]["tier"] == "elite"
    assert result["options"]["channel"] == "resell"
    assert result["placeholder_values"]["customer_name"] == "Acme Corp"


def test_invalid_option_value_sanitised_to_empty():
    bad_response = json.dumps({
        "options": {"tier": "gold", "channel": "resell"},  # "gold" is not valid
        "placeholder_values": {"customer_name": "Acme"},
    })
    with patch("anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _fake_message(bad_response)

        from web.claude_interpreter import interpret_request
        result = interpret_request("Some description", RECIPE)

    assert result["options"]["tier"] == ""
    assert result["options"]["channel"] == "resell"


def test_malformed_json_returns_empty_dict():
    with patch("anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _fake_message("This is not JSON")

        from web.claude_interpreter import interpret_request
        result = interpret_request("Some description", RECIPE)

    assert result == {}


def test_missing_api_key_returns_empty_dict(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with patch("anthropic.Anthropic") as mock_cls:
        from web.claude_interpreter import interpret_request
        result = interpret_request("Some description", RECIPE)

    mock_cls.assert_not_called()
    assert result == {}


def test_api_exception_returns_empty_dict():
    with patch("anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API timeout")

        from web.claude_interpreter import interpret_request
        result = interpret_request("Some description", RECIPE)

    assert result == {}
