"""
Golden-set dry-run tests — G-05 correct block selection (Issue #16).
No live API calls. Runs assemble.py --dry-run and compares resolved_blocks
to the stored expected lists.
"""
from __future__ import annotations
import json
import pathlib
import subprocess
import sys
import pytest

ROOT = pathlib.Path(__file__).parent.parent.parent
REQUESTS_DIR = ROOT / "tests" / "golden" / "requests"
EXPECTED_DIR = ROOT / "tests" / "golden" / "expected"
RECIPE = ROOT / "config" / "recipes" / "mss_sow_v1.json"
ASSEMBLE = ROOT / ".claude" / "skills" / "document-assembly" / "scripts" / "assemble.py"
VALIDATE = ROOT / ".claude" / "skills" / "document-assembly" / "scripts" / "validate_request.py"


def _valid_profiles():
    """Return (stem, request_path, expected_path) for all valid profiles."""
    profiles = []
    for req in sorted(REQUESTS_DIR.glob("mss_sow_*.json")):
        if "failure" in req.stem:
            continue
        exp = EXPECTED_DIR / req.name
        if exp.exists():
            profiles.append(pytest.param(req.stem, req, exp, id=req.stem))
    return profiles


@pytest.mark.parametrize("stem,req_path,exp_path", _valid_profiles())
def test_dry_run_resolved_blocks(stem, req_path, exp_path):
    """G-05: dry-run resolved_blocks matches stored expected list for each profile."""
    # assemble.py derives the recipe from workspace.yaml — no --recipe arg needed.
    # cwd=ROOT so that the default --workspace config/workspace.yaml resolves correctly.
    result = subprocess.run(
        [sys.executable, str(ASSEMBLE), "--request", str(req_path), "--dry-run"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert result.returncode == 0, f"assemble.py --dry-run failed:\n{result.stdout}\n{result.stderr}"

    # Parse events from stdout (newline-delimited JSON)
    events = [json.loads(line) for line in result.stdout.strip().splitlines() if line.strip()]
    dry_run_event = next((e for e in events if e.get("event") == "dry_run_complete"), None)
    assert dry_run_event is not None, f"No dry_run_complete event found in: {result.stdout}"

    got = sorted(dry_run_event["detail"]["resolved_blocks"])
    expected = sorted(json.loads(exp_path.read_text())["resolved_blocks"])
    assert got == expected, f"Block mismatch for {stem}:\n  got:      {got}\n  expected: {expected}"


def test_failure_path_validate_request_exits_1():
    """G-10: failure-path profile with invalid option is rejected by validate_request.py (exit 1)."""
    req = REQUESTS_DIR / "mss_sow_failure_invalid_tier.json"
    result = subprocess.run(
        [sys.executable, str(VALIDATE), "--request", str(req), "--recipe", str(RECIPE)],
        capture_output=True, text=True,
    )
    assert result.returncode == 1, f"Expected exit 1 for invalid request, got {result.returncode}"
    output = json.loads(result.stdout)
    assert output["valid"] is False
    assert any(e["code"] == "invalid_option_value" for e in output["errors"])


def test_failure_path_assemble_dryrun_no_tier_blocks():
    """G-10: assemble.py --dry-run with an unrecognised tier produces no tier-specific blocks.

    validate_request.py is the authoritative rejection gate (exit 1).
    assemble.py's resolve_blocks() silently ignores unmatched option values, so the
    dry-run still exits 0 but the resolved block list contains only channel blocks
    (partner_logo for channel=resell), confirming that no tier content is selected
    for an invalid tier.  The production gate is validate_request.py (tested above).
    """
    req = REQUESTS_DIR / "mss_sow_failure_invalid_tier.json"
    result = subprocess.run(
        [sys.executable, str(ASSEMBLE), "--request", str(req), "--dry-run"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert result.returncode == 0, f"Unexpected non-zero exit: {result.returncode}\n{result.stderr}"

    events = [json.loads(line) for line in result.stdout.strip().splitlines() if line.strip()]
    dry_run_event = next((e for e in events if e.get("event") == "dry_run_complete"), None)
    assert dry_run_event is not None, f"No dry_run_complete event in: {result.stdout}"

    resolved = dry_run_event["detail"]["resolved_blocks"]
    # No tier-specific blocks should be present (tier "ultra" matches no tier rule)
    tier_blocks = [b for b in resolved if b.startswith("service_desc_") or
                   b.startswith("mdr_") or b.startswith("fees_table_") or
                   b in ("bench_ndr", "bench_cloud_identity", "isensor")]
    assert tier_blocks == [], (
        f"Unexpected tier-specific blocks for invalid tier 'ultra': {tier_blocks}"
    )
