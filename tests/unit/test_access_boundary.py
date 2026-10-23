"""
Unit-level access boundary and secret-scan tests (Issue #18).

Verifies without a live Google connection:
  - Git history contains no committed credential files (SB-02)
  - .gitignore blocks all required credential patterns (SB-02)
  - .secrets.baseline exists and detect-secrets finds no new secrets (SB-02)
  - check_drive_api() returns status: fail when a 403-like error is raised (G-12)
  - .pre-commit-config.yaml exists and includes detect-secrets hook (SB-02)

No live Google API calls are made. (SB-05)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

SCRIPTS = os.path.join(
    REPO_ROOT,
    ".claude", "skills", "document-assembly", "scripts",
)
sys.path.insert(0, SCRIPTS)

import doctor


# ---------------------------------------------------------------------------
# Fake Drive client (matches real googleapiclient chain)
# ---------------------------------------------------------------------------

class _FakeDriveClient403:
    """Drive client that raises HttpError-like 403 on any drives().get() call."""

    class _Exc(Exception):
        def __init__(self):
            super().__init__("HttpError 403: the caller does not have permission")

    class _Resource:
        def get(self, **kwargs):
            class _Exec:
                def execute(self):
                    raise _FakeDriveClient403._Exc()
            return _Exec()

    def drives(self):
        return self._Resource()

    def files(self):
        return self._Resource()


# ---------------------------------------------------------------------------
# G-12 unit test: 403 handling in check_drive_api
# ---------------------------------------------------------------------------

class TestDriveApi403Handling:
    def test_check_drive_api_returns_fail_on_403(self):
        """check_drive_api() returns status: fail when a 403-like error is raised. (G-12)"""
        workspace = {
            "shared_drive_id": "some-real-looking-drive-id",
        }
        result = doctor.check_drive_api(_FakeDriveClient403(), workspace)
        assert result["status"] == "fail"
        assert result["name"] == "drive_api"
        assert "403" in result["detail"] or "permission" in result["detail"].lower()

    def test_check_master_template_returns_fail_on_403(self):
        """check_master_template() returns status: fail on a 403-like error. (G-12)"""
        workspace = {
            "pilot_family": {
                "master_template_id": "some-real-looking-doc-id",
                "approved_revision_id": "",
            }
        }
        result = doctor.check_master_template(_FakeDriveClient403(), workspace)
        assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# SB-02: git history contains no credential files
# ---------------------------------------------------------------------------

class TestGitHistorySecrets:
    def test_no_key_files_in_git_history(self):
        """git log --all finds no committed *.key.json, *.pem, or credentials*.json. (SB-02)"""
        result = subprocess.run(
            [
                "git", "log", "--all", "--diff-filter=A",
                "--name-only", "--format=",
                "--", "*.key.json", "*.key", "*.pem", "credentials*.json",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        committed_files = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        assert committed_files == [], (
            f"Credential files were committed to git history (SB-02): {committed_files}"
        )

    def test_no_env_files_in_git_history(self):
        """git log --all finds no committed .env files. (SB-02)"""
        result = subprocess.run(
            [
                "git", "log", "--all", "--diff-filter=A",
                "--name-only", "--format=",
                "--", ".env", "*.env",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        committed_files = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        assert committed_files == [], (
            f".env files were committed to git history (SB-02): {committed_files}"
        )


# ---------------------------------------------------------------------------
# SB-02: .gitignore coverage
# ---------------------------------------------------------------------------

class TestGitignoreCoverage:
    def _check_ignored(self, filename: str) -> bool:
        """Return True if git considers the filename ignored."""
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", filename],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        return result.returncode == 0

    @pytest.mark.parametrize("pattern,example", [
        ("*.key.json", "service-account.key.json"),
        ("*.pem", "private.pem"),
        (".env", ".env"),
        ("credentials*.json", "credentials.json"),
        ("credentials*.json", "credentials_sa.json"),
        ("*-credentials*.json", "project-credentials-prod.json"),
        ("*.p12", "key.p12"),
    ])
    def test_gitignore_blocks_credential_pattern(self, pattern, example, tmp_path):
        """Each sensitive file pattern is blocked by .gitignore. (SB-02)"""
        # Write a temp file matching the pattern inside the repo, check it's ignored
        temp_file = os.path.join(REPO_ROOT, example)
        try:
            with open(temp_file, "w") as f:
                f.write("{}")
            assert self._check_ignored(temp_file), (
                f"File matching pattern {pattern!r} ({example!r}) is NOT ignored "
                f"by .gitignore — add this pattern to fix SB-02."
            )
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


# ---------------------------------------------------------------------------
# SB-02: detect-secrets baseline exists and has no new findings
# ---------------------------------------------------------------------------

class TestSecretsBaseline:
    def test_secrets_baseline_exists(self):
        """A .secrets.baseline file exists at repo root. (SB-02)"""
        baseline_path = os.path.join(REPO_ROOT, ".secrets.baseline")
        assert os.path.isfile(baseline_path), (
            ".secrets.baseline not found. "
            "Run: python -m detect_secrets scan > .secrets.baseline"
        )

    def test_secrets_baseline_is_valid_json(self):
        """The .secrets.baseline file is valid JSON. (SB-02)"""
        baseline_path = os.path.join(REPO_ROOT, ".secrets.baseline")
        if not os.path.isfile(baseline_path):
            pytest.skip(".secrets.baseline not found")
        with open(baseline_path) as f:
            data = json.load(f)
        assert "version" in data
        assert "results" in data

    def test_detect_secrets_scan_exits_zero(self):
        """detect-secrets scan --baseline .secrets.baseline exits 0 (no new secrets). (SB-02)"""
        baseline_path = os.path.join(REPO_ROOT, ".secrets.baseline")
        if not os.path.isfile(baseline_path):
            pytest.skip(".secrets.baseline not found")
        result = subprocess.run(
            [
                sys.executable, "-m", "detect_secrets", "scan",
                "--baseline", baseline_path,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"detect-secrets found new potential secrets (SB-02).\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# SB-02: .pre-commit-config.yaml exists and includes detect-secrets
# ---------------------------------------------------------------------------

class TestPreCommitConfig:
    def test_pre_commit_config_exists(self):
        """.pre-commit-config.yaml exists at repo root. (SB-02)"""
        config_path = os.path.join(REPO_ROOT, ".pre-commit-config.yaml")
        assert os.path.isfile(config_path), (
            ".pre-commit-config.yaml not found. Create it to enforce pre-commit hooks."
        )

    def test_pre_commit_config_includes_detect_secrets(self):
        """.pre-commit-config.yaml references the detect-secrets hook. (SB-02)"""
        import yaml
        config_path = os.path.join(REPO_ROOT, ".pre-commit-config.yaml")
        if not os.path.isfile(config_path):
            pytest.skip(".pre-commit-config.yaml not found")
        with open(config_path) as f:
            config = yaml.safe_load(f)
        hook_ids = []
        for repo in config.get("repos", []):
            for hook in repo.get("hooks", []):
                hook_ids.append(hook.get("id", ""))
        assert "detect-secrets" in hook_ids, (
            "detect-secrets hook not found in .pre-commit-config.yaml (SB-02). "
            f"Found hooks: {hook_ids}"
        )
