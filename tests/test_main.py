import pytest
import json
from pathlib import Path
from applydir.main import main
from applydir.applydir_changes import ApplydirChanges
from applydir.applydir_applicator import ApplydirApplicator
from applydir.applydir_error import ApplydirError, ErrorType, ErrorSeverity
import logging
from unittest.mock import patch
from prepdir import configure_logging
import sys

# Set up logging for tests
logger = logging.getLogger("applydir_test")
configure_logging(logger, level=logging.DEBUG)
logging.getLogger("applydir").setLevel(logging.DEBUG)


@pytest.fixture
def setup_logging():
    """Reset logging configuration before each test."""
    logger = logging.getLogger("applydir")
    logger.handlers = []
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def input_json_file(tmp_path):
    """Create a temporary JSON file with valid changes."""
    file_path = tmp_path / "changes.json"
    changes = {
        "file_entries": [
            {
                "file": "main.py",
                "action": "replace_lines",
                "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
            }
        ]
    }
    file_path.write_text(json.dumps(changes))
    return file_path


def test_main_successful_execution(tmp_path, setup_logging, input_json_file, caplog):
    """Test successful execution of main with valid input."""
    caplog.set_level(logging.INFO)
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    with patch.object(ApplydirApplicator, "apply_changes") as mock_apply_changes:
        mock_apply_changes.return_value = [
            ApplydirError(
                change=None,
                error_type=ErrorType.FILE_CHANGES_SUCCESSFUL,
                severity=ErrorSeverity.INFO,
                message="All changes to file applied successfully",
                details={"file": str(file_path), "actions": ["replace_lines"], "change_count": 1},
            )
        ]
        with patch.object(sys, "argv", ["applydir", str(input_json_file), "--base-dir", str(tmp_path)]):
            exit_code = main()
        assert exit_code == 0
        assert "Changes applied successfully" in caplog.text
        assert mock_apply_changes.called


def test_main_invalid_json(tmp_path, setup_logging, caplog):
    """Test main with invalid JSON input file."""
    caplog.set_level(logging.ERROR)
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("not a valid json")
    with patch.object(sys, "argv", ["applydir", str(invalid_file)]):
        exit_code = main()
    assert exit_code == 1
    assert "Failed to read input file" in caplog.text


def test_main_missing_input_file(setup_logging, caplog):
    """Test main with non-existent input file."""
    caplog.set_level(logging.ERROR)
    with patch.object(sys, "argv", ["applydir", "non_existent.json"]):
        exit_code = main()
    assert exit_code == 1
    assert "Failed to read input file" in caplog.text


def test_main_no_allow_file_deletion(tmp_path, input_json_file, setup_logging, caplog):
    """Test main with --no-allow-file-deletion flag."""
    caplog.set_level(logging.INFO)
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    with patch.object(ApplydirApplicator, "apply_changes") as mock_apply_changes:
        mock_apply_changes.return_value = []
        with patch.object(
            sys, "argv", ["applydir", str(input_json_file), "--base-dir", str(tmp_path), "--no-allow-file-deletion"]
        ):
            exit_code = main()
        assert exit_code == 0
        assert "Changes applied successfully" in caplog.text
        assert mock_apply_changes.called


def test_main_non_ascii_action(tmp_path, input_json_file, setup_logging, caplog):
    """Test main with --non-ascii-action flag."""
    caplog.set_level(logging.INFO)
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    with patch.object(ApplydirApplicator, "apply_changes") as mock_apply_changes:
        mock_apply_changes.return_value = []
        with patch.object(
            sys, "argv", ["applydir", str(input_json_file), "--base-dir", str(tmp_path), "--non-ascii-action", "error"]
        ):
            exit_code = main()
        assert exit_code == 0
        assert "Changes applied successfully" in caplog.text
        assert mock_apply_changes.called


def test_main_custom_log_level(tmp_path, input_json_file, setup_logging, caplog):
    """Test main with custom --log-level."""
    caplog.set_level(logging.DEBUG)
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    with patch.object(ApplydirApplicator, "apply_changes") as mock_apply_changes:
        mock_apply_changes.return_value = []
        with patch.object(
            sys, "argv", ["applydir", str(input_json_file), "--base-dir", str(tmp_path), "--log-level", "DEBUG"]
        ):
            exit_code = main()
        assert exit_code == 0
        assert "Changes applied successfully" in caplog.text
        assert mock_apply_changes.called
        assert setup_logging.level == logging.DEBUG


def test_main_validation_errors(tmp_path, input_json_file, setup_logging, caplog):
    """Test main when validation returns errors."""
    caplog.set_level(logging.ERROR)
    with patch.object(ApplydirChanges, "validate_changes") as mock_validate_changes:
        mock_validate_changes.return_value = [
            ApplydirError(
                change=None,
                error_type=ErrorType.JSON_STRUCTURE,
                severity=ErrorSeverity.ERROR,
                message="Invalid JSON structure",
                details={},
            )
        ]
        with patch.object(sys, "argv", ["applydir", str(input_json_file), "--base-dir", str(tmp_path)]):
            exit_code = main()
        assert exit_code == 1
        assert "Invalid JSON structure" in caplog.text
        assert mock_validate_changes.called


