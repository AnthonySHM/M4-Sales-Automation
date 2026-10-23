"""
validate_request.py — Validate an assembly request JSON against a recipe.

Exit codes:
  0 — request is valid
  1 — request is invalid (structured errors in JSON stdout)
  2 — external / transient error
  3 — credential / permission error
"""

import argparse
import json
import sys

# Full implementation in Issue #11. This stub validates CLI contract only.


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate an assembly request")
    parser.add_argument("--request", required=True, help="Path to request JSON file")
    parser.add_argument("--recipe", required=True, help="Path to recipe JSON file")
    args = parser.parse_args(argv)

    # Validate files exist
    errors = []
    for label, path in [("request", args.request), ("recipe", args.recipe)]:
        try:
            with open(path) as f:
                json.load(f)
        except FileNotFoundError:
            errors.append({"field": label, "code": "file_not_found",
                           "message": f"{label} file not found: {path}"})
        except json.JSONDecodeError as exc:
            errors.append({"field": label, "code": "invalid_json",
                           "message": f"{label} is not valid JSON: {exc}"})

    if errors:
        print(json.dumps({"valid": False, "errors": errors}))
        sys.exit(1)

    # Stub: passes if files are valid JSON. Full logic in Issue #11.
    result = {
        "valid": True,
        "errors": [],
        "note": "Stub implementation — full logic delivered in Issue #11",
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
