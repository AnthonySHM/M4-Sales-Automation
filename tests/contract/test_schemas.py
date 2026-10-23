"""
Contract tests for all five JSON Schema files.

Validates:
  - Each schema is itself a valid Draft 2020-12 meta-schema (AC-1)
  - Each schema accepts a fully conforming fixture (AC-2 through AC-6)
  - Each schema rejects invalid fixtures: missing required fields, wrong types,
    enum violations, pattern violations, additionalProperties (AC-2 through AC-7)
  - block_id boundary values: 3 chars (valid), 64 chars (valid), 2 chars (invalid),
    65 chars (invalid)  — NF-04, architecture §9

No live Google API calls are made anywhere in this file. (SB-02, SB-06, architecture §9)
"""

import json
import pathlib

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCHEMAS_DIR = pathlib.Path(__file__).parent.parent.parent / "schemas"


def load_schema(name: str) -> dict:
    """Load a schema file from the schemas/ directory."""
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


def assert_valid(schema: dict, instance: dict) -> None:
    """Assert that instance passes validation against schema with zero errors.

    format_checker is passed so that 'format': 'date-time' constraints are
    enforced (jsonschema does not enable format checking by default).
    """
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = list(validator.iter_errors(instance))
    assert errors == [], f"Expected 0 validation errors, got: {[str(e) for e in errors]}"


def assert_invalid(schema: dict, instance: dict) -> None:
    """Assert that instance fails validation against schema with at least one error.

    format_checker is passed so that 'format': 'date-time' constraints are
    enforced (jsonschema does not enable format checking by default).
    """
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = list(validator.iter_errors(instance))
    assert errors, f"Expected at least 1 validation error, but instance passed unexpectedly."


# ---------------------------------------------------------------------------
# AC-1 — All five schemas are valid Draft 2020-12 meta-schemas
# ---------------------------------------------------------------------------

SCHEMA_FILES = [
    "request.schema.json",
    "recipe.schema.json",
    "registry.schema.json",
    "job.schema.json",
    "event.schema.json",
]


@pytest.mark.parametrize("schema_name", SCHEMA_FILES)
def test_schema_is_valid_draft2020_12(schema_name):
    """Each schema file must itself be a valid Draft 2020-12 schema (AC-1)."""
    schema = load_schema(schema_name)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        pytest.fail(f"{schema_name} is not a valid Draft 2020-12 schema: {exc}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_REQUEST = {
    "request_id": "REQ-2026-0001",
    "workspace_id": "ws_main",
    "family_key": "family_a",
    "options": {"service_tier": "premium"},
    "placeholder_values": {"PARTY_NAME": "Acme Ltd", "EFFECTIVE_DATE": "2026-11-01"},
    "requested_by": "member@example.com",
}

VALID_RECIPE = {
    "family_key": "family_a",
    "version": 1,
    "options": [
        {"option_key": "service_tier", "allowed_values": ["standard", "premium"], "required": True}
    ],
    "rules": [
        {"when": {"service_tier": "premium"}, "include": ["sla_annex"], "exclude": []},
        {"when": {"service_tier": "standard"}, "exclude": ["sla_annex"]},
    ],
    "defaults": {"include": ["intro_section", "payment_clause"]},
    "placeholder_map": {"PARTY_NAME": "placeholder_values.PARTY_NAME"},
    "status": "published",
}

VALID_REGISTRY = {
    "family_key": "family_a",
    "blocks": [
        {
            "block_id": "intro_section",
            "label": "Introduction Section",
            "kind": "section",
            "optional": False,
            "status": "active",
        },
        {
            "block_id": "sla_annex",
            "label": "SLA Annex",
            "kind": "annex",
            "optional": True,
            "status": "active",
            "source_ref": "legacy_template_v1.docx",
            "owner": "curator@example.com",
        },
    ],
}

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

VALID_EVENT = {
    "event_id": "evt_001",
    "job_id": "job_abc123",
    "workspace_id": "ws_main",
    "event_type": "job.awaiting_review",
    "occurred_at": "2026-10-22T17:05:00Z",
    "actor": "service",
    "detail": {"output_document_id": "doc_xyz", "blocks": 14},
}


# ---------------------------------------------------------------------------
# AC-2 — request.schema.json
# ---------------------------------------------------------------------------

