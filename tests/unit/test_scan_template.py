"""
Unit tests for scan_template.py — Issue #8.

All Google Docs API interactions are via injected fakes (no live API calls).
Covers: happy path boundary values, all five issue types, exit codes,
registry cross-check, and safety constraints.

Advances G-01, AD-05, NF-04, SB-05, Architecture §9.
"""

import json
import os
import sys

import pytest

# Resolve the scripts directory regardless of where pytest is invoked from.
SCRIPTS_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "../../.claude/skills/document-assembly/scripts",
    )
)
sys.path.insert(0, SCRIPTS_DIR)

from scan_template import _extract_markers, _find_issues, main, scan  # noqa: E402


# ---------------------------------------------------------------------------
# Fake Google Docs client helpers
# ---------------------------------------------------------------------------


class _FakeExecute:
    def __init__(self, data):
        self._data = data

    def execute(self):
        return self._data


class _FakeDocuments:
    def __init__(self, doc):
        self._doc = doc

    def get(self, documentId):
        return _FakeExecute(self._doc)


class FakeDocsClient:
    """Fake Docs client that returns a hand-crafted document."""

    def __init__(self, doc):
        self._doc = doc

    def documents(self):
        return _FakeDocuments(self._doc)


class _FakeErrorResp:
    def __init__(self, status):
        self.status = status


class _FakeHttpError(Exception):
    def __init__(self, status, message="API error"):
        self.resp = _FakeErrorResp(status)
        super().__init__(message)


class _FakeExecuteError:
    def __init__(self, status):
        self._status = status

    def execute(self):
        raise _FakeHttpError(self._status)


class _FakeDocumentsError:
    def __init__(self, status):
        self._status = status

    def get(self, documentId):
        return _FakeExecuteError(self._status)


class FakeDocsClientError:
    """Fake Docs client that raises an HTTP-like error on execute()."""

    def __init__(self, status):
        self._status = status

    def documents(self):
        return _FakeDocumentsError(self._status)


# ---------------------------------------------------------------------------
# Document builder helpers
# ---------------------------------------------------------------------------


def _make_doc(*texts):
    """Build a minimal Docs API document response from a sequence of text strings."""
    content = []
    index = 1
    for text in texts:
        end = index + len(text)
        content.append(
            {
                "startIndex": index,
                "endIndex": end,
                "paragraph": {
                    "elements": [
                        {
                            "startIndex": index,
                            "endIndex": end,
                            "textRun": {"content": text},
                        }
                    ]
                },
            }
        )
        index = end
    return {"body": {"content": content}}


def _make_balanced_doc(n):
    """Build a doc with exactly n balanced BEGIN/END marker pairs."""
    texts = []
    for i in range(n):
        bid = "blk_{:03d}".format(i)  # blk_000 .. blk_059 — matches ^[a-z0-9_]{3,64}$
        texts.append("[[BLOCK:" + bid + "]]\n")
        texts.append("Body of block {}\n".format(i))
        texts.append("[[/BLOCK:" + bid + "]]\n")
    return _make_doc(*texts)


def _registry_json(block_ids):
    return {
        "family_key": "test_family",
        "blocks": [
            {
                "block_id": bid,
                "label": bid,
                "kind": "section",
                "optional": True,
                "status": "active",
            }
            for bid in block_ids
        ],
    }


def _write_registry(tmp_path, block_ids):
    path = os.path.join(str(tmp_path), "registry.json")
    with open(path, "w") as f:
        json.dump(_registry_json(block_ids), f)
    return path


# ---------------------------------------------------------------------------
# Safety invariant: no live API construction in this file (SB-05, Architecture §9)
# ---------------------------------------------------------------------------


class TestNoLiveApiCalls:
    def test_no_build_call_in_test_file(self):
        """grep equivalent: no live googleapiclient.discovery.build() in this file."""
        with open(__file__) as fh:
            source = fh.read()
        # Construct patterns at runtime so they don't self-match
        dq = "build" + '("docs"'
        sq = "build" + "('docs'"
        assert dq not in source
        assert sq not in source


# ---------------------------------------------------------------------------
# Happy-path boundary values (NF-04: 0, 1, 2, typical=10, max=60)
# ---------------------------------------------------------------------------


