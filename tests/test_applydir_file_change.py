import pytest
import logging
from pathlib import Path
from prepdir import configure_logging
from applydir.applydir_file_change import ApplydirFileChange, ActionType
from applydir.applydir_error import ApplydirError, ErrorType, ErrorSeverity
from applydir.applydir_matcher import ApplydirMatcher
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

def test_valid_file_path():
    """Test valid file path."""
    change = ApplydirFileChange(
        file_path=Path("src/main.py"),
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    logger.debug(f"Valid file path: {change.file_path}")
    assert change.file_path == Path("src/main.py")

def test_empty_file_path():
    """Test empty file path raises ValidationError."""
    with pytest.raises(ValueError) as exc_info:
        ApplydirFileChange(
            file_path=Path(""),
            original_lines=["print('Hello')"],
            changed_lines=["print('Hello World')"],
            action=ActionType.REPLACE_LINES,
        )
    logger.debug(f"Validation error for empty path: {exc_info.value}")
    assert "File path must be a valid Path object and non-empty" in str(exc_info.value)

def test_non_ascii_error():
    """Test non-ASCII characters with error config."""
    change = ApplydirFileChange(
        file_path=Path("src/main.py"),
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change(config={"validation": {"non_ascii": {"default": "error"}}})
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.SYNTAX
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Non-ASCII characters found in changed_lines"
    assert errors[0].details == {"line": "print('Hello 😊')", "line_number": 1}
    logger.debug(f"Non-ASCII error: {errors[0]}")

def test_non_ascii_ignore():
    """Test non-ASCII characters with ignore config."""
    change = ApplydirFileChange(
        file_path=Path("src/main.py"),
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change(config={"validation": {"non_ascii": {"default": "ignore"}}})
    assert len(errors) == 0
    logger.debug("Non-ASCII ignored")

def test_non_ascii_rule_override():
    """Test non-ASCII rule override for .py file."""
    config = {
        "validation": {
            "non_ascii": {
                "default": "error",
                "rules": [{"extensions": [".py"], "action": "ignore"}],
            }
        }
    }
    change = ApplydirFileChange(
        file_path=Path("src/main.py"),
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change(config=config)
    assert len(errors) == 0
    logger.debug("Non-ASCII ignored for .py due to rule override")

def test_valid_change_no_original_lines():
    """Test valid change for create_file with empty original_lines."""
    change = ApplydirFileChange(
        file_path=Path("src/new.py"),
        original_lines=[],
        changed_lines=["print('Hello World')"],
        action=ActionType.CREATE_FILE,
    )
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Valid change for create_file with empty original_lines")

def test_non_ascii_py_file_error():
    """Test non-ASCII characters in .py file generates ERROR."""
    change = ApplydirFileChange(
        file_path=Path("src/main.py"),
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change(config=TEST_ASCII_CONFIG)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.SYNTAX
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Non-ASCII characters found in changed_lines"
    assert errors[0].details == {"line": "print('Hello 😊')", "line_number": 1}
    logger.debug(f"Non-ASCII error for .py: {errors[0]}")

def test_non_ascii_js_file_error():
    """Test non-ASCII characters in .js file generates ERROR."""
    change = ApplydirFileChange(
        file_path=Path("src/script.js"),
        original_lines=["console.log('Hello');"],
        changed_lines=["console.log('Hello 😊');"],
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change(config=TEST_ASCII_CONFIG)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.SYNTAX
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Non-ASCII characters found in changed_lines"
    assert errors[0].details == {"line": "console.log('Hello 😊');", "line_number": 1}
    logger.debug(f"Non-ASCII error for .js: {errors[0]}")

def test_non_ascii_md_file_ignore():
    """Test non-ASCII characters in .md file are ignored."""
    change = ApplydirFileChange(
        file_path=Path("src/docs.md"),
        original_lines=["# Original"],
        changed_lines=["Hello 😊"],
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change(config=TEST_ASCII_CONFIG)
    assert len(errors) == 0
    logger.debug("Non-ASCII ignored for .md")

def test_multiple_non_ascii_errors():
    """Test multiple non-ASCII characters in changed_lines generate multiple errors."""
    change = ApplydirFileChange(
        file_path=Path("src/main.py"),
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')", "print('World 😊')"],
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change(config=TEST_ASCII_CONFIG)
    assert len(errors) == 2
    assert errors[0].error_type == ErrorType.SYNTAX
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Non-ASCII characters found in changed_lines"
    assert errors[0].details == {"line": "print('Hello 😊')", "line_number": 1}
    assert errors[1].error_type == ErrorType.SYNTAX
    assert errors[1].severity == ErrorSeverity.ERROR
    assert errors[1].message == "Non-ASCII characters found in changed_lines"
    assert errors[1].details == {"line": "print('World 😊')", "line_number": 2}
    logger.debug(f"Multiple non-ASCII errors: {errors}")

def test_empty_config():
    """Test validation with empty config."""
    change = ApplydirFileChange(
        file_path=Path("src/main.py"),
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change(config={})
    assert len(errors) == 0
    logger.debug("Empty config: no errors")

def test_invalid_action():
    """Test invalid action value raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirFileChange(
            file_path=Path("src/main.py"),
            original_lines=["print('Hello')"],
            changed_lines=["print('Hello World')"],
            action="invalid_action",
        )
    logger.debug(f"Validation error for invalid action: {exc_info.value}")
    assert "Input should be 'replace_lines', 'create_file' or 'delete_file'" in str(exc_info.value)

def test_action_serialization():
    """Test JSON serialization of action field."""
    change = ApplydirFileChange(
        file_path=Path("src/main.py"),
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    change_dict = change.model_dump(mode="json")
    logger.debug(f"Serialized action: {change_dict['action']}")
    assert change_dict["action"] == "replace_lines"

    change = ApplydirFileChange(
        file_path=Path("src/new.py"),
        original_lines=[],
        changed_lines=["print('Hello World')"],
        action=ActionType.CREATE_FILE,
    )
    change_dict = change.model_dump(mode="json")
    logger.debug(f"Serialized action: {change_dict['action']}")
    assert change_dict["action"] == "create_file"

def test_no_match_error_integration():
    """Test ApplydirFileChange with ApplydirMatcher producing NO_MATCH error."""
    change = ApplydirFileChange(
        file_path=Path("src/main.py"),
        original_lines=["print('Unique')"],
        changed_lines=["print('Modified')"],
        action=ActionType.REPLACE_LINES,
    )
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    file_content = ["print('Different')", "print('Other')"]
    result, errors = matcher.match(file_content, change)
    assert isinstance(errors, list)
    assert len(errors) == 1
    logger.debug(f"NO_MATCH error: {errors[0]}")
    assert errors[0].error_type == ErrorType.NO_MATCH
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "No matching lines found"
    assert errors[0].details == {"file": str(change.file_path)}
    assert errors[0].change == change

def test_multiple_matches_error_integration():
    """Test ApplydirFileChange with ApplydirMatcher producing MULTIPLE_MATCHES error."""
    change = ApplydirFileChange(
        file_path=Path("src/main.py"),
        original_lines=["print('Common')"],
        changed_lines=["print('Modified')"],
        action=ActionType.REPLACE_LINES,
    )
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    file_content = ["print('Common')", "print('Other')", "print('Common')"]
    result, errors = matcher.match(file_content, change)
    assert isinstance(errors, list)
    assert len(errors) == 1
    logger.debug(f"MULTIPLE_MATCHES error: {errors[0]}")
    assert errors[0].error_type == ErrorType.MULTIPLE_MATCHES
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Multiple matches found for original_lines"
    assert errors[0].details == {"file": str(change.file_path), "match_count": 2, "match_indices": [0, 2]}
    assert errors[0].change == change

def test_empty_changed_lines_new_file():
    """Test empty changed_lines for new file."""
    change = ApplydirFileChange(
        file_path=Path("src/new.py"),
        original_lines=[],
        changed_lines=[],
        action=ActionType.CREATE_FILE,
    )
    errors = change.validate_change()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.EMPTY_CHANGED_LINES
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Empty changed_lines not allowed for create_file"
    logger.debug("Invalid create_file: empty changed_lines")

def test_action_validation():
    """Test validation for action-specific rules."""
    # Valid: non-empty original_lines, non-empty changed_lines, replace_lines
    change = ApplydirFileChange(
        file_path=Path("src/main.py"),
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Valid replace_lines: non-empty original_lines and changed_lines")

    # Invalid: non-empty original_lines, empty changed_lines, replace_lines
    change = ApplydirFileChange(
        file_path=Path("src/main.py"),
        original_lines=["print('Hello')"],
        changed_lines=[],
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.EMPTY_CHANGED_LINES
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Empty changed_lines not allowed for replace_lines"
    logger.debug(f"Invalid replace_lines: {errors[0]}")

    # Valid: empty original_lines, non-empty changed_lines, create_file
    change = ApplydirFileChange(
        file_path=Path("src/new.py"),
        original_lines=[],
        changed_lines=["print('Hello World')"],
        action=ActionType.CREATE_FILE,
    )
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Valid create_file: empty original_lines, non-empty changed_lines")

    # Invalid: non-empty original_lines, create_file
    change = ApplydirFileChange(
        file_path=Path("src/new.py"),
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.CREATE_FILE,
    )
    errors = change.validate_change()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.ORIG_LINES_NOT_EMPTY
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Non-empty original_lines not allowed for create_file"
    logger.debug(f"Invalid create_file: {errors[0]}")


def test_delete_file_validation():
    """Test validation for delete_file action."""
    # Valid: empty original_lines and changed_lines, delete_file
    change = ApplydirFileChange(
        file_path=Path("src/old.py"),
        original_lines=[],
        changed_lines=[],
        action=ActionType.DELETE_FILE,
    )
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Valid delete_file: empty original_lines and changed_lines")

    # Invalid: non-empty original_lines or changed_lines, delete_file
    change = ApplydirFileChange(
        file_path=Path("src/old.py"),
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.DELETE_FILE,
    )
    errors = change.validate_change()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.INVALID_CHANGE
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "original_lines and changed_lines must be empty for delete_file"
    logger.debug(f"Invalid delete_file: {errors[0]}")

def test_from_file_entry_replace_lines():
    """Test from_file_entry for REPLACE_LINES with change_dict."""
    file_path = Path("src/main.py")
    action = ActionType.REPLACE_LINES
    change_dict = {
        "original_lines": ["print('Hello')"],
        "changed_lines": ["print('Hello World')"]
    }
    change = ApplydirFileChange.from_file_entry(file_path, action, change_dict)
    assert change.file_path == file_path
    assert change.original_lines == ["print('Hello')"]
    assert change.changed_lines == ["print('Hello World')"]
    assert change.action == ActionType.REPLACE_LINES
    logger.debug("Valid REPLACE_LINES from_file_entry")

def test_from_file_entry_create_file():
    """Test from_file_entry for CREATE_FILE with change_dict."""
    file_path = Path("src/new.py")
    action = ActionType.CREATE_FILE
    change_dict = {
        "original_lines": [],
        "changed_lines": ["print('New file')"]
    }
    change = ApplydirFileChange.from_file_entry(file_path, action, change_dict)
    assert change.file_path == file_path
    assert change.original_lines == []
    assert change.changed_lines == ["print('New file')"]
    assert change.action == ActionType.CREATE_FILE
    logger.debug("Valid CREATE_FILE from_file_entry")

def test_from_file_entry_delete_file():
    """Test from_file_entry for DELETE_FILE with None change_dict."""
    file_path = Path("src/old.py")
    action = ActionType.DELETE_FILE
    change = ApplydirFileChange.from_file_entry(file_path, action, None)
    assert change.file_path == file_path
    assert change.original_lines == []
    assert change.changed_lines == []
    assert change.action == ActionType.DELETE_FILE
    logger.debug("Valid DELETE_FILE from_file_entry")

def test_from_file_entry_empty_change_dict():
    """Test from_file_entry with empty change_dict."""
    file_path = Path("src/main.py")
    action = ActionType.REPLACE_LINES
    change_dict = {}
    change = ApplydirFileChange.from_file_entry(file_path, action, change_dict)
    assert change.file_path == file_path
    assert change.original_lines == []
    assert change.changed_lines == []
    assert change.action == ActionType.REPLACE_LINES
    logger.debug("Empty change_dict from_file_entry")

def test_from_file_entry_none_change_dict():
    """Test from_file_entry with None change_dict."""
    file_path = Path("src/main.py")
    action = ActionType.REPLACE_LINES
    change = ApplydirFileChange.from_file_entry(file_path, action, None)
    assert change.file_path == file_path
    assert change.original_lines == []
    assert change.changed_lines == []
    assert change.action == ActionType.REPLACE_LINES
    logger.debug("None change_dict from_file_entry")

def test_from_file_entry_non_dict_change_dict():
    """Test from_file_entry with non-dict change_dict."""
    file_path = Path("src/main.py")
    action = ActionType.REPLACE_LINES
    change_dict = "invalid"
    change = ApplydirFileChange.from_file_entry(file_path, action, change_dict)
    assert change.file_path == file_path
    assert change.original_lines == []
    assert change.changed_lines == []
    assert change.action == ActionType.REPLACE_LINES
    logger.debug("Non-dict change_dict from_file_entry")

def test_from_file_entry_invalid_action():
    """Test from_file_entry with invalid action raises ValueError."""
    file_path = Path("src/main.py")
    action = "invalid_action"
    with pytest.raises(ValueError) as exc_info:
        ApplydirFileChange.from_file_entry(file_path, action, None)
    logger.debug(f"Invalid action in from_file_entry: {exc_info.value}")
    assert "Input should be 'replace_lines', 'create_file' or 'delete_file" in str(exc_info.value)