class TestRequestSchema:
    @pytest.fixture(autouse=True)
    def schema(self):
        self.s = load_schema("request.schema.json")

    def test_valid_full_instance(self):
        """A fully specified valid request passes with zero errors (AC-2)."""
        assert_valid(self.s, VALID_REQUEST)

    def test_valid_with_raw_input_ref(self):
        """Optional raw_input_ref field is accepted when present."""
        instance = {**VALID_REQUEST, "raw_input_ref": "email://inbox/msg-42"}
        assert_valid(self.s, instance)

    def test_valid_empty_options_and_placeholders(self):
        """Empty options and placeholder_values objects are valid."""
        instance = {**VALID_REQUEST, "options": {}, "placeholder_values": {}}
        assert_valid(self.s, instance)

    @pytest.mark.parametrize("missing_field", [
        "request_id", "workspace_id", "family_key", "options",
        "placeholder_values", "requested_by",
    ])
    def test_missing_required_field_fails(self, missing_field):
        """Missing any required field must produce a 'required' error (AC-2)."""
        instance = {k: v for k, v in VALID_REQUEST.items() if k != missing_field}
        assert_invalid(self.s, instance)

    def test_additional_property_fails(self):
        """additionalProperties:false — unknown fields must fail."""
        instance = {**VALID_REQUEST, "unknown_field": "oops"}
        assert_invalid(self.s, instance)

    def test_request_id_wrong_type_fails(self):
        """request_id must be a string."""
        instance = {**VALID_REQUEST, "request_id": 12345}
        assert_invalid(self.s, instance)

    def test_options_value_wrong_type_fails(self):
        """options values must be strings, not integers."""
        instance = {**VALID_REQUEST, "options": {"tier": 1}}
        assert_invalid(self.s, instance)

    def test_placeholder_value_wrong_type_fails(self):
        """placeholder_values values must be strings."""
        instance = {**VALID_REQUEST, "placeholder_values": {"NAME": 42}}
        assert_invalid(self.s, instance)


# ---------------------------------------------------------------------------
# AC-3 — recipe.schema.json
# ---------------------------------------------------------------------------

class TestRecipeSchema:
    @pytest.fixture(autouse=True)
    def schema(self):
        self.s = load_schema("recipe.schema.json")

    def test_valid_full_instance(self):
        """A fully specified valid recipe passes with zero errors (AC-3)."""
        assert_valid(self.s, VALID_RECIPE)

    def test_valid_minimal_instance(self):
        """A minimal recipe with empty arrays and map is valid."""
        instance = {
            "family_key": "fam",
            "version": 1,
            "options": [],
            "rules": [],
            "defaults": {"include": []},
            "placeholder_map": {},
            "status": "draft",
        }
        assert_valid(self.s, instance)

    @pytest.mark.parametrize("missing_field", [
        "family_key", "version", "options", "rules", "defaults",
        "placeholder_map", "status",
    ])
    def test_missing_required_field_fails(self, missing_field):
        """Missing any required field must fail (AC-3)."""
        instance = {k: v for k, v in VALID_RECIPE.items() if k != missing_field}
        assert_invalid(self.s, instance)

    @pytest.mark.parametrize("status", ["draft", "validated", "published", "deprecated"])
    def test_all_valid_status_values(self, status):
        """All four valid recipe status values are accepted (AC-3)."""
        instance = {**VALID_RECIPE, "status": status}
        assert_valid(self.s, instance)

    def test_invalid_status_fails(self):
        """status 'unknown' must fail (AC-3)."""
        instance = {**VALID_RECIPE, "status": "unknown"}
        assert_invalid(self.s, instance)

    def test_status_retired_invalid(self):
        """status 'retired' (old spec) must fail; only 'deprecated' is valid."""
        instance = {**VALID_RECIPE, "status": "retired"}
        assert_invalid(self.s, instance)

    def test_version_zero_fails(self):
        """version must be >= 1; 0 must fail."""
        instance = {**VALID_RECIPE, "version": 0}
        assert_invalid(self.s, instance)

    def test_version_string_fails(self):
        """version must be an integer, not a string."""
        instance = {**VALID_RECIPE, "version": "1"}
        assert_invalid(self.s, instance)

    def test_additional_property_fails(self):
        """additionalProperties:false — unknown top-level fields must fail."""
        instance = {**VALID_RECIPE, "extra": True}
        assert_invalid(self.s, instance)

    def test_rule_without_when_fails(self):
        """A rule missing the 'when' key must fail."""
        instance = {**VALID_RECIPE, "rules": [{"include": ["abc"]}]}
        assert_invalid(self.s, instance)

    def test_rule_with_empty_when_fails(self):
        """A rule with an empty 'when' object must fail (minProperties: 1)."""
        instance = {**VALID_RECIPE, "rules": [{"when": {}}]}
        assert_invalid(self.s, instance)

    def test_option_item_missing_field_fails(self):
        """An option item missing 'required' must fail."""
        instance = {**VALID_RECIPE, "options": [{"option_key": "x", "allowed_values": []}]}
        assert_invalid(self.s, instance)

    def test_rule_include_block_id_pattern_enforced(self):
        """Block IDs in rule include/exclude must match ^[a-z0-9_]{3,64}$."""
        instance = {
            **VALID_RECIPE,
            "rules": [{"when": {"tier": "x"}, "include": ["AB"]}],  # uppercase, too short
        }
        assert_invalid(self.s, instance)


