"""
Contract tests for recipe.schema.json (AC-3).

Validates:
  - Schema is a valid Draft 2020-12 meta-schema (AC-1)
  - Conforming fixture passes with zero errors (AC-3)
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


# ---------------------------------------------------------------------------
# AC-1 — Schema is a valid Draft 2020-12 meta-schema
# ---------------------------------------------------------------------------

def test_schema_is_valid_draft2020_12():
    """recipe.schema.json must itself be a valid Draft 2020-12 schema (AC-1)."""
    schema = load_schema("recipe.schema.json")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        pytest.fail(f"recipe.schema.json is not a valid Draft 2020-12 schema: {exc}")


# ---------------------------------------------------------------------------
# AC-3 — Conforming fixture passes
# ---------------------------------------------------------------------------

def test_valid_full_instance():
    """A fully specified valid recipe passes with zero errors (AC-3)."""
    schema = load_schema("recipe.schema.json")
    assert_valid(schema, VALID_RECIPE)


def test_valid_minimal_instance():
    """A minimal recipe with empty arrays and map is valid."""
    schema = load_schema("recipe.schema.json")
    instance = {
        "family_key": "fam",
        "version": 1,
        "options": [],
        "rules": [],
        "defaults": {"include": []},
        "placeholder_map": {},
        "status": "draft",
    }
    assert_valid(schema, instance)


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing_field", [
    "family_key", "version", "options", "rules", "defaults",
    "placeholder_map", "status",
])
def test_missing_required_field_fails(missing_field):
    """Missing any required field must fail (AC-3)."""
    schema = load_schema("recipe.schema.json")
    instance = {k: v for k, v in VALID_RECIPE.items() if k != missing_field}
    assert_invalid(schema, instance)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["draft", "validated", "published", "deprecated"])
def test_all_valid_status_values(status):
    """All four valid recipe status values are accepted (AC-3)."""
    schema = load_schema("recipe.schema.json")
    instance = {**VALID_RECIPE, "status": status}
    assert_valid(schema, instance)


def test_invalid_status_fails():
    """status 'unknown' must fail (AC-3)."""
    schema = load_schema("recipe.schema.json")
    instance = {**VALID_RECIPE, "status": "unknown"}
    assert_invalid(schema, instance)


def test_status_retired_invalid():
    """status 'retired' (old spec) must fail; only 'deprecated' is valid."""
    schema = load_schema("recipe.schema.json")
    instance = {**VALID_RECIPE, "status": "retired"}
    assert_invalid(schema, instance)


# ---------------------------------------------------------------------------
# Wrong types
# ---------------------------------------------------------------------------

def test_version_zero_fails():
    """version must be >= 1; 0 must fail."""
    schema = load_schema("recipe.schema.json")
    instance = {**VALID_RECIPE, "version": 0}
    assert_invalid(schema, instance)


def test_version_string_fails():
    """version must be an integer, not a string."""
    schema = load_schema("recipe.schema.json")
    instance = {**VALID_RECIPE, "version": "1"}
    assert_invalid(schema, instance)


# ---------------------------------------------------------------------------
# additionalProperties rejection
# ---------------------------------------------------------------------------

def test_additional_property_fails():
    """additionalProperties:false — unknown top-level fields must fail."""
    schema = load_schema("recipe.schema.json")
    instance = {**VALID_RECIPE, "extra": True}
    assert_invalid(schema, instance)


def test_rule_without_when_fails():
    """A rule missing the 'when' key must fail."""
    schema = load_schema("recipe.schema.json")
    instance = {**VALID_RECIPE, "rules": [{"include": ["abc"]}]}
    assert_invalid(schema, instance)


def test_rule_with_empty_when_fails():
    """A rule with an empty 'when' object must fail (minProperties: 1)."""
    schema = load_schema("recipe.schema.json")
    instance = {**VALID_RECIPE, "rules": [{"when": {}}]}
    assert_invalid(schema, instance)


def test_option_item_missing_field_fails():
    """An option item missing 'required' must fail."""
    schema = load_schema("recipe.schema.json")
    instance = {**VALID_RECIPE, "options": [{"option_key": "x", "allowed_values": []}]}
    assert_invalid(schema, instance)


def test_rule_include_block_id_pattern_enforced():
    """Block IDs in rule include/exclude must match ^[a-z0-9_]{3,64}$."""
    schema = load_schema("recipe.schema.json")
    instance = {
        **VALID_RECIPE,
        "rules": [{"when": {"tier": "x"}, "include": ["AB"]}],  # uppercase, too short
    }
    assert_invalid(schema, instance)