class TestHappyPath:
    @pytest.mark.parametrize("n", [0, 1, 2, 10, 60])
    def test_balanced_markers_no_issues(self, n):
        client = FakeDocsClient(_make_balanced_doc(n))
        result = scan(client, "fake_file_id")
        assert result["summary"]["total_markers"] == n
        assert result["summary"]["issue_count"] == 0
        assert result["file_id"] == "fake_file_id"
        for key in (
            "unregistered_markers",
            "registry_without_marker",
            "duplicate_ids",
            "unbalanced_markers",
            "nested_markers",
        ):
            assert result["issues"][key] == []

    @pytest.mark.parametrize("n", [0, 1, 2, 10, 60])
    def test_exit_zero_when_no_issues(self, n):
        client = FakeDocsClient(_make_balanced_doc(n))
        with pytest.raises(SystemExit) as exc_info:
            main(["--file-id", "fake_id"], docs_client=client)
        assert exc_info.value.code == 0

    def test_markers_found_list_correct_length(self):
        client = FakeDocsClient(_make_balanced_doc(5))
        result = scan(client, "fake_id")
        assert len(result["markers_found"]) == 5

    def test_markers_found_has_required_fields(self):
        client = FakeDocsClient(_make_balanced_doc(1))
        result = scan(client, "fake_id")
        marker = result["markers_found"][0]
        assert "block_id" in marker
        assert "start_index" in marker
        assert "end_index" in marker

    def test_result_has_all_required_top_level_keys(self):
        """Architecture §4.2: file_id, markers_found, issues, summary all present."""
        client = FakeDocsClient(_make_balanced_doc(2))
        result = scan(client, "some_id")
        assert set(result.keys()) >= {"file_id", "markers_found", "issues", "summary"}
        assert set(result["issues"].keys()) == {
            "unregistered_markers",
            "registry_without_marker",
            "duplicate_ids",
            "unbalanced_markers",
            "nested_markers",
        }
        assert set(result["summary"].keys()) >= {"total_markers", "issue_count"}

    def test_empty_doc_produces_empty_markers_found(self):
        client = FakeDocsClient(_make_doc())
        result = scan(client, "empty_id")
        assert result["markers_found"] == []
        assert result["summary"]["total_markers"] == 0
        assert result["summary"]["issue_count"] == 0


# ---------------------------------------------------------------------------
# Unbalanced markers
# ---------------------------------------------------------------------------


class TestUnbalancedMarkers:
    def test_begin_without_end(self):
        doc = _make_doc("[[BLOCK:intro]]\nSome text\n")
        result = scan(FakeDocsClient(doc), "fid")
        assert any(m["block_id"] == "intro" for m in result["issues"]["unbalanced_markers"])
        assert result["summary"]["issue_count"] > 0

    def test_end_without_begin(self):
        doc = _make_doc("Some text\n[[/BLOCK:intro]]\n")
        result = scan(FakeDocsClient(doc), "fid")
        assert any(m["block_id"] == "intro" for m in result["issues"]["unbalanced_markers"])
        assert result["summary"]["issue_count"] > 0

    def test_exit_one_when_unbalanced(self):
        doc = _make_doc("[[BLOCK:intro]]\n")
        with pytest.raises(SystemExit) as exc_info:
            main(["--file-id", "fid"], docs_client=FakeDocsClient(doc))
        assert exc_info.value.code == 1

    def test_balanced_pair_not_flagged(self):
        doc = _make_doc("[[BLOCK:intro]]\ntext\n[[/BLOCK:intro]]\n")
        result = scan(FakeDocsClient(doc), "fid")
        assert result["issues"]["unbalanced_markers"] == []


# ---------------------------------------------------------------------------
# Duplicate ids
# ---------------------------------------------------------------------------


class TestDuplicateIds:
    def test_duplicate_begin_detected(self):
        doc = _make_doc(
            "[[BLOCK:intro]]\ntext\n[[/BLOCK:intro]]\n",
            "[[BLOCK:intro]]\ntext2\n[[/BLOCK:intro]]\n",
        )
        result = scan(FakeDocsClient(doc), "fid")
        assert "intro" in result["issues"]["duplicate_ids"]
        assert result["summary"]["issue_count"] > 0

    def test_exit_one_on_duplicate(self):
        doc = _make_doc(
            "[[BLOCK:foo]]\nA\n[[/BLOCK:foo]]\n",
            "[[BLOCK:foo]]\nB\n[[/BLOCK:foo]]\n",
        )
        with pytest.raises(SystemExit) as exc_info:
            main(["--file-id", "fid"], docs_client=FakeDocsClient(doc))
        assert exc_info.value.code == 1

    def test_unique_ids_not_flagged(self):
        doc = _make_doc(
            "[[BLOCK:aaa]]\ntext\n[[/BLOCK:aaa]]\n",
            "[[BLOCK:bbb]]\ntext\n[[/BLOCK:bbb]]\n",
        )
        result = scan(FakeDocsClient(doc), "fid")
        assert result["issues"]["duplicate_ids"] == []


# ---------------------------------------------------------------------------
# Nested markers
# ---------------------------------------------------------------------------


class TestNestedMarkers:
    def test_nested_detected(self):
        doc = _make_doc(
            "[[BLOCK:outer]]\n",
            "[[BLOCK:inner]]\n",
            "[[/BLOCK:inner]]\n",
            "[[/BLOCK:outer]]\n",
        )
        result = scan(FakeDocsClient(doc), "fid")
        nested = result["issues"]["nested_markers"]
        assert len(nested) == 1
        assert nested[0]["outer_block_id"] == "outer"
        assert nested[0]["inner_block_id"] == "inner"
        assert result["summary"]["issue_count"] > 0

    def test_sequential_blocks_not_nested(self):
        doc = _make_doc(
            "[[BLOCK:aaa]]\ntext\n[[/BLOCK:aaa]]\n",
            "[[BLOCK:bbb]]\ntext\n[[/BLOCK:bbb]]\n",
        )
        result = scan(FakeDocsClient(doc), "fid")
        assert result["issues"]["nested_markers"] == []

    def test_exit_one_on_nested(self):
        doc = _make_doc(
            "[[BLOCK:outer]]\n[[BLOCK:inner]]\n[[/BLOCK:inner]]\n[[/BLOCK:outer]]\n",
        )
        with pytest.raises(SystemExit) as exc_info:
            main(["--file-id", "fid"], docs_client=FakeDocsClient(doc))
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Registry cross-check
# ---------------------------------------------------------------------------