# ---------------------------------------------------------------------------
# AC-4 — registry.schema.json
# ---------------------------------------------------------------------------

class TestRegistrySchema:
    @pytest.fixture(autouse=True)
    def schema(self):
        self.s = load_schema("registry.schema.json")

    def test_valid_full_instance(self):
        """A fully specified valid registry passes with zero errors (AC-4)."""
        assert_valid(self.s, VALID_REGISTRY)

    def test_valid_empty_blocks(self):
        """An empty blocks array is valid (no blocks registered yet)."""
        instance = {"family_key": "fam", "blocks": []}
        assert_valid(self.s, instance)

    @pytest.mark.parametrize("missing_field", ["family_key", "blocks"])
    def test_missing_required_top_level_field_fails(self, missing_field):
        """Missing a required top-level field must fail (AC-4)."""
        instance = {k: v for k, v in VALID_REGISTRY.items() if k != missing_field}
        assert_invalid(self.s, instance)

    @pytest.mark.parametrize("missing_field", ["block_id", "label", "kind", "optional", "status"])
    def test_missing_required_block_field_fails(self, missing_field):
        """Missing any required block field must fail (AC-4)."""
        block = {
            "block_id": "abc",
            "label": "Test Block",
            "kind": "section",
            "optional": False,
            "status": "active",
        }
        block.pop(missing_field)
        instance = {"family_key": "fam", "blocks": [block]}
        assert_invalid(self.s, instance)

    # block_id boundary values (NF-04, architecture §9)
    def test_block_id_exactly_3_chars_valid(self):
        """block_id of exactly 3 chars is valid (lower boundary)."""
        block = {"block_id": "abc", "label": "l", "kind": "section", "optional": False, "status": "active"}
        assert_valid(self.s, {"family_key": "fam", "blocks": [block]})

    def test_block_id_exactly_64_chars_valid(self):
        """block_id of exactly 64 chars is valid (upper boundary)."""
        block_id = "a" * 64
        block = {"block_id": block_id, "label": "l", "kind": "section", "optional": False, "status": "active"}
        assert_valid(self.s, {"family_key": "fam", "blocks": [block]})

    def test_block_id_2_chars_invalid(self):
        """block_id of 2 chars is too short — must fail (below lower boundary)."""
        block = {"block_id": "ab", "label": "l", "kind": "section", "optional": False, "status": "active"}
        assert_invalid(self.s, {"family_key": "fam", "blocks": [block]})

    def test_block_id_65_chars_invalid(self):
        """block_id of 65 chars is too long — must fail (above upper boundary)."""
        block_id = "a" * 65
        block = {"block_id": block_id, "label": "l", "kind": "section", "optional": False, "status": "active"}
        assert_invalid(self.s, {"family_key": "fam", "blocks": [block]})

    def test_block_id_uppercase_invalid(self):
        """block_id with uppercase letters must fail (pattern ^[a-z0-9_]{3,64}$)."""
        block = {"block_id": "ABC", "label": "l", "kind": "section", "optional": False, "status": "active"}
        assert_invalid(self.s, {"family_key": "fam", "blocks": [block]})

    def test_block_id_with_hyphen_invalid(self):
        """block_id with hyphens must fail (only [a-z0-9_] allowed)."""
        block = {"block_id": "my-block", "label": "l", "kind": "section", "optional": False, "status": "active"}
        assert_invalid(self.s, {"family_key": "fam", "blocks": [block]})

    @pytest.mark.parametrize("kind", ["section", "clause", "table", "annex"])
    def test_all_valid_kind_values(self, kind):
        """All four valid block kind values are accepted (AC-4)."""
        block = {"block_id": "abc", "label": "l", "kind": kind, "optional": False, "status": "active"}
        assert_valid(self.s, {"family_key": "fam", "blocks": [block]})

    def test_invalid_kind_fails(self):
        """An unrecognised kind value must fail."""
        block = {"block_id": "abc", "label": "l", "kind": "paragraph", "optional": False, "status": "active"}
        assert_invalid(self.s, {"family_key": "fam", "blocks": [block]})

    @pytest.mark.parametrize("status", ["proposed", "active", "deprecated", "removed"])
    def test_all_valid_block_status_values(self, status):
        """All four valid block status values are accepted (AC-4)."""
        block = {"block_id": "abc", "label": "l", "kind": "section", "optional": False, "status": status}
        assert_valid(self.s, {"family_key": "fam", "blocks": [block]})

    def test_invalid_block_status_fails(self):
        """An unrecognised block status must fail."""
        block = {"block_id": "abc", "label": "l", "kind": "section", "optional": False, "status": "unknown"}
        assert_invalid(self.s, {"family_key": "fam", "blocks": [block]})

    def test_additional_property_on_block_fails(self):
        """additionalProperties:false on block — unknown fields must fail."""
        block = {"block_id": "abc", "label": "l", "kind": "section", "optional": False, "status": "active", "extra": "x"}
        assert_invalid(self.s, {"family_key": "fam", "blocks": [block]})

    def test_additional_property_on_top_level_fails(self):
        """additionalProperties:false at top level — unknown fields must fail."""
        instance = {**VALID_REGISTRY, "extra": "x"}
        assert_invalid(self.s, instance)

    def test_optional_wrong_type_fails(self):
        """optional must be boolean, not a string."""
        block = {"block_id": "abc", "label": "l", "kind": "section", "optional": "true", "status": "active"}
        assert_invalid(self.s, {"family_key": "fam", "blocks": [block]})


