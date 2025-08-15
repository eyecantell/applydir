import pytest
import logging
from pathlib import Path
from prepdir import configure_logging
from applydir.applydir_file_change import ApplydirFileChange
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
        )
    logger.debug(f"Validation error for outside path: {exc_info.value}")
    assert "File path is outside project directory" in str(exc_info.value)

def test_empty_file_path():
    """Test empty file path raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirFileChange(
            file="", original_lines=["print('Hello')"], changed_lines=["print('Hello World')"], base_dir=Path.cwd()
        )
    logger.debug(f"Validation error for empty path: {exc_info.value}")
    assert "File path must be non-empty" in str(exc_info.value)

def test_missing_file_field():
    """Test missing file field raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirFileChange(
            file=None, original_lines=["print('Hello')"], changed_lines=["print('Hello World')"], base_dir=Path.cwd()
        )
    logger.debug(f"Validation error for missing file: {exc_info.value}")
    assert "File path must be non-empty" in str(exc_info.value)

def test_non_ascii_error():
    """Test non-ASCII characters with error config."""
    change = ApplydirFileChange(
        file="src/main.py", original_lines=["print('Hello')"], changed_lines=["print('Hello 😊')"], base_dir=Path.cwd()
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
        file="src/main.py", original_lines=["print('Hello')"], changed_lines=["print('Hello 😊')"], base_dir=Path.cwd()
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
        file="src/main.py", original_lines=["print('Hello')"], changed_lines=["print('Hello 😊')"], base_dir=Path.cwd()
    )
    errors = change.validate_change(config=config)
    assert len(errors) == 0
    logger.debug("Non-ASCII ignored for .py due to rule override")

def test_empty_changed_lines_new_file():
    """Test empty changed_lines for new file."""
    change = ApplydirFileChange(file="src/new.py", original_lines=[], changed_lines=[], base_dir=Path.cwd())
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Empty changed_lines for new file")

def test_valid_change_no_original_lines():
    """Test valid change with no original lines."""
    change = ApplydirFileChange(
        file="src/new.py", original_lines=[], changed_lines=["print('Hello World')"], base_dir=None
    )
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Valid change with no original lines")

def test_base_dir_storage():
    """Test base_dir is stored correctly."""
    base_dir = Path("/workspaces/applydir")
    change = ApplydirFileChange(
        file="src/main.py", original_lines=["print('Hello')"], changed_lines=["print('Hello World')"], base_dir=base_dir
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
        original_lines=["Hello"],
        changed_lines=["Hello 😊"],
        base_dir=Path.cwd(),
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
        original_lines=["Hello"],
        changed_lines=["Hello 😊"],
        base_dir=Path.cwd(),
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
    )
    change_dict = change.model_dump(mode="json")
    logger.debug(f"Serialized change: {change_dict}")
    assert change_dict == {
        "file": "src/main.py",
        "original_lines": ["print('Hello')"],
        "changed_lines": ["print('Hello World')"],
        "base_dir": str(Path.cwd()),
    }

def test_serialization_none_base_dir():
    """Test JSON serialization of ApplydirFileChange with base_dir=None."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=None,
    )
    change_dict = change.model_dump(mode="json")
    logger.debug(f"Serialized change with None base_dir: {change_dict}")
    assert change_dict == {
        "file": "src/main.py",
        "original_lines": ["print('Hello')"],
        "changed_lines": ["print('Hello World')"],
        "base_dir": None,
    }

def test_non_ascii_multiple_lines():
    """Test multiple non-ASCII lines in changed_lines."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')", "print('World 😊')"],
        base_dir=Path.cwd(),
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
    )
    errors = change.validate_change(config={})
    assert len(errors) == 0
    logger.debug("Empty config: no errors")

def test_replace_lines_validation():
    """Test validation for replace_lines requiring non-empty original_lines and changed_lines."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=[],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd(),
    )
    errors = change.validate_change()
    assert len(errors) == 0  # Empty original_lines allowed for create_file
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=[],
        base_dir=Path.cwd(),
    )
    errors = change.validate_change()
    assert len(errors) == 0  # Empty changed_lines allowed for replace_lines
    logger.debug("Replace lines validation")

def test_no_match_error_integration():
    """Test ApplydirFileChange with ApplydirMatcher producing NO_MATCH error."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Unique')"],
        changed_lines=["print('Modified')"],
        base_dir=Path.cwd(),
    )
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    file_content = ["print('Different')", "print('Other')"]
    result = matcher.match(file_content, change)
    assert isinstance(result, list)
    assert len(result) == 1
    error = result[0]
    logger.debug(f"NO_MATCH error: {error}")
    assert error.error_type == ErrorType.NO_MATCH
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "No matching lines found"
    assert error.details == {"file": "src/main.py"}
    assert error.change == change

def test_multiple_matches_error_integration():
    """Test ApplydirFileChange with ApplydirMatcher producing MULTIPLE_MATCHES error."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Common')"],
        changed_lines=["print('Modified')"],
        base_dir=Path.cwd(),
    )
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    file_content = ["print('Common')", "print('Other')", "print('Common')"]
    result = matcher.match(file_content, change)
    assert isinstance(result, list)
    assert len(result) == 1
    error = result[0]
    logger.debug(f"MULTIPLE_MATCHES error: {error}")
    assert error.error_type == ErrorType.MULTIPLE_MATCHES
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "Multiple matches found for original_lines"
    assert error.details == {"file": "src/main.py", "match_count": 2}
    assert error.change == change