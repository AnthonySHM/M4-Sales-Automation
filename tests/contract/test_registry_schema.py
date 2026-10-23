"""
Contract tests for registry.schema.json (AC-4).

Validates:
  - Schema is a valid Draft 2020-12 meta-schema (AC-1)
  - Conforming fixture passes with zero errors (AC-4)
  - Missing required fields are rejected
  - Wrong enum values are rejected
  - Wrong types are rejected
  - additionalProperties rejection
  - block_id boundary values: 3 chars valid, 64 chars valid, 2 chars invalid, 65 chars invalid
    (NF-04, architecture §9)

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


# ---------------------------------------------------------------------------
# AC-1 — Schema is a valid Draft 2020-12 meta-schema
# ---------------------------------------------------------------------------

def test_schema_is_valid_draft2020_12():
    """registry.schema.json must itself be a valid Draft 2020-12 schema (AC-1)."""
    schema = load_schema("registry.schema.json")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        pytest.fail(f"registry.schema.json is not a valid Draft 2020-12 schema: {exc}")


# ---------------------------------------------------------------------------
# AC-4 — Conforming fixture passes
# ---------------------------------------------------------------------------

def test_valid_full_instance():
    """A fully specified valid registry passes with zero errors (AC-4)."""
    schema = load_schema("registry.schema.json")
    assert_valid(schema, VALID_REGISTRY)


def test_valid_empty_blocks():
    """An empty blocks array is valid (no blocks registered yet)."""
    schema = load_schema("registry.schema.json")
    instance = {"family_key": "fam", "blocks": []}
    assert_valid(schema, instance)


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing_field", ["family_key", "blocks"])
def test_missing_required_top_level_field_fails(missing_field):
    """Missing a required top-level field must fail (AC-4)."""
    schema = load_schema("registry.schema.json")
    instance = {k: v for k, v in VALID_REGISTRY.items() if k != missing_field}
    assert_invalid(schema, instance)


@pytest.mark.parametrize("missing_field", ["block_id", "label", "kind", "optional", "status"])
def test_missing_required_block_field_fails(missing_field):
    """Missing any required block field must fail (AC-4)."""
    schema = load_schema("registry.schema.json")
    block = {
        "block_id": "abc",
        "label": "Test Block",
        "kind": "section",
        "optional": False,
        "status": "active",
    }
    block.pop(missing_field)
    instance = {"family_key": "fam", "blocks": [block]}
    assert_invalid(schema, instance)


# ---------------------------------------------------------------------------
# block_id boundary values (NF-04, architecture §9)
# ---------------------------------------------------------------------------

def test_block_id_exactly_3_chars_valid():
    """block_id of exactly 3 chars is valid (lower boundary)."""
    schema = load_schema("registry.schema.json")
    block = {"block_id": "abc", "label": "l", "kind": "section", "optional": False, "status": "active"}
    assert_valid(schema, {"family_key": "fam", "blocks": [block]})


def test_block_id_exactly_64_chars_valid():
    """block_id of exactly 64 chars is valid (upper boundary)."""
    schema = load_schema("registry.schema.json")
    block_id = "a" * 64
    block = {"block_id": block_id, "label": "l", "kind": "section", "optional": False, "status": "active"}
    assert_valid(schema, {"family_key": "fam", "blocks": [block]})


def test_block_id_2_chars_invalid():
    """block_id of 2 chars is too short — must fail (below lower boundary)."""
    schema = load_schema("registry.schema.json")
    block = {"block_id": "ab", "label": "l", "kind": "section", "optional": False, "status": "active"}
    assert_invalid(schema, {"family_key": "fam", "blocks": [block]})


def test_block_id_65_chars_invalid():
    """block_id of 65 chars is too long — must fail (above upper boundary)."""
    schema = load_schema("registry.schema.json")
    block_id = "a" * 65
    block = {"block_id": block_id, "label": "l", "kind": "section", "optional": False, "status": "active"}
    assert_invalid(schema, {"family_key": "fam", "blocks": [block]})


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["section", "clause", "table", "annex"])
def test_all_valid_kind_values(kind):
    """All four valid block kind values are accepted (AC-4)."""
    schema = load_schema("registry.schema.json")
    block = {"block_id": "abc", "label": "l", "kind": kind, "optional": False, "status": "active"}
    assert_valid(schema, {"family_key": "fam", "blocks": [block]})


def test_invalid_kind_fails():
    """An unrecognised kind value must fail."""
    schema = load_schema("registry.schema.json")
    block = {"block_id": "abc", "label": "l", "kind": "paragraph", "optional": False, "status": "active"}
    assert_invalid(schema, {"family_key": "fam", "blocks": [block]})


@pytest.mark.parametrize("status", ["proposed", "active", "deprecated", "removed"])
def test_all_valid_block_status_values(status):
    """All four valid block status values are accepted (AC-4)."""
    schema = load_schema("registry.schema.json")
    block = {"block_id": "abc", "label": "l", "kind": "section", "optional": False, "status": status}
    assert_valid(schema, {"family_key": "fam", "blocks": [block]})


def test_invalid_block_status_fails():
    """An unrecognised block status must fail."""
    schema = load_schema("registry.schema.json")
    block = {"block_id": "abc", "label": "l", "kind": "section", "optional": False, "status": "unknown"}
    assert_invalid(schema, {"family_key": "fam", "blocks": [block]})


# ---------------------------------------------------------------------------
# Wrong types
# ---------------------------------------------------------------------------

def test_block_id_uppercase_invalid():
    """block_id with uppercase letters must fail (pattern ^[a-z0-9_]{3,64}$)."""
    schema = load_schema("registry.schema.json")
    block = {"block_id": "ABC", "label": "l", "kind": "section", "optional": False, "status": "active"}
    assert_invalid(schema, {"family_key": "fam", "blocks": [block]})


def test_block_id_with_hyphen_invalid():
    """block_id with hyphens must fail (only [a-z0-9_] allowed)."""
    schema = load_schema("registry.schema.json")
    block = {"block_id": "my-block", "label": "l", "kind": "section", "optional": False, "status": "active"}
    assert_invalid(schema, {"family_key": "fam", "blocks": [block]})


def test_optional_wrong_type_fails():
    """optional must be boolean, not a string."""
    schema = load_schema("registry.schema.json")
    block = {"block_id": "abc", "label": "l", "kind": "section", "optional": "true", "status": "active"}
    assert_invalid(schema, {"family_key": "fam", "blocks": [block]})


# ---------------------------------------------------------------------------
# additionalProperties rejection
# ---------------------------------------------------------------------------

def test_additional_property_on_block_fails():
    """additionalProperties:false on block — unknown fields must fail."""
    schema = load_schema("registry.schema.json")
    block = {"block_id": "abc", "label": "l", "kind": "section", "optional": False, "status": "active", "extra": "x"}
    assert_invalid(schema, {"family_key": "fam", "blocks": [block]})


def test_additional_property_on_top_level_fails():
    """additionalProperties:false at top level — unknown fields must fail."""
    schema = load_schema("registry.schema.json")
    instance = {**VALID_REGISTRY, "extra": "x"}
    assert_invalid(schema, instance)
