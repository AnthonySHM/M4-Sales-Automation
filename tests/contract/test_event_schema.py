"""
Contract tests for event.schema.json (AC-6).

Validates:
  - Schema is a valid Draft 2020-12 meta-schema (AC-1)
  - Conforming fixture passes with zero errors (AC-6); includes event_id, workspace_id,
    job_id, sequence, event_type, from, to, actor, occurred_at, and optional detail
  - Missing required fields are rejected (sequence, from, to are required)
  - detail is optional — omitting it must still pass
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
# Fixture — includes all AC-6 required fields; detail is optional
# ---------------------------------------------------------------------------

VALID_EVENT = {
    "event_id": "evt_001",
    "workspace_id": "ws_main",
    "job_id": "job_abc123",
    "sequence": 1,
    "event_type": "job.awaiting_review",
    "from": "building",
    "to": "awaiting_review",
    "actor": "service",
    "occurred_at": "2026-10-22T17:05:00Z",
    "detail": {"output_document_id": "doc_xyz", "blocks": 14},
}


# ---------------------------------------------------------------------------
# AC-1 — Schema is a valid Draft 2020-12 meta-schema
# ---------------------------------------------------------------------------

def test_schema_is_valid_draft2020_12():
    """event.schema.json must itself be a valid Draft 2020-12 schema (AC-1)."""
    schema = load_schema("event.schema.json")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        pytest.fail(f"event.schema.json is not a valid Draft 2020-12 schema: {exc}")


# ---------------------------------------------------------------------------
# AC-6 — Conforming fixture passes
# ---------------------------------------------------------------------------

def test_valid_full_instance():
    """A fully specified valid event (all AC-6 fields including detail) passes (AC-6)."""
    schema = load_schema("event.schema.json")
    assert_valid(schema, VALID_EVENT)


def test_valid_without_detail():
    """detail is optional — an event without detail must still pass (AC-6)."""
    schema = load_schema("event.schema.json")
    instance = {k: v for k, v in VALID_EVENT.items() if k != "detail"}
    assert_valid(schema, instance)


def test_valid_empty_detail():
    """An event with an empty detail object is valid."""
    schema = load_schema("event.schema.json")
    instance = {**VALID_EVENT, "detail": {}}
    assert_valid(schema, instance)


def test_valid_rich_detail():
    """An event with nested detail fields is valid (object is open-ended)."""
    schema = load_schema("event.schema.json")
    instance = {**VALID_EVENT, "detail": {"blocks": 14, "output_document_id": "doc_abc", "nested": {"key": "val"}}}
    assert_valid(schema, instance)


# ---------------------------------------------------------------------------
# Missing required fields (sequence, from, to are required per AC-6)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing_field", [
    "event_id", "workspace_id", "job_id", "sequence",
    "event_type", "from", "to", "actor", "occurred_at",
])
def test_missing_required_field_fails(missing_field):
    """Missing any required field must fail (AC-6)."""
    schema = load_schema("event.schema.json")
    instance = {k: v for k, v in VALID_EVENT.items() if k != missing_field}
    assert_invalid(schema, instance)


# ---------------------------------------------------------------------------
# Wrong types
# ---------------------------------------------------------------------------

def test_sequence_wrong_type_fails():
    """sequence must be an integer, not a string."""
    schema = load_schema("event.schema.json")
    instance = {**VALID_EVENT, "sequence": "1"}
    assert_invalid(schema, instance)


def test_sequence_zero_fails():
    """sequence must be >= 1; 0 must fail."""
    schema = load_schema("event.schema.json")
    instance = {**VALID_EVENT, "sequence": 0}
    assert_invalid(schema, instance)


def test_from_wrong_type_fails():
    """from must be a string, not a number."""
    schema = load_schema("event.schema.json")
    instance = {**VALID_EVENT, "from": 123}
    assert_invalid(schema, instance)


def test_to_wrong_type_fails():
    """to must be a string, not a number."""
    schema = load_schema("event.schema.json")
    instance = {**VALID_EVENT, "to": 123}
    assert_invalid(schema, instance)


def test_event_id_wrong_type_fails():
    """event_id must be a string, not a number."""
    schema = load_schema("event.schema.json")
    instance = {**VALID_EVENT, "event_id": 1}
    assert_invalid(schema, instance)


def test_actor_wrong_type_fails():
    """actor must be a string."""
    schema = load_schema("event.schema.json")
    instance = {**VALID_EVENT, "actor": 123}
    assert_invalid(schema, instance)


def test_occurred_at_must_be_datetime_format():
    """occurred_at must match the ISO 8601 date-time pattern; an arbitrary string must fail."""
    schema = load_schema("event.schema.json")
    instance = {**VALID_EVENT, "occurred_at": "not-a-datetime"}
    assert_invalid(schema, instance)


def test_detail_must_be_object_not_string():
    """detail must be an object, not a string."""
    schema = load_schema("event.schema.json")
    instance = {**VALID_EVENT, "detail": "some string"}
    assert_invalid(schema, instance)


def test_detail_must_be_object_not_array():
    """detail must be an object, not an array."""
    schema = load_schema("event.schema.json")
    instance = {**VALID_EVENT, "detail": ["a", "b"]}
    assert_invalid(schema, instance)


# ---------------------------------------------------------------------------
# additionalProperties rejection
# ---------------------------------------------------------------------------

def test_additional_property_fails():
    """additionalProperties:false — unknown fields must fail."""
    schema = load_schema("event.schema.json")
    instance = {**VALID_EVENT, "unknown_key": "value"}
    assert_invalid(schema, instance)
