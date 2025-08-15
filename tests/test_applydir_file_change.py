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
    """Test valid file path within base_dir."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    logger.debug(f"Valid file path: {change.file}")
    assert change.file == "src/main.py"


def test_invalid_file_path_outside_base_dir():
    """Test file path outside base_dir raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirFileChange(
            file="../outside.py",
            original_lines=["print('Hello')"],
            changed_lines=["print('Hello World')"],
            base_dir=Path.cwd(),
            action=ActionType.REPLACE_LINES,
        )
    logger.debug(f"Validation error for outside path: {exc_info.value}")
    assert "File path is outside project directory" in str(exc_info.value)


def test_empty_file_path():
    """Test empty file path raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirFileChange(
            file="",
            original_lines=["print('Hello')"],
            changed_lines=["print('Hello World')"],
            base_dir=Path.cwd(),
            action=ActionType.REPLACE_LINES,
        )
    logger.debug(f"Validation error for empty path: {exc_info.value}")
    assert "File path must be non-empty" in str(exc_info.value)


def test_missing_file_field():
    """Test missing file field raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirFileChange(
            file=None,
            original_lines=["print('Hello')"],
            changed_lines=["print('Hello World')"],
            base_dir=Path.cwd(),
            action=ActionType.REPLACE_LINES,
        )
    logger.debug(f"Validation error for missing file: {exc_info.value}")
    assert "File path must be non-empty" in str(exc_info.value)


def test_non_ascii_error():
    """Test non-ASCII characters with error config."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        base_dir=Path.cwd(),
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
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        base_dir=Path.cwd(),
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
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change(config=config)
    assert len(errors) == 0
    logger.debug("Non-ASCII ignored for .py due to rule override")


def test_empty_changed_lines_new_file():
    """Test empty changed_lines for new file."""
    change = ApplydirFileChange(
        file="src/new.py",
        original_lines=[],
        changed_lines=[],
        base_dir=Path.cwd(),
        action=ActionType.CREATE_FILE,
    )
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Empty changed_lines for new file")


def test_valid_change_no_original_lines():
    """Test valid change for create_file with empty original_lines."""
    change = ApplydirFileChange(
        file="src/new.py",
        original_lines=[],
        changed_lines=["print('Hello World')"],
        base_dir=None,
        action=ActionType.CREATE_FILE,
    )
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Valid change for create_file with empty original_lines")


def test_base_dir_storage():
    """Test base_dir is stored correctly."""
    base_dir = Path("/workspaces/applydir")
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=base_dir,
        action=ActionType.REPLACE_LINES,
    )
    assert change.base_dir == base_dir
    logger.debug(f"Base dir stored: {change.base_dir}")


def test_non_ascii_py_file_error():
    """Test non-ASCII characters in .py file generates ERROR."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        base_dir=Path.cwd(),
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
        file="src/script.js",
        original_lines=["console.log('Hello');"],
        changed_lines=["console.log('Hello 😊');"],
        base_dir=Path.cwd(),
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
        file="src/docs.md",
        original_lines=[],
        changed_lines=["Hello 😊"],
        base_dir=Path.cwd(),
        action=ActionType.CREATE_FILE,
    )
    errors = change.validate_change(config=TEST_ASCII_CONFIG)
    assert len(errors) == 0
    logger.debug("Non-ASCII ignored for .md")


def test_non_ascii_json_file_warning():
    """Test non-ASCII characters in .json file generates WARNING."""
    change = ApplydirFileChange(
        file="src/config.json",
        original_lines=['{"key": "value"}'],
        changed_lines=['{"key": "value 😊"}'],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change(config=TEST_ASCII_CONFIG)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.SYNTAX
    assert errors[0].severity == ErrorSeverity.WARNING
    assert errors[0].message == "Non-ASCII characters found in changed_lines"
    assert errors[0].details == {"line": '{"key": "value 😊"}', "line_number": 1}
    logger.debug(f"Non-ASCII warning for .json: {errors[0]}")


def test_non_ascii_default_action():
    """Test non-ASCII characters in unlisted extension (.txt) uses default WARNING."""
    change = ApplydirFileChange(
        file="src/notes.txt",
        original_lines=[],
        changed_lines=["Hello 😊"],
        base_dir=Path.cwd(),
        action=ActionType.CREATE_FILE,
    )
    errors = change.validate_change(config=TEST_ASCII_CONFIG)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.SYNTAX
    assert errors[0].severity == ErrorSeverity.WARNING
    assert errors[0].message == "Non-ASCII characters found in changed_lines"
    assert errors[0].details == {"line": "Hello 😊", "line_number": 1}
    logger.debug(f"Non-ASCII default warning for .txt: {errors[0]}")


def test_serialization_base_dir():
    """Test JSON serialization of ApplydirFileChange with base_dir."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    change_dict = change.model_dump(mode="json")
    logger.debug(f"Serialized change: {change_dict}")
    assert change_dict == {
        "file": "src/main.py",
        "original_lines": ["print('Hello')"],
        "changed_lines": ["print('Hello World')"],
        "base_dir": str(Path.cwd()),
        "action": "replace_lines",
    }


def test_serialization_none_base_dir():
    """Test JSON serialization of ApplydirFileChange with base_dir=None."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=None,
        action=ActionType.REPLACE_LINES,
    )
    change_dict = change.model_dump(mode="json")
    logger.debug(f"Serialized change with None base_dir: {change_dict}")
    assert change_dict == {
        "file": "src/main.py",
        "original_lines": ["print('Hello')"],
        "changed_lines": ["print('Hello World')"],
        "base_dir": None,
        "action": "replace_lines",
    }


