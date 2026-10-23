"""
validate_request.py — Validate an assembly request JSON against a recipe.

Checks performed (in order, all errors collected before returning):
  1. Files exist and are valid JSON.
  2. family_key matches between request and recipe.
  3. All required recipe options are present in request.options.
  4. No unknown options appear in request.options (AD-06 hard-fail).
  5. Each option value is in the recipe's allowed_values list.
  6. All keys in recipe.placeholder_map are present in request.placeholder_values.

Exit codes:
  0 — request is valid
  1 — validation error, file error, or bad/missing CLI args
  2 — external / transient error (reserved; not raised here)
  3 — credential / permission error (reserved; not raised here)

Advances G-02, G-03, AD-06. Full implementation for Issue #11.
"""

import argparse
import json
import sys


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({"error": {"code": "missing_argument", "message": message}}))
        sys.exit(1)


def validate(request: dict, recipe: dict) -> list:
    """Cross-validate request against recipe. Returns list of error dicts.

    Each error: {"field": str, "code": str, "message": str}
    An empty list means the request is valid.
    """
    errors = []

    # Check 1: family_key match
    req_family = request.get("family_key", "")
    rec_family = recipe.get("family_key", "")
    if req_family != rec_family:
        errors.append(
            {
                "field": "family_key",
                "code": "family_key_mismatch",
                "message": (
                    f"request family_key '{req_family}' does not match "
                    f"recipe family_key '{rec_family}'"
                ),
            }
        )

    # Build option schema lookup: option_key -> {allowed_values, required}
    recipe_options = {
        opt["option_key"]: opt for opt in recipe.get("options", [])
    }
    request_options = request.get("options", {})

    # Check 2: missing required options
    for opt_key, opt_def in recipe_options.items():
        if opt_def.get("required", False) and opt_key not in request_options:
            errors.append(
                {
                    "field": f"options.{opt_key}",
                    "code": "missing_required_option",
                    "message": f"required option '{opt_key}' is missing from request",
                }
            )

    # Check 3: unknown options (hard-fail per AD-06)
    for opt_key in request_options:
        if opt_key not in recipe_options:
            errors.append(
                {
                    "field": f"options.{opt_key}",
                    "code": "unknown_option",
                    "message": f"option '{opt_key}' is not defined in recipe",
                }
            )

    # Check 4: invalid option values
    for opt_key, opt_value in request_options.items():
        if opt_key in recipe_options:
            allowed = recipe_options[opt_key].get("allowed_values", [])
            if allowed and opt_value not in allowed:
                errors.append(
                    {
                        "field": f"options.{opt_key}",
                        "code": "invalid_option_value",
                        "message": (
                            f"value '{opt_value}' for option '{opt_key}' is not in "
                            f"allowed_values {allowed}"
                        ),
                    }
                )

    # Check 5: missing placeholder values
    placeholder_map = recipe.get("placeholder_map", {})
    placeholder_values = request.get("placeholder_values", {})
    for ph_key in placeholder_map:
        if ph_key not in placeholder_values:
            errors.append(
                {
                    "field": f"placeholder_values.{ph_key}",
                    "code": "missing_placeholder",
                    "message": f"required placeholder '{ph_key}' is missing from request",
                }
            )

    return errors


def main(argv=None):
    parser = _Parser(description="Validate an assembly request")
    parser.add_argument("--request", required=True, help="Path to request JSON file")
    parser.add_argument("--recipe", required=True, help="Path to recipe JSON file")
    args = parser.parse_args(argv)

    # Load files
    file_errors = []
    request_data = None
    recipe_data = None

    for label, path in [("request", args.request), ("recipe", args.recipe)]:
        try:
            with open(path) as f:
                data = json.load(f)
            if label == "request":
                request_data = data
            else:
                recipe_data = data
        except FileNotFoundError:
            file_errors.append(
                {
                    "field": label,
                    "code": "file_not_found",
                    "message": f"{label} file not found: {path}",
                }
            )
        except json.JSONDecodeError as exc:
            file_errors.append(
                {
                    "field": label,
                    "code": "invalid_json",
                    "message": f"{label} is not valid JSON: {exc}",
                }
            )

    if file_errors:
        print(json.dumps({"valid": False, "errors": file_errors}))
        sys.exit(1)

    errors = validate(request_data, recipe_data)

    if errors:
        print(json.dumps({"valid": False, "errors": errors}))
        sys.exit(1)

    print(json.dumps({"valid": True, "errors": []}))
    sys.exit(0)


if __name__ == "__main__":
    main()