class TestRegistryCrossCheck:
    def test_unregistered_marker_detected(self, tmp_path):
        doc = _make_doc("[[BLOCK:intro]]\ntext\n[[/BLOCK:intro]]\n")
        reg_path = _write_registry(tmp_path, ["body"])
        result = scan(FakeDocsClient(doc), "fid", registry_path=reg_path)
        assert "intro" in result["issues"]["unregistered_markers"]
        assert result["summary"]["issue_count"] > 0

    def test_registry_without_marker_detected(self, tmp_path):
        doc = _make_doc("[[BLOCK:intro]]\ntext\n[[/BLOCK:intro]]\n")
        reg_path = _write_registry(tmp_path, ["intro", "body"])
        result = scan(FakeDocsClient(doc), "fid", registry_path=reg_path)
        assert "body" in result["issues"]["registry_without_marker"]
        assert result["summary"]["issue_count"] > 0

    def test_exact_match_no_registry_issues(self, tmp_path):
        doc = _make_doc("[[BLOCK:intro]]\ntext\n[[/BLOCK:intro]]\n")
        reg_path = _write_registry(tmp_path, ["intro"])
        result = scan(FakeDocsClient(doc), "fid", registry_path=reg_path)
        assert result["issues"]["unregistered_markers"] == []
        assert result["issues"]["registry_without_marker"] == []

    def test_no_registry_skips_cross_check(self):
        """When --registry omitted, unregistered/registry_without_marker stay empty (Architecture §4.2)."""
        doc = _make_doc("[[BLOCK:foo]]\ntext\n[[/BLOCK:foo]]\n")
        result = scan(FakeDocsClient(doc), "fid", registry_path=None)
        assert result["issues"]["unregistered_markers"] == []
        assert result["issues"]["registry_without_marker"] == []

    def test_missing_registry_file_exits_one(self):
        doc = _make_doc("[[BLOCK:foo]]\ntext\n[[/BLOCK:foo]]\n")
        with pytest.raises(SystemExit) as exc_info:
            main(
                ["--file-id", "fid", "--registry", "/nonexistent/registry.json"],
                docs_client=FakeDocsClient(doc),
            )
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Exit codes for API errors (Architecture §4)
# ---------------------------------------------------------------------------


class TestExitCodes:
    def test_exit_two_on_500(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["--file-id", "fid"], docs_client=FakeDocsClientError(500))
        assert exc_info.value.code == 2

    def test_exit_two_on_503(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["--file-id", "fid"], docs_client=FakeDocsClientError(503))
        assert exc_info.value.code == 2

    def test_exit_three_on_403(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["--file-id", "fid"], docs_client=FakeDocsClientError(403))
        assert exc_info.value.code == 3

    def test_exit_one_on_missing_file_id_arg(self):
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 1

    def test_stdout_json_on_500(self, capsys):
        with pytest.raises(SystemExit):
            main(["--file-id", "fid"], docs_client=FakeDocsClientError(500))
        data = json.loads(capsys.readouterr().out)
        assert data["error"]["code"] == "api_error"
        assert data["error"]["retryable"] is True

    def test_stdout_json_on_403(self, capsys):
        with pytest.raises(SystemExit):
            main(["--file-id", "fid"], docs_client=FakeDocsClientError(403))
        data = json.loads(capsys.readouterr().out)
        assert data["error"]["code"] == "api_error"
        assert data["error"]["retryable"] is False


# ---------------------------------------------------------------------------
# stdout safety (SB-06)
# ---------------------------------------------------------------------------


class TestOutputSafety:
    def test_stdout_is_valid_json_on_success(self, capsys):
        with pytest.raises(SystemExit):
            main(["--file-id", "fid"], docs_client=FakeDocsClient(_make_balanced_doc(3)))
        data = json.loads(capsys.readouterr().out)
        assert data["file_id"] == "fid"

    def test_stdout_contains_no_doc_body_content(self, capsys):
        """Body text inside blocks must not leak onto stdout (SB-06)."""
        secret = "SENSITIVE_BODY_TEXT_XYZ_12345"
        doc = _make_doc("[[BLOCK:blk]]\n" + secret + "\n[[/BLOCK:blk]]\n")
        with pytest.raises(SystemExit):
            main(["--file-id", "fid"], docs_client=FakeDocsClient(doc))
        assert secret not in capsys.readouterr().out
