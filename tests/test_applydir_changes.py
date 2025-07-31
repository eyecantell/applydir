import pytest
import logging
from pathlib import Path
from prepdir import configure_logging
from applydir.applydir_changes import ApplydirChanges
from applydir.applydir_file_change import ApplydirFileChange
from applydir.applydir_error import ApplydirError, ErrorType, ErrorSeverity
from pydantic import ValidationError

# Set up logging for tests
logger = logging.getLogger("applydir_test")
configure_logging(logger, level=logging.DEBUG)


def test_valid_changes():
    """Test valid JSON input with file and changes."""
    changes_json = [
        {
            "file": "src/main.py",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    changes = ApplydirChanges(files=changes_json)
    errors = changes.validate_changes(base_dir=Path.cwd())
    assert len(errors) == 0
    logger.debug(f"Valid changes: {changes}")


def test_multiple_changes_per_file():
    """Test valid JSON input with multiple changes for a single file."""
    changes_json = [
        {
            "file": "src/main.py",
            "changes": [
                {"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]},
                {"original_lines": ["print('Another change')"], "changed_lines": ["print('Good change!')"]},
            ],
        }
    ]
    changes = ApplydirChanges(files=changes_json)
    errors = changes.validate_changes(base_dir=Path.cwd())
    assert len(errors) == 0
    assert len(changes.files[0].changes) == 2
    assert changes.files[0].file == "src/main.py"
    assert changes.files[0].changes[0].file == "src/main.py"
    assert changes.files[0].changes[0].original_lines == ["print('Hello')"]
    assert changes.files[0].changes[0].changed_lines == ["print('Hello World')"]
    assert changes.files[0].changes[1].file == "src/main.py"
    assert changes.files[0].changes[1].original_lines == ["print('Another change')"]
    assert changes.files[0].changes[1].changed_lines == ["print('Good change!')"]
    logger.debug(f"Multiple changes: {changes}")


def test_empty_files_array():
    """Test empty files array raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(files=[])
    logger.debug(f"Validation error for empty files: {exc_info.value}")
    assert "JSON must contain a non-empty array of files" in str(exc_info.value)


def test_missing_file_key():
    """Test missing file key raises ValidationError."""
    changes_json = [{"changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}]}]
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(files=changes_json)
    logger.debug(f"Validation error for missing file key: {exc_info.value}")
    assert "File path missing or empty" in str(exc_info.value)


def test_empty_changes_array():
    """Test empty changes array raises ValidationError."""
    changes_json = [{"file": "src/main.py", "changes": []}]
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(files=changes_json)
    logger.debug(f"Validation error for empty changes: {exc_info.value}")
    assert "Changes array is empty" in str(exc_info.value)


def test_extra_fields_warning():
    """Test extra fields in JSON produce warning."""
    changes_json = [
        {
            "file": "src/main.py",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
            "extra_field": "value",
        }
    ]
    changes = ApplydirChanges(files=changes_json)
    errors = changes.validate_changes(base_dir=Path.cwd())
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.JSON_STRUCTURE
    assert errors[0].severity == ErrorSeverity.WARNING
    assert errors[0].message == "Extra fields found in JSON"
    assert errors[0].details == {"extra_keys": ["extra_field"]}
    logger.debug(f"Extra fields warning: {errors[0]}")


def test_invalid_file_change():
    """Test invalid ApplydirFileChange produces errors."""
    changes_json = [
        {
            "file": "src/main.py",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello 😊')"]}],
        }
    ]
    changes = ApplydirChanges(files=changes_json)
    errors = changes.validate_changes(
        base_dir=Path.cwd(), config_override={"validation": {"non_ascii": {"default": "error"}}}
    )
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.SYNTAX
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Non-ASCII characters found in changed_lines"
    assert errors[0].details == {"line": "print('Hello 😊')", "line_number": 1}
    logger.debug(f"Invalid file change error: {errors[0]}")


def test_changes_serialization():
    """Test JSON serialization of ApplydirChanges."""
    changes_json = [
        {
            "file": "src/main.py",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    changes = ApplydirChanges(files=changes_json)
    serialized = changes.model_dump()
    assert serialized["files"] == changes_json
    logger.debug(f"Serialized changes: {serialized}")


def test_invalid_files_type():
    """Test invalid type for files raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(files="not_a_list")
    logger.debug(f"Validation error for invalid files type: {exc_info.value}")
    assert "Input should be a valid list" in str(exc_info.value)


def test_empty_file_entry():
    """Test empty file entry dictionary raises ValidationError."""
    changes_json = [{}]
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(files=changes_json)
    logger.debug(f"Validation error for empty file entry: {exc_info.value}")
    assert "Field required" in str(exc_info.value)


def test_multiple_errors():
    """Test multiple validation errors in one JSON input."""
    changes_json = [
        {
            "file": "",  # Invalid file path
            "changes": [],
        },
        {
            "file": "src/main.py",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello 😊')"]}],
            "extra_field": "value",
        },
    ]
    changes = ApplydirChanges(files=changes_json)
    errors = changes.validate_changes(
        base_dir=Path.cwd(), config_override={"validation": {"non_ascii": {"default": "error"}}}
    )
    assert len(errors) == 3
    assert any(e.error_type == ErrorType.FILE_PATH and e.message == "File path missing or empty" for e in errors)
    assert any(e.error_type == ErrorType.CHANGES_EMPTY and e.message == "Changes array is empty" for e in errors)
    assert any(
        e.error_type == ErrorType.JSON_STRUCTURE
        and e.severity == ErrorSeverity.WARNING
        and e.message == "Extra fields found in JSON"
        for e in errors
    )
    logger.debug(f"Multiple errors: {[str(e) for e in errors]}")


def test_valid_new_file_change():
    """Test valid new file change with no original lines."""
    changes_json = [
        {"file": "src/new.py", "changes": [{"original_lines": [], "changed_lines": ["print('Hello World')"]}]}
    ]
    changes = ApplydirChanges(files=changes_json)
    errors = changes.validate_changes(base_dir=Path.cwd())
    assert len(errors) == 0
    logger.debug("Valid new file change")