# ---------------------------------------------------------------------------
# AC-5 — job.schema.json
# ---------------------------------------------------------------------------

class TestJobSchema:
    @pytest.fixture(autouse=True)
    def schema(self):
        self.s = load_schema("job.schema.json")

    def test_valid_full_instance_status_requested(self):
        """A job at 'requested' status with null output/error/finished passes (AC-5)."""
        assert_valid(self.s, VALID_JOB)

    def test_valid_full_instance_with_output_and_error(self):
        """A failed job with a populated error object passes."""
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
        assert_valid(self.s, instance)

    def test_valid_approved_job(self):
        """An approved job with output_document_id set and finished_at set passes."""
        instance = {
            **VALID_JOB,
            "status": "approved",
            "output_document_id": "doc_xyz789",
            "finished_at": "2026-10-22T18:00:00Z",
        }
        assert_valid(self.s, instance)

    @pytest.mark.parametrize("missing_field", [
        "job_id", "workspace_id", "request_id", "recipe_version",
        "master_revision_id", "resolved_blocks", "output_document_id",
        "status", "error", "run_by", "started_at", "finished_at",
        "created_at", "updated_at",
    ])
    def test_missing_required_field_fails(self, missing_field):
        """Missing any required field must fail (AC-5)."""
        instance = {k: v for k, v in VALID_JOB.items() if k != missing_field}
        assert_invalid(self.s, instance)

    @pytest.mark.parametrize("status", [
        "requested", "validating", "resolving", "building", "verifying",
        "awaiting_review", "approved", "rejected", "failed", "cancelled",
    ])
    def test_all_valid_job_status_values(self, status):
        """All ten valid job status values are accepted (AC-5)."""
        instance = {**VALID_JOB, "status": status}
        assert_valid(self.s, instance)

    def test_invalid_status_in_flight_fails(self):
        """status 'in_flight' is not a recognised value and must fail (AC-5)."""
        instance = {**VALID_JOB, "status": "in_flight"}
        assert_invalid(self.s, instance)

    def test_invalid_status_pending_fails(self):
        """status 'pending' is not in the enum and must fail."""
        instance = {**VALID_JOB, "status": "pending"}
        assert_invalid(self.s, instance)

    @pytest.mark.parametrize("error_code", [
        "unknown_option", "missing_placeholder", "marker_error",
        "master_revision_mismatch", "recipe_conflict", "api_error",
    ])
    def test_all_valid_error_codes(self, error_code):
        """All six valid error codes are accepted in the error object."""
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
        assert_valid(self.s, instance)

    def test_invalid_error_code_fails(self):
        """An unrecognised error code must fail."""
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
        assert_invalid(self.s, instance)

    @pytest.mark.parametrize("step", [
        "validate_request", "resolve_blocks", "copy_master", "prune_blocks",
        "fill_placeholders", "strip_markers", "verify_output", "submit_for_review",
    ])
    def test_all_valid_error_steps(self, step):
        """All eight valid error step values are accepted in the error object."""
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
        assert_valid(self.s, instance)

    def test_invalid_error_step_fails(self):
        """An unrecognised error step must fail."""
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
        assert_invalid(self.s, instance)

    def test_error_additional_property_fails(self):
        """additionalProperties:false on error object — unknown fields must fail."""
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
        assert_invalid(self.s, instance)

    def test_recipe_version_zero_fails(self):
        """recipe_version must be >= 1; 0 must fail."""
        instance = {**VALID_JOB, "recipe_version": 0}
        assert_invalid(self.s, instance)

    def test_resolved_blocks_block_id_pattern_enforced(self):
        """resolved_blocks entries must match the block_id pattern."""
        instance = {**VALID_JOB, "resolved_blocks": ["UPPERCASE_BLOCK"]}
        assert_invalid(self.s, instance)

    def test_additional_property_fails(self):
        """additionalProperties:false — unknown top-level fields must fail."""
        instance = {**VALID_JOB, "extra": "oops"}
        assert_invalid(self.s, instance)

    def test_started_at_not_datetime_fails(self):
        """started_at must match the ISO 8601 date-time pattern; an arbitrary string must fail."""
        instance = {**VALID_JOB, "started_at": "not-a-date"}
        assert_invalid(self.s, instance)


