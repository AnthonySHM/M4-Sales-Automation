"""
Contract tests for request.schema.json (AC-2).

Validates:
  - Schema is a valid Draft 2020-12 meta-schema (AC-1)
  - Conforming fixture passes with zero errors (AC-2)
  - Missing required fields are rejected
  - Wrong types are rejected
  - additionalProperties rejection

No live Google API calls are made anywhere in this file. (SB-02, SB-06)
"""

import json
import pathlib

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

SCHEMAS_DIR = pathlib.Path(__file__).parent.parent.parent / "schemas"


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


def assert_valid(schema: dict, instance: dict) -> None:
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = list(validator.iter_errors(instance))
    assert errors == [], f"Expected 0 validation errors, got: {[str(e) for e in errors]}"


def assert_invalid(schema: dict, instance: dict) -> None:
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = list(validator.iter_errors(instance))
    assert errors, "Expected at least 1 validation error, but instance passed unexpectedly."


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

VALID_REQUEST = {
    "request_id": "REQ-2026-0001",
    "workspace_id": "ws_main",
    "family_key": "family_a",
    "options": {"service_tier": "premium"},
    "placeholder_values": {"PARTY_NAME": "Acme Ltd", "EFFECTIVE_DATE": "2026-11-01"},
    "requested_by": "member@example.com",
}


# ---------------------------------------------------------------------------
# AC-1 — Schema is a valid Draft 2020-12 meta-schema
# ---------------------------------------------------------------------------

def test_schema_is_valid_draft2020_12():
    """request.schema.json must itself be a valid Draft 2020-12 schema (AC-1)."""
    schema = load_schema("request.schema.json")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        pytest.fail(f"request.schema.json is not a valid Draft 2020-12 schema: {exc}")


# ---------------------------------------------------------------------------
# AC-2 — Conforming fixture passes
# ---------------------------------------------------------------------------

def test_valid_full_instance():
    """A fully specified valid request passes with zero errors (AC-2)."""
    schema = load_schema("request.schema.json")
    assert_valid(schema, VALID_REQUEST)


def test_valid_with_raw_input_ref():
    """Optional raw_input_ref field is accepted when present."""
    schema = load_schema("request.schema.json")
    instance = {**VALID_REQUEST, "raw_input_ref": "email://inbox/msg-42"}
    assert_valid(schema, instance)


def test_valid_empty_options_and_placeholders():
    """Empty options and placeholder_values objects are valid."""
    schema = load_schema("request.schema.json")
    instance = {**VALID_REQUEST, "options": {}, "placeholder_values": {}}
    assert_valid(schema, instance)


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing_field", [
    "request_id", "workspace_id", "family_key", "options",
    "placeholder_values", "requested_by",
])
def test_missing_required_field_fails(missing_field):
    """Missing any required field must produce a validation error (AC-2)."""
    schema = load_schema("request.schema.json")
    instance = {k: v for k, v in VALID_REQUEST.items() if k != missing_field}
    assert_invalid(schema, instance)


# ---------------------------------------------------------------------------
# Wrong types
# ---------------------------------------------------------------------------

def test_request_id_wrong_type_fails():
    """request_id must be a string."""
    schema = load_schema("request.schema.json")
    instance = {**VALID_REQUEST, "request_id": 12345}
    assert_invalid(schema, instance)


def test_options_value_wrong_type_fails():
    """options values must be strings, not integers."""
    schema = load_schema("request.schema.json")
    instance = {**VALID_REQUEST, "options": {"tier": 1}}
    assert_invalid(schema, instance)


def test_placeholder_value_wrong_type_fails():
    """placeholder_values values must be strings."""
    schema = load_schema("request.schema.json")
    instance = {**VALID_REQUEST, "placeholder_values": {"NAME": 42}}
    assert_invalid(schema, instance)


# ---------------------------------------------------------------------------
# additionalProperties rejection
# ---------------------------------------------------------------------------

def test_additional_property_fails():
    """additionalProperties:false — unknown fields must fail."""
    schema = load_schema("request.schema.json")
    instance = {**VALID_REQUEST, "unknown_field": "oops"}
    assert_invalid(schema, instance)
