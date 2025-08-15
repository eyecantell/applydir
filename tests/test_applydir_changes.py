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
    changes = ApplydirChanges(files=changes_json)
    errors = changes.validate_changes(base_dir=Path.cwd())
    assert len(errors) == 0
    assert changes.files[0].action == "replace_lines"
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
    changes = ApplydirChanges(files=changes_json)
    errors = changes.validate_changes(base_dir=Path.cwd())
    assert len(errors) == 0
    assert len(changes.files[0].changes) == 2
    assert changes.files[0].file == "src/main.py"
    assert changes.files[0].action == "replace_lines"
    assert changes.files[0].changes[0]["original_lines"] == ["print('Hello')"]
    assert changes.files[0].changes[0]["changed_lines"] == ["print('Hello World')"]
    assert changes.files[0].changes[1]["original_lines"] == ["print('Another change')"]
    assert changes.files[0].changes[1]["changed_lines"] == ["print('Good change!')"]
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
    assert "Field required" in str(exc_info.value)

def test_empty_changes_array():
    """Test empty changes array raises ValidationError."""
    changes_json = [{"file": "src/main.py", "action": "replace_lines", "changes": []}]
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(files=changes_json)
    logger.debug(f"Validation error for empty changes: {exc_info.value}")
    assert "Empty changes array for replace_lines or create_file" in str(exc_info.value)

def test_invalid_file_change():
    """Test invalid ApplydirFileChange produces errors."""
    changes_json = [
        {
            "file": "src/main.py",
            "action": "replace_lines",
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
    assert errors[0].change.action == ActionType.REPLACE_LINES
    logger.debug(f"Invalid file change error: {errors[0]}")

def test_changes_serialization():
    """Test JSON serialization of ApplydirChanges."""
    changes_json = [
        {
            "file": "src/main.py",
            "action": "replace_lines",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    changes = ApplydirChanges(files=changes_json, base_dir=Path.cwd())
    serialized = changes.model_dump(mode="json")
    logger.debug(f"Serialized changes: {json.dumps(serialized, indent=4)}")
    assert serialized["files"][0]["file"] == changes_json[0]["file"]
    assert serialized["files"][0]["action"] == "replace_lines"
    assert serialized["files"][0]["changes"][0]["original_lines"] == changes_json[0]["changes"][0]["original_lines"]
    assert serialized["files"][0]["changes"][0]["changed_lines"] == changes_json[0]["changes"][0]["changed_lines"]
    assert serialized["base_dir"] == str(Path.cwd())

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
            "action": "replace_lines",
            "changes": [],
        },
        {
            "file": "src/main.py",
            "action": "replace_lines",
            "changes": [{"original_lines": [], "changed_lines": ["print('Hello 😊')"]}],  # Empty original_lines
        },
        {
            "file": "src/new.py",
            "action": "create_file",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],  # Non-empty original_lines
        },
    ]
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(files=changes_json)
    errors = exc_info.value.errors()
    error_messages = []
    for e in errors:
        if "errors" in e["ctx"]:
            error_messages.extend([err["message"] for err in e["ctx"]["errors"]])
    logger.debug(f"Multiple errors: {error_messages}")
    assert len(error_messages) >= 3  # File path, empty original_lines, non-empty original_lines for create_file
    assert any("File path missing or empty" in msg for msg in error_messages)
    assert any("Empty original_lines not allowed for replace_lines" in msg for msg in error_messages)
    assert any("Non-empty original_lines not allowed for create_file" in msg for msg in error_messages)

def test_valid_new_file_change():
    """Test valid new file change with no original lines."""
    changes_json = [
        {
            "file": "src/new.py",
            "action": "create_file",
            "changes": [{"original_lines": [], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    changes = ApplydirChanges(files=changes_json, base_dir=Path.cwd())
    errors = changes.validate_changes(base_dir=Path.cwd())
    assert len(errors) == 0
    assert changes.files[0].action == "create_file"
    logger.debug("Valid new file change")

def test_invalid_create_file_non_empty_original_lines():
    """Test invalid create_file with non-empty original_lines."""
    changes_json = [
        {
            "file": "src/new.py",
            "action": "create_file",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(files=changes_json, base_dir=Path.cwd())
    error_messages = [e["msg"] for e in exc_info.value.errors()]
    logger.debug(f"Invalid create_file error: {error_messages}")
    assert any("Non-empty original_lines not allowed for create_file" in msg for msg in error_messages)

def test_delete_file_action():
    """Test valid delete_file action with no changes."""
    changes_json = [
        {
            "file": "src/main.py",
            "action": "delete_file",
            "changes": [],  # Ignored for delete_file
        }
    ]
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(files=changes_json, base_dir=Path.cwd())
    error_messages = [e["msg"] for e in exc_info.value.errors()]
    logger.debug(f"Delete file error: {error_messages}")
    assert any("File does not exist for deletion" in msg for msg in error_messages)

def test_empty_original_lines_replace_lines():
    """Test empty original_lines for replace_lines raises ORIG_LINES_EMPTY."""
    changes_json = [
        {
            "file": "src/main.py",
            "action": "replace_lines",
            "changes": [{"original_lines": [], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(files=changes_json, base_dir=Path.cwd())
    error_messages = [e["msg"] for e in exc_info.value.errors()]
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
    changes = ApplydirChanges(files=changes_json, base_dir=Path.cwd())
    file_entry = changes.files[0]
    change_obj = ApplydirFileChange(
        file=file_entry.file,
        original_lines=file_entry.changes[0]["original_lines"],
        changed_lines=file_entry.changes[0]["changed_lines"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    errors = change_obj.validate_change()
    assert len(errors) == 0
    assert change_obj.base_dir == Path.cwd()
    assert change_obj.action == ActionType.REPLACE_LINES
    logger.debug(f"ApplydirFileChange created: {change_obj}")