def test_non_ascii_multiple_lines():
    """Test multiple non-ASCII lines in changed_lines."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')", "print('World 😊')"],
        base_dir=Path.cwd(),
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
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change(config={})
    assert len(errors) == 0
    logger.debug("Empty config: no errors")


def test_action_validation():
    """Test validation for action-specific rules."""
    # Valid: non-empty original_lines, non-empty changed_lines, replace_lines
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Valid replace_lines: non-empty original_lines and changed_lines")

    # Valid: non-empty original_lines, empty changed_lines, replace_lines (removal)
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=[],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Valid replace_lines: non-empty original_lines, empty changed_lines")

    # Invalid: empty original_lines, non-empty changed_lines, replace_lines
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=[],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    errors = change.validate_change()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.CHANGES_EMPTY
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Empty original_lines not allowed for replace_lines"
    logger.debug(f"Invalid replace_lines: {errors[0]}")

    # Valid: empty original_lines and changed_lines, create_file
    change = ApplydirFileChange(
        file="src/new.py",
        original_lines=[],
        changed_lines=[],
        base_dir=Path.cwd(),
        action=ActionType.CREATE_FILE,
    )
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Valid create_file: empty original_lines and changed_lines")

    # Valid: empty original_lines, non-empty changed_lines, create_file
    change = ApplydirFileChange(
        file="src/new.py",
        original_lines=[],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd(),
        action=ActionType.CREATE_FILE,
    )
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Valid create_file: empty original_lines, non-empty changed_lines")

    # Invalid: non-empty original_lines, create_file
    change = ApplydirFileChange(
        file="src/new.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd(),
        action=ActionType.CREATE_FILE,
    )
    errors = change.validate_change()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.ORIG_LINES_NOT_EMPTY
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Non-empty original_lines not allowed for create_file"
    logger.debug(f"Invalid create_file: {errors[0]}")


def test_invalid_action():
    """Test invalid action value raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirFileChange(
            file="src/main.py",
            original_lines=["print('Hello')"],
            changed_lines=["print('Hello World')"],
            base_dir=Path.cwd(),
            action="invalid_action",
        )
    logger.debug(f"Validation error for invalid action: {exc_info.value}")
    assert "Input should be 'replace_lines' or 'create_file'" in str(exc_info.value)


def test_action_serialization():
    """Test JSON serialization of action field."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    change_dict = change.model_dump(mode="json")
    logger.debug(f"Serialized action: {change_dict['action']}")
    assert change_dict["action"] == "replace_lines"

    change = ApplydirFileChange(
        file="src/new.py",
        original_lines=[],
        changed_lines=["print('Hello World')"],
        base_dir=None,
        action=ActionType.CREATE_FILE,
    )
    change_dict = change.model_dump(mode="json")
    logger.debug(f"Serialized action: {change_dict['action']}")
    assert change_dict["action"] == "create_file"


def test_no_match_error_integration():
    """Test ApplydirFileChange with ApplydirMatcher producing NO_MATCH error."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Unique')"],
        changed_lines=["print('Modified')"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    file_content = ["print('Different')", "print('Other')"]
    result, errors = matcher.match(file_content, change)
    print(f"result is {result}")
    print(f"errors is {errors}")
    assert isinstance(errors, list)
    assert len(errors) == 1

    logger.debug(f"NO_MATCH error: {errors[0]}")
    assert errors[0].error_type == ErrorType.NO_MATCH
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "No matching lines found"
    assert errors[0].details == {"file": "src/main.py", 'original_lines': ["print('Unique')"]}
    assert errors[0].change == change


def test_multiple_matches_error_integration():
    """Test ApplydirFileChange with ApplydirMatcher producing MULTIPLE_MATCHES error."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Common')"],
        changed_lines=["print('Modified')"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    file_content = ["print('Common')", "print('Other')", "print('Common')"]
    result, errors = matcher.match(file_content, change)
    print(f"result is {result}")
    print(f"errors is {errors}")
    assert isinstance(errors, list)
    assert len(errors) == 1

    logger.debug(f"MULTIPLE_MATCHES error: {errors[0]}")
    assert errors[0].error_type == ErrorType.MULTIPLE_MATCHES
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Multiple matches found for original_lines"
    assert errors[0].details == {"file": "src/main.py", "match_count": 2, 'match_indices': [0, 2]}
    assert errors[0].change == change
