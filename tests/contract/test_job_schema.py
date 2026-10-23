"""
Contract tests for job.schema.json (AC-5).

Validates:
  - Schema is a valid Draft 2020-12 meta-schema (AC-1)
  - Conforming fixture passes with zero errors (AC-5)
  - Missing required fields are rejected
  - Wrong enum values are rejected
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

VALID_JOB = {
    "job_id": "job_abc123",
    "workspace_id": "ws_main",
    "request_id": "REQ-2026-0001",
    "recipe_version": 1,
    "master_revision_id": "rev_xyz789",
    "resolved_blocks": ["intro_section", "payment_clause"],
    "output_document_id": None,
    "status": "requested",
    "error": None,
    "run_by": "member@example.com",
    "started_at": "2026-10-22T17:00:00Z",
    "finished_at": None,
    "created_at": "2026-10-22T17:00:00Z",
    "updated_at": "2026-10-22T17:00:00Z",
}


# ---------------------------------------------------------------------------
# AC-1 — Schema is a valid Draft 2020-12 meta-schema
# ---------------------------------------------------------------------------

def test_schema_is_valid_draft2020_12():
    """job.schema.json must itself be a valid Draft 2020-12 schema (AC-1)."""
    schema = load_schema("job.schema.json")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        pytest.fail(f"job.schema.json is not a valid Draft 2020-12 schema: {exc}")


# ---------------------------------------------------------------------------
# AC-5 — Conforming fixture passes
# ---------------------------------------------------------------------------

def test_valid_full_instance_status_requested():
    """A job at 'requested' status with null output/error/finished passes (AC-5)."""
    schema = load_schema("job.schema.json")
    assert_valid(schema, VALID_JOB)


def test_valid_full_instance_with_output_and_error():
    """A failed job with a populated error object passes."""
    schema = load_schema("job.schema.json")
    instance = {
        **VALID_JOB,
        "status": "failed",
        "error": {
            "code": "api_error",
            "step": "copy_master",
            "message": "Drive API returned 503",
            "retryable": True,
        },
        "output_document_id": None,
        "finished_at": "2026-10-22T17:02:00Z",
    }
    assert_valid(schema, instance)


def test_valid_approved_job():
    """An approved job with output_document_id set and finished_at set passes."""
    schema = load_schema("job.schema.json")
    instance = {
        **VALID_JOB,
        "status": "approved",
        "output_document_id": "doc_xyz789",
        "finished_at": "2026-10-22T18:00:00Z",
    }
    assert_valid(schema, instance)


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing_field", [
    "job_id", "workspace_id", "request_id", "recipe_version",
    "master_revision_id", "resolved_blocks", "output_document_id",
    "status", "error", "run_by", "started_at", "finished_at",
    "created_at", "updated_at",
])
def test_missing_required_field_fails(missing_field):
    """Missing any required field must fail (AC-5)."""
    schema = load_schema("job.schema.json")
    instance = {k: v for k, v in VALID_JOB.items() if k != missing_field}
    assert_invalid(schema, instance)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", [
    "requested", "validating", "resolving", "building", "verifying",
    "awaiting_review", "approved", "rejected", "failed", "cancelled",
])
def test_all_valid_job_status_values(status):
    """All ten valid job status values are accepted (AC-5)."""
    schema = load_schema("job.schema.json")
    instance = {**VALID_JOB, "status": status}
    assert_valid(schema, instance)


def test_invalid_status_in_flight_fails():
    """status 'in_flight' is not a recognised value and must fail (AC-5)."""
    schema = load_schema("job.schema.json")
    instance = {**VALID_JOB, "status": "in_flight"}
    assert_invalid(schema, instance)


def test_invalid_status_pending_fails():
    """status 'pending' is not in the enum and must fail."""
    schema = load_schema("job.schema.json")
    instance = {**VALID_JOB, "status": "pending"}
    assert_invalid(schema, instance)


@pytest.mark.parametrize("error_code", [
    "unknown_option", "missing_placeholder", "marker_error",
    "master_revision_mismatch", "recipe_conflict", "api_error",
])
def test_all_valid_error_codes(error_code):
    """All six valid error codes are accepted in the error object."""
    schema = load_schema("job.schema.json")
    instance = {
        **VALID_JOB,
        "status": "failed",
        "error": {
            "code": error_code,
            "step": "validate_request",
            "message": "test error",
            "retryable": False,
        },
    }
    assert_valid(schema, instance)


def test_invalid_error_code_fails():
    """An unrecognised error code must fail."""
    schema = load_schema("job.schema.json")
    instance = {
        **VALID_JOB,
        "status": "failed",
        "error": {
            "code": "unknown_error_code",
            "step": "validate_request",
            "message": "test",
            "retryable": False,
        },
    }
    assert_invalid(schema, instance)


@pytest.mark.parametrize("step", [
    "validate_request", "resolve_blocks", "copy_master", "prune_blocks",
    "fill_placeholders", "strip_markers", "verify_output", "submit_for_review",
])
def test_all_valid_error_steps(step):
    """All eight valid error step values are accepted in the error object."""
    schema = load_schema("job.schema.json")
    instance = {
        **VALID_JOB,
        "status": "failed",
        "error": {
            "code": "api_error",
            "step": step,
            "message": "test",
            "retryable": True,
        },
    }
    assert_valid(schema, instance)


def test_invalid_error_step_fails():
    """An unrecognised error step must fail."""
    schema = load_schema("job.schema.json")
    instance = {
        **VALID_JOB,
        "status": "failed",
        "error": {
            "code": "api_error",
            "step": "unknown_step",
            "message": "test",
            "retryable": True,
        },
    }
    assert_invalid(schema, instance)


# ---------------------------------------------------------------------------
# Wrong types
# ---------------------------------------------------------------------------

def test_recipe_version_zero_fails():
    """recipe_version must be >= 1; 0 must fail."""
    schema = load_schema("job.schema.json")
    instance = {**VALID_JOB, "recipe_version": 0}
    assert_invalid(schema, instance)


def test_resolved_blocks_block_id_pattern_enforced():
    """resolved_blocks entries must match the block_id pattern."""
    schema = load_schema("job.schema.json")
    instance = {**VALID_JOB, "resolved_blocks": ["UPPERCASE_BLOCK"]}
    assert_invalid(schema, instance)


def test_started_at_not_datetime_fails():
    """started_at must match the ISO 8601 date-time pattern; an arbitrary string must fail."""
    schema = load_schema("job.schema.json")
    instance = {**VALID_JOB, "started_at": "not-a-date"}
    assert_invalid(schema, instance)


# ---------------------------------------------------------------------------
# additionalProperties rejection
# ---------------------------------------------------------------------------

def test_additional_property_fails():
    """additionalProperties:false — unknown top-level fields must fail."""
    schema = load_schema("job.schema.json")
    instance = {**VALID_JOB, "extra": "oops"}
    assert_invalid(schema, instance)


def test_error_additional_property_fails():
    """additionalProperties:false on error object — unknown fields must fail."""
    schema = load_schema("job.schema.json")
    instance = {
        **VALID_JOB,
        "status": "failed",
        "error": {
            "code": "api_error",
            "step": "copy_master",
            "message": "test",
            "retryable": False,
            "extra_field": "oops",
        },
    }
    assert_invalid(schema, instance)
