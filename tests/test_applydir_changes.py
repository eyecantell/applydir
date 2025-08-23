import pytest
import logging
import json
from pathlib import Path
from prepdir import configure_logging
from applydir.applydir_changes import ApplydirChanges, FileEntry
from applydir.applydir_file_change import ApplydirFileChange, ActionType
from applydir.applydir_error import ApplydirError, ErrorType, ErrorSeverity
from pydantic import ValidationError

# Set up logging for tests
logger = logging.getLogger("applydir_test")
configure_logging(logger, level=logging.DEBUG)
logging.getLogger("applydir").setLevel(logging.DEBUG)

# Configuration matching config.yaml
TEST_ASCII_CONFIG = {
    "validation": {
        "non_ascii": {
            "default": "warning",
            "rules": [
                {"extensions": [".py", ".js"], "action": "error"},
                {"extensions": [".md", ".markdown"], "action": "ignore"},
                {"extensions": [".json", ".yaml"], "action": "warning"},
            ],
        }
    }
}


def test_valid_changes():
    """Test valid JSON input with file, action, and changes."""
    changes_json = [
        {
            "file": "src/main.py",
            "action": "replace_lines",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    changes = ApplydirChanges(file_entries=changes_json)
    errors = changes.validate_changes(base_dir=str(Path.cwd()))
    assert len(errors) == 0
    assert changes.file_entries[0].action == "replace_lines"
    logger.debug(f"Valid changes: {changes}")


def test_multiple_changes_per_file():
    """Test valid JSON input with multiple changes for a single file."""
    changes_json = [
        {
            "file": "src/main.py",
            "action": "replace_lines",
            "changes": [
                {"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]},
                {"original_lines": ["print('Another change')"], "changed_lines": ["print('Good change!')"]},
            ],
        }
    ]
    changes = ApplydirChanges(file_entries=changes_json)
    errors = changes.validate_changes(base_dir=str(Path.cwd()))
    assert len(errors) == 0
    assert len(changes.file_entries[0].changes) == 2
    assert changes.file_entries[0].file == "src/main.py"
    assert changes.file_entries[0].action == "replace_lines"
    assert changes.file_entries[0].changes[0]["original_lines"] == ["print('Hello')"]
    assert changes.file_entries[0].changes[0]["changed_lines"] == ["print('Hello World')"]
    assert changes.file_entries[0].changes[1]["original_lines"] == ["print('Another change')"]
    assert changes.file_entries[0].changes[1]["changed_lines"] == ["print('Good change!')"]
    logger.debug(f"Multiple changes: {changes}")


def test_empty_file_entries_array():
    """Test empty file_entries array raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(file_entries=[])
    logger.debug(f"Validation error for empty file_entries: {exc_info.value}")
    assert "JSON must contain a non-empty array of file entries" in str(exc_info.value)


def test_invalid_file_change():
    """Test invalid ApplydirFileChange produces errors."""
    changes_json = [
        {
            "file": "src/main.py",
            "action": "replace_lines",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello 😊')"]}],
        }
    ]
    changes = ApplydirChanges(file_entries=changes_json)
    errors = changes.validate_changes(
        base_dir=str(Path.cwd()), config={"validation": {"non_ascii": {"default": "error"}}}
    )
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.NON_ASCII_CHARS
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Non-ASCII characters found in changed_lines"
    assert errors[0].details == {"line": "print('Hello 😊')", "line_number": 1}
    logger.debug(f"Invalid change: {errors[0]}")


def test_path_outside_base_dir():
    """Test file path outside base_dir produces FILE_PATH error."""
    changes_json = [
        {
            "file": "../outside.py",
            "action": "create_file",
            "changes": [{"original_lines": [], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    changes = ApplydirChanges(file_entries=changes_json)
    errors = changes.validate_changes(base_dir=str(Path.cwd()))
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_PATH
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "File path is outside project directory"
    logger.debug(f"Path outside base_dir error: {errors[0]}")


def test_non_existent_file_no_error():
    """Test non-existent file does not produce error (existence checks moved to applicator)."""
    changes_json = [
        {
            "file": "src/non_existent.py",
            "action": "replace_lines",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    changes = ApplydirChanges(file_entries=changes_json)
    errors = changes.validate_changes(base_dir=str(Path.cwd()))
    assert len(errors) == 0
    logger.debug("Non-existent file: no error in validation")


def test_invalid_action():
    """Test invalid action raises ValidationError."""
    changes_json = [
        {
            "file": "src/main.py",
            "action": "invalid_action",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(file_entries=changes_json)
    logger.debug(f"Validation error for invalid action: {exc_info.value}")
    assert "Invalid action: invalid_action" in str(exc_info.value)


def test_extra_fields_ignored():
    """Test extra fields are ignored."""
    changes_json = [
        {
            "file": "src/main.py",
            "action": "replace_lines",
            "extra_field": "ignored",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    changes = ApplydirChanges(file_entries=changes_json)
    errors = changes.validate_changes(base_dir=str(Path.cwd()))
    assert len(errors) == 0
    logger.debug("Extra fields ignored")


def test_changes_for_delete_ignored():
    """Test changes for delete_file are ignored."""
    changes_json = [
        {
            "file": "src/old.py",
            "action": "delete_file",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    changes = ApplydirChanges(file_entries=changes_json)
    errors = changes.validate_changes(base_dir=str(Path.cwd()))
    assert len(errors) == 1
    assert errors[0].severity == ErrorSeverity.WARNING
    logger.debug("Changes for delete_file ignored")


def test_invalid_change_type():
    """Test invalid change type raises ValidationError."""
    changes_json = [{"file": "src/main.py", "action": "replace_lines", "changes": "invalid"}]
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(file_entries=changes_json)
    logger.debug(f"Validation error for invalid change type: {exc_info.value}")
    assert "Input should be a valid list" in str(exc_info.value)


def test_empty_original_lines():
    """Test empty original_lines for replace_lines produces ORIG_LINES_EMPTY error."""
    changes_json = [
        {
            "file": "src/main.py",
            "action": "replace_lines",
            "changes": [{"original_lines": [], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    changes = ApplydirChanges(file_entries=changes_json)
    errors = changes.validate_changes(base_dir=str(Path.cwd()))
    error_messages = [e.message for e in errors]
    logger.debug(f"Empty original_lines error: {error_messages}")
    assert any("Empty original_lines not allowed for replace_lines" in msg for msg in error_messages)


def test_applydir_file_change_creation():
    """Test creation of ApplydirFileChange objects during validation."""
    changes_json = [
        {
            "file": "src/main.py",
            "action": "replace_lines",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    changes = ApplydirChanges(file_entries=changes_json)
    errors = changes.validate_changes(base_dir=str(Path.cwd()))
    assert len(errors) == 0
    file_entry = changes.file_entries[0]
    change_obj = ApplydirFileChange(
        file_path=Path(file_entry.file),
        original_lines=file_entry.changes[0]["original_lines"],
        changed_lines=file_entry.changes[0]["changed_lines"],
        action=ActionType.REPLACE_LINES,
    )
    errors = change_obj.validate_change()
    assert len(errors) == 0
    assert change_obj.action == ActionType.REPLACE_LINES
    logger.debug(f"ApplydirFileChange created: {change_obj}")


def test_missing_file_key():
    """Test missing file key raises ValidationError."""
    changes_json = [{"changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}]}]
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(file_entries=changes_json)
    logger.debug(f"Validation error for missing file key: {exc_info.value}")
    assert "Field required" in str(exc_info.value)


def test_empty_changes_array():
    """Test empty changes array reports errors."""
    changes_json = [{"file": "src/main.py", "action": "replace_lines", "changes": []}]

    changes = ApplydirChanges(file_entries=changes_json)
    print(f"changes is {changes}")
    errors = changes.validate_changes(base_dir=str(Path.cwd()))
    print(f"errors is {errors}")
    assert len(errors) == 2
    assert any(ErrorType.ORIG_LINES_EMPTY == err.error_type for err in errors)
    assert any(ErrorType.CHANGED_LINES_EMPTY == err.error_type for err in errors)
    logger.debug(f"Valid changes: {changes}")


def test_empty_file_entry():
    """Test empty file entry dictionary raises ValidationError."""
    changes_json = [{}]
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(file_entries=changes_json)
    logger.debug(f"Validation error for empty file entry: {exc_info.value}")
    assert "Field required" in str(exc_info.value)


def test_multiple_errors():
    """Test multiple validation errors in one JSON input."""
    changes_json = [
        {
            "file": "src/main.py",
            "action": "replace_lines",
            "changes": [{"original_lines": [], "changed_lines": ["print('Hello 😊')"]}],  # Empty original_lines
        },
        {
            "file": "src/new.py",
            "action": "create_file",
            "changes": [
                {"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}
            ],  # Non-empty original_lines
        },
    ]
    changes = ApplydirChanges(file_entries=changes_json)
    errors = changes.validate_changes(
        base_dir=str(Path.cwd()), config={"validation": {"non_ascii": {"default": "error"}}}
    )
    error_messages = [e.message for e in errors]
    logger.debug(f"Multiple errors: {error_messages}")
    assert len(error_messages) >= 3  # Empty original_lines, non-empty original_lines, non-ASCII
    assert any("Empty original_lines not allowed for replace_lines" in msg for msg in error_messages)
    assert any("Non-empty original_lines not allowed for create_file" in msg for msg in error_messages)
    assert any("Non-ASCII characters found in changed_lines" in msg for msg in error_messages)