def test_main_application_errors(tmp_path, input_json_file, setup_logging, caplog):
    """Test main when apply_changes returns errors."""
    caplog.set_level(logging.ERROR)
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    with patch.object(ApplydirApplicator, "apply_changes") as mock_apply_changes:
        mock_apply_changes.return_value = [
            ApplydirError(
                change=None,
                error_type=ErrorType.FILE_NOT_FOUND,
                severity=ErrorSeverity.ERROR,
                message="File does not exist for deletion",
                details={"file": str(tmp_path / "missing.py")},
            )
        ]
        with patch.object(sys, "argv", ["applydir", str(input_json_file), "--base-dir", str(tmp_path)]):
            exit_code = main()
        assert exit_code == 1
        assert "File does not exist for deletion" in caplog.text
        assert mock_apply_changes.called


def test_main_invalid_log_level(tmp_path, setup_logging, caplog, capsys):
    """Test main with an invalid --log-level argument."""
    caplog.set_level(logging.ERROR)
    with patch.object(sys, "argv", ["applydir", str(tmp_path / "changes.json"), "--log-level", "INVALID"]):
        with pytest.raises(SystemExit):
            main()
        captured = capsys.readouterr()
        assert "invalid choice: 'INVALID'" in captured.err


def test_main_invalid_non_ascii_action(tmp_path, setup_logging, caplog, capsys):
    """Test main with an invalid --non-ascii-action argument."""
    caplog.set_level(logging.ERROR)
    with patch.object(sys, "argv", ["applydir", str(tmp_path / "changes.json"), "--non-ascii-action", "invalid"]):
        with pytest.raises(SystemExit):
            main()
        captured = capsys.readouterr()
        assert "invalid choice: 'invalid'" in captured.err


def test_main_missing_file_entries(tmp_path, setup_logging, caplog):
    """Test main with JSON missing file_entries key."""
    caplog.set_level(logging.ERROR)
    file_path = tmp_path / "changes.json"
    file_path.write_text(json.dumps({}))
    with patch.object(sys, "argv", ["applydir", str(file_path), "--base-dir", str(tmp_path)]):
        exit_code = main()
    assert exit_code == 1
    assert "JSON must contain a non-empty array of file entries" in caplog.text


def test_main_warning_errors(tmp_path, input_json_file, setup_logging, caplog):
    """Test main with warning-level errors from apply_changes."""
    caplog.set_level(logging.WARNING)
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    with patch.object(ApplydirApplicator, "apply_changes") as mock_apply_changes:
        mock_apply_changes.return_value = [
            ApplydirError(
                change=None,
                error_type=ErrorType.NON_ASCII_CHARS,
                severity=ErrorSeverity.WARNING,
                message="Non-ASCII characters found",
                details={"file": str(file_path)},
            )
        ]
        with patch.object(
            sys,
            "argv",
            ["applydir", str(input_json_file), "--base-dir", str(tmp_path), "--non-ascii-action", "warning"],
        ):
            exit_code = main()
        assert exit_code == 1
        assert "Non-ASCII characters found" in caplog.text
        assert mock_apply_changes.called


def test_main_empty_file_entries(tmp_path, setup_logging, caplog):
    """Test main with an empty file_entries array."""
    caplog.set_level(logging.ERROR)
    file_path = tmp_path / "changes.json"
    file_path.write_text(json.dumps({"file_entries": []}))
    with patch.object(sys, "argv", ["applydir", str(file_path), "--base-dir", str(tmp_path)]):
        exit_code = main()
    assert exit_code == 1
    assert "JSON must contain a non-empty array of file entries" in caplog.text


def test_main_mixed_severity_errors(tmp_path, input_json_file, setup_logging, caplog):
    """Test main with mixed severity errors from apply_changes."""
    caplog.set_level(logging.DEBUG)
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    with patch.object(ApplydirApplicator, "apply_changes") as mock_apply_changes:
        mock_apply_changes.return_value = [
            ApplydirError(
                change=None,
                error_type=ErrorType.FILE_CHANGES_SUCCESSFUL,
                severity=ErrorSeverity.INFO,
                message="All changes to file applied successfully",
                details={"file": str(file_path), "actions": ["replace_lines"], "change_count": 1},
            ),
            ApplydirError(
                change=None,
                error_type=ErrorType.NON_ASCII_CHARS,
                severity=ErrorSeverity.WARNING,
                message="Non-ASCII characters found",
                details={"file": str(file_path)},
            ),
            ApplydirError(
                change=None,
                error_type=ErrorType.FILE_NOT_FOUND,
                severity=ErrorSeverity.ERROR,
                message="File does not exist",
                details={"file": str(tmp_path / "missing.py")},
            ),
        ]
        with patch.object(sys, "argv", ["applydir", str(input_json_file), "--base-dir", str(tmp_path)]):
            exit_code = main()
        assert exit_code == 1
        assert "All changes to file applied successfully" in caplog.text
        assert "Non-ASCII characters found" in caplog.text
        assert "File does not exist" in caplog.text
        assert mock_apply_changes.called