# ---------------------------------------------------------------------------
# AC-6 — event.schema.json
# ---------------------------------------------------------------------------

class TestEventSchema:
    @pytest.fixture(autouse=True)
    def schema(self):
        self.s = load_schema("event.schema.json")

    def test_valid_full_instance(self):
        """A fully specified valid event passes with zero errors (AC-6)."""
        assert_valid(self.s, VALID_EVENT)

    def test_valid_empty_detail(self):
        """An event with an empty detail object is valid."""
        instance = {**VALID_EVENT, "detail": {}}
        assert_valid(self.s, instance)

    def test_valid_rich_detail(self):
        """An event with nested detail fields is valid (object is open-ended)."""
        instance = {**VALID_EVENT, "detail": {"blocks": 14, "output_document_id": "doc_abc", "nested": {"key": "val"}}}
        assert_valid(self.s, instance)

    @pytest.mark.parametrize("missing_field", [
        "event_id", "job_id", "workspace_id", "event_type",
        "occurred_at", "actor", "detail",
    ])
    def test_missing_required_field_fails(self, missing_field):
        """Missing any required field must fail (AC-6)."""
        instance = {k: v for k, v in VALID_EVENT.items() if k != missing_field}
        assert_invalid(self.s, instance)

    def test_additional_property_fails(self):
        """additionalProperties:false — unknown fields must fail."""
        instance = {**VALID_EVENT, "unknown_key": "value"}
        assert_invalid(self.s, instance)

    def test_occurred_at_must_be_datetime_format(self):
        """occurred_at must match the ISO 8601 date-time pattern; an arbitrary string must fail."""
        instance = {**VALID_EVENT, "occurred_at": "not-a-datetime"}
        assert_invalid(self.s, instance)

    def test_event_id_wrong_type_fails(self):
        """event_id must be a string, not a number."""
        instance = {**VALID_EVENT, "event_id": 1}
        assert_invalid(self.s, instance)

    def test_detail_must_be_object_not_string(self):
        """detail must be an object, not a string."""
        instance = {**VALID_EVENT, "detail": "some string"}
        assert_invalid(self.s, instance)

    def test_detail_must_be_object_not_array(self):
        """detail must be an object, not an array."""
        instance = {**VALID_EVENT, "detail": ["a", "b"]}
        assert_invalid(self.s, instance)

    def test_actor_wrong_type_fails(self):
        """actor must be a string."""
        instance = {**VALID_EVENT, "actor": 123}
        assert_invalid(self.s, instance)
