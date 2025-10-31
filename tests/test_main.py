# tests/test_main.py
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import patch

import pytest
from applydir.applydir_applicator import ApplydirApplicator
from applydir.applydir_changes import ApplydirChanges
from applydir.applydir_error import ApplydirError, ErrorSeverity, ErrorType
from applydir.applydir_result import ApplydirResult
from applydir.main import main
from prepdir import configure_logging


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def clean_logger():
    """Reset the applydir logger before every test."""
    log = logging.getLogger("applydir")
    log.handlers.clear()
    log.setLevel(logging.DEBUG)
    configure_logging(log, level=logging.DEBUG)


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    """A temporary directory that contains a dummy file."""
    (tmp_path / "main.py").write_text("print('Hello')\n")
    return tmp_path


@pytest.fixture
def valid_file_entry() -> Dict:
    """A valid file_entry dict for testing."""
    return {
        "file": "main.py",
        "action": "replace_lines",
        "changes": [
            {"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}
        ],
    }


@pytest.fixture
def valid_json(tmp_path: Path, valid_file_entry: Dict) -> Path:
    """Minimal JSON – no commit message."""
    data = {"file_entries": [valid_file_entry]}
    p = tmp_path / "changes.json"
    p.write_text(json.dumps(data))
    return p


@pytest.fixture
def json_with_message(tmp_path: Path, valid_file_entry: Dict) -> Path:
    data = {"message": "fix: greet the world", "file_entries": [valid_file_entry]}
    p = tmp_path / "changes_msg.json"
    p.write_text(json.dumps(data))
    return p


@pytest.fixture
def json_multiline(tmp_path: Path, valid_file_entry: Dict) -> Path:
    data = {
        "message": "feat: add auth\n\n- JWT logic\n- tests",
        "file_entries": [valid_file_entry],
    }
    p = tmp_path / "changes_multi.json"
    p.write_text(json.dumps(data))
    return p


# --------------------------------------------------------------------------- #
# Helper – a realistic successful result
# --------------------------------------------------------------------------- #
def _success(message: Optional[str] = None) -> ApplydirResult:
    return ApplydirResult(
        errors=[
            ApplydirError(
                change=None,
                error_type=ErrorType.FILE_CHANGES_SUCCESSFUL,
                severity=ErrorSeverity.INFO,
                message="All changes to file applied successfully",
                details={"file": "main.py", "actions": ["replace_lines"], "change_count": 1},
            )
        ],
        commit_message=message,
        success=True,
    )


# --------------------------------------------------------------------------- #
# NEW / FIXED TESTS
# --------------------------------------------------------------------------- #
def test_main_success_no_message(base_dir: Path, valid_json: Path, caplog):
    caplog.set_level(logging.INFO)
    with patch.object(ApplydirApplicator, "apply_changes", return_value=_success()):
        with patch.object(sys, "argv", ["applydir", str(valid_json), "--base-dir", str(base_dir)]):
            assert main() == 0
    assert "Changes applied successfully" in caplog.text
    assert "Commit message available" not in caplog.text


def test_main_success_with_message(base_dir: Path, json_with_message: Path, caplog):
    caplog.set_level(logging.INFO)
    with patch.object(
        ApplydirApplicator, "apply_changes", return_value=_success("fix: greet the world")
    ):
        with patch.object(sys, "argv", ["applydir", str(json_with_message), "--base-dir", str(base_dir)]):
            assert main() == 0
    assert "Commit message available: 'fix: greet the world'" in caplog.text


def test_main_success_multiline_message(base_dir: Path, json_multiline: Path, caplog):
    caplog.set_level(logging.INFO)
    msg = "feat: add auth\n\n- JWT logic\n- tests"
    with patch.object(ApplydirApplicator, "apply_changes", return_value=_success(msg)):
        with patch.object(sys, "argv", ["applydir", str(json_multiline), "--base-dir", str(base_dir)]):
            assert main() == 0
    assert f"Commit message available: {msg!r}" in caplog.text


def test_main_invalid_message_empty_string(tmp_path: Path, base_dir: Path, valid_file_entry: Dict, caplog):
    """An empty ``message`` raises the message validator."""
    data = {"message": "", "file_entries": [valid_file_entry]}
    p = tmp_path / "empty_msg.json"
    p.write_text(json.dumps(data))

    caplog.set_level(logging.ERROR)
    with patch.object(sys, "argv", ["applydir", str(p), "--base-dir", str(base_dir)]):
        assert main() == 1
    assert "Invalid JSON structure" in caplog.text
    assert "Commit message must be a non-empty string" in caplog.text


def test_main_invalid_message_whitespace_only(tmp_path: Path, base_dir: Path, valid_file_entry: Dict, caplog):
    data = {"message": " \t\n ", "file_entries": [valid_file_entry]}
    p = tmp_path / "ws_msg.json"
    p.write_text(json.dumps(data))

    caplog.set_level(logging.ERROR)
    with patch.object(sys, "argv", ["applydir", str(p), "--base-dir", str(base_dir)]):
        assert main() == 1
    assert "Invalid JSON structure" in caplog.text
    assert "Commit message must be a non-empty string" in caplog.text


def test_main_missing_file_entries_with_message(tmp_path: Path, base_dir: Path, caplog):
    data = {"message": "some msg"}  # no file_entries
    p = tmp_path / "no_entries.json"
    p.write_text(json.dumps(data))

    caplog.set_level(logging.ERROR)
    with patch.object(sys, "argv", ["applydir", str(p), "--base-dir", str(base_dir)]):
        assert main() == 1
    assert "Invalid JSON structure" in caplog.text
    assert "Field required" in caplog.text


def test_main_application_error_exits_1(base_dir: Path, valid_json: Path, caplog):
    caplog.set_level(logging.ERROR)
    result = ApplydirResult(
        errors=[
            ApplydirError(
                change=None,
                error_type=ErrorType.NO_MATCH,
                severity=ErrorSeverity.ERROR,
                message="No matching lines found",
                details={"file": "main.py"},
            )
        ],
        commit_message="ignored",
        success=False,
    )
    with patch.object(ApplydirApplicator, "apply_changes", return_value=result):
        with patch.object(sys, "argv", ["applydir", str(valid_json), "--base-dir", str(base_dir)]):
            assert main() == 1
    assert "No matching lines found" in caplog.text


def test_main_warning_is_logged_but_successful(base_dir: Path, valid_json: Path, caplog):
    """WARNINGs are logged **and** the run is still considered successful."""
    caplog.set_level(logging.INFO)  # Changed to INFO to capture success log

    result = ApplydirResult(
        errors=[
            ApplydirError(
                change=None,
                error_type=ErrorType.NON_ASCII_CHARS,
                severity=ErrorSeverity.WARNING,
                message="Non-ASCII characters found",
                details={"file": "main.py"},
            ),
            ApplydirError(
                change=None,
                error_type=ErrorType.FILE_CHANGES_SUCCESSFUL,
                severity=ErrorSeverity.INFO,
                message="All changes to file applied successfully",
                details={"file": "main.py", "actions": ["replace_lines"], "change_count": 1},
            ),
        ],
        commit_message=None,
        success=True,
    )

    with patch.object(ApplydirApplicator, "apply_changes", return_value=result):
        with patch.object(sys, "argv", ["applydir", str(valid_json), "--base-dir", str(base_dir)]):
            assert main() == 0
    assert "Non-ASCII characters found" in caplog.text
    assert "Changes applied successfully" in caplog.text


def test_main_invalid_json(tmp_path: Path, caplog):
    p = tmp_path / "bad.json"
    p.write_text("not json")
    caplog.set_level(logging.ERROR)
    with patch.object(sys, "argv", ["applydir", str(p)]):
        assert main() == 1
    assert "Failed to read input file" in caplog.text


def test_main_missing_input_file(caplog):
    caplog.set_level(logging.ERROR)
    with patch.object(sys, "argv", ["applydir", "nonexistent.json"]):
        assert main() == 1
    assert "Failed to read input file" in caplog.text


def test_main_no_allow_file_deletion(base_dir: Path, valid_json: Path, caplog):
    caplog.set_level(logging.INFO)
    with patch.object(ApplydirApplicator, "apply_changes", return_value=_success()):
        with patch.object(
            sys,
            "argv",
            ["applydir", str(valid_json), "--base-dir", str(base_dir), "--no-allow-file-deletion"],
        ):
            assert main() == 0
    assert "Changes applied successfully" in caplog.text


def test_main_non_ascii_action(base_dir: Path, valid_json: Path, caplog):
    caplog.set_level(logging.INFO)
    with patch.object(ApplydirApplicator, "apply_changes", return_value=_success()):
        with patch.object(
            sys,
            "argv",
            ["applydir", str(valid_json), "--base-dir", str(base_dir), "--non-ascii-action", "error"],
        ):
            assert main() == 0
    assert "Changes applied successfully" in caplog.text


def test_main_custom_log_level(base_dir: Path, valid_json: Path, caplog):
    caplog.set_level(logging.DEBUG)
    with patch.object(ApplydirApplicator, "apply_changes", return_value=_success()):
        with patch.object(
            sys,
            "argv",
            ["applydir", str(valid_json), "--base-dir", str(base_dir), "--log-level", "DEBUG"],
        ):
            assert main() == 0
    assert "Changes applied successfully" in caplog.text


def test_main_validation_errors(base_dir: Path, valid_json: Path, caplog):
    caplog.set_level(logging.ERROR)
    with patch.object(
        ApplydirChanges,
        "validate_changes",
        return_value=[
            ApplydirError(
                change=None,
                error_type=ErrorType.JSON_STRUCTURE,
                severity=ErrorSeverity.ERROR,
                message="Invalid JSON structure",
                details={},
            )
        ],
    ):
        with patch.object(sys, "argv", ["applydir", str(valid_json), "--base-dir", str(base_dir)]):
            assert main() == 1
    assert "Invalid JSON structure" in caplog.text


def test_main_invalid_log_level(tmp_path: Path, capsys):
    with patch.object(
        sys, "argv", ["applydir", str(tmp_path / "changes.json"), "--log-level", "BOGUS"]
    ):
        with pytest.raises(SystemExit):
            main()
    assert "invalid choice: 'BOGUS'" in capsys.readouterr().err


def test_main_invalid_non_ascii_action(tmp_path: Path, capsys):
    with patch.object(
        sys, "argv", ["applydir", str(tmp_path / "changes.json"), "--non-ascii-action", "bad"]
    ):
        with pytest.raises(SystemExit):
            main()
    assert "invalid choice: 'bad'" in capsys.readouterr().err


def test_main_missing_file_entries(tmp_path: Path, caplog):
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({}))
    caplog.set_level(logging.ERROR)
    with patch.object(sys, "argv", ["applydir", str(p), "--base-dir", str(tmp_path)]):
        assert main() == 1
    assert "Invalid JSON structure" in caplog.text
    assert "Field required" in caplog.text


def test_main_empty_file_entries(tmp_path: Path, caplog):
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"file_entries": []}))
    caplog.set_level(logging.ERROR)
    with patch.object(sys, "argv", ["applydir", str(p), "--base-dir", str(tmp_path)]):
        assert main() == 1
    assert "Invalid JSON structure" in caplog.text
    assert "JSON must contain a non-empty array of file_entries" in caplog.text