import pytest
import logging
from pathlib import Path
from prepdir import configure_logging
from applydir.applydir_error import ApplydirError, ErrorType, ErrorSeverity
from applydir.applydir_file_change import ApplydirFileChange, ActionType
from applydir.applydir_matcher import ApplydirMatcher

# Set up logging for tests
logger = logging.getLogger("applydir_test")
configure_logging(logger, level=logging.DEBUG)

def test_json_structure_error():
    """Test ApplydirError creation for JSON_STRUCTURE."""
    error = ApplydirError(
        change=None,
        error_type=ErrorType.JSON_STRUCTURE,
        severity=ErrorSeverity.ERROR,
        message="Invalid JSON structure",
        details={"field": "files"},
    )
    assert error.error_type == ErrorType.JSON_STRUCTURE
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "Invalid JSON structure"
    assert error.details == {"field": "files"}
    assert error.change is None
    logger.debug(f"JSON structure error: {error}")

def test_file_path_error():
    """Test ApplydirError creation for FILE_PATH."""
    error = ApplydirError(
        change=None,
        error_type=ErrorType.FILE_PATH,
        severity=ErrorSeverity.ERROR,
        message="File path missing or empty",
        details={"file": "src/main.py"},
    )
    assert error.error_type == ErrorType.FILE_PATH
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "File path missing or empty"
    assert error.details == {"file": "src/main.py"}
    logger.debug(f"File path error: {error}")

def test_changes_empty_error():
    """Test ApplydirError creation for CHANGES_EMPTY."""
    error = ApplydirError(
        change=None,
        error_type=ErrorType.CHANGES_EMPTY,
        severity=ErrorSeverity.ERROR,
        message="Empty changes array for replace_lines or create_file",
        details={"file": "src/main.py"},
    )
    assert error.error_type == ErrorType.CHANGES_EMPTY
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "Empty changes array for replace_lines or create_file"
    assert error.details == {"file": "src/main.py"}
    logger.debug(f"Changes empty error: {error}")

def test_orig_lines_not_empty_error():
    """Test ApplydirError creation for ORIG_LINES_NOT_EMPTY."""
    change = ApplydirFileChange(
        file="src/new.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd(),
        action=ActionType.CREATE_FILE,
    )
    error = ApplydirError(
        change=change,
        error_type=ErrorType.ORIG_LINES_NOT_EMPTY,
        severity=ErrorSeverity.ERROR,
        message="Non-empty original_lines not allowed for create_file",
        details={},
    )
    assert error.error_type == ErrorType.ORIG_LINES_NOT_EMPTY
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "Non-empty original_lines not allowed for create_file"
    assert error.details == {}
    assert error.change == change
    logger.debug(f"Orig lines not empty error: {error}")

def test_orig_lines_empty_error():
    """Test ApplydirError creation for ORIG_LINES_EMPTY."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=[],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    error = ApplydirError(
        change=change,
        error_type=ErrorType.ORIG_LINES_EMPTY,
        severity=ErrorSeverity.ERROR,
        message="Empty original_lines not allowed for replace_lines",
        details={"file": "src/main.py"},
    )
    assert error.error_type == ErrorType.ORIG_LINES_EMPTY
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "Empty original_lines not allowed for replace_lines"
    assert error.details == {"file": "src/main.py"}
    assert error.change == change
    logger.debug(f"Orig lines empty error: {error}")

def test_syntax_error():
    """Test ApplydirError creation for SYNTAX."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    error = ApplydirError(
        change=change,
        error_type=ErrorType.SYNTAX,
        severity=ErrorSeverity.ERROR,
        message="Non-ASCII characters found in changed_lines",
        details={"line": "print('Hello 😊')", "line_number": 1},
    )
    assert error.error_type == ErrorType.SYNTAX
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "Non-ASCII characters found in changed_lines"
    assert error.details == {"line": "print('Hello 😊')", "line_number": 1}
    assert error.change == change
    logger.debug(f"Syntax error: {error}")

def test_empty_changed_lines_error():
    """Test ApplydirError creation for EMPTY_CHANGED_LINES."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=[],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    error = ApplydirError(
        change=change,
        error_type=ErrorType.EMPTY_CHANGED_LINES,
        severity=ErrorSeverity.ERROR,
        message="Empty changed_lines for replace_lines or create_file",
        details={"file": "src/main.py"},
    )
    assert error.error_type == ErrorType.EMPTY_CHANGED_LINES
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "Empty changed_lines for replace_lines or create_file"
    assert error.details == {"file": "src/main.py"}
    assert error.change == change
    logger.debug(f"Empty changed lines error: {error}")

def test_no_match_error():
    """Test ApplydirError creation for NO_MATCH with ApplydirMatcher."""
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
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.NO_MATCH
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "No matching lines found"
    assert errors[0].details == {"file": "src/main.py"}
    assert errors[0].change == change
    assert result is None
    logger.debug(f"No match error: {errors[0]}")

def test_multiple_matches_error():
    """Test ApplydirError creation for MULTIPLE_MATCHES with ApplydirMatcher."""
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
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.MULTIPLE_MATCHES
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Multiple matches found for original_lines"
    assert errors[0].details["file"] == "src/main.py"
    assert errors[0].details["match_count"] == 2
    assert errors[0].details["match_indices"] == [0, 2]
    assert errors[0].change == change
    assert result is None
    logger.debug(f"Multiple matches error: {errors[0]}")

def test_file_system_error():
    """Test ApplydirError creation for FILE_SYSTEM."""
    error = ApplydirError(
        change=None,
        error_type=ErrorType.FILE_SYSTEM,
        severity=ErrorSeverity.ERROR,
        message="File does not exist for deletion",
        details={"file": "src/main.py"},
    )
    assert error.error_type == ErrorType.FILE_SYSTEM
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "File does not exist for deletion"
    assert error.details == {"file": "src/main.py"}
    logger.debug(f"File system error: {error}")

def test_linting_error():
    """Test ApplydirError creation for LINTING."""
    error = ApplydirError(
        change=None,
        error_type=ErrorType.LINTING,
        severity=ErrorSeverity.ERROR,
        message="Linting failed on file (handled by vibedir)",
        details={"file": "src/main.py", "linting_output": "Syntax error at line 10"},
    )
    assert error.error_type == ErrorType.LINTING
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "Linting failed on file (handled by vibedir)"
    assert error.details == {"file": "src/main.py", "linting_output": "Syntax error at line 10"}
    logger.debug(f"Linting error: {error}")

def test_configuration_error():
    """Test ApplydirError creation for CONFIGURATION."""
    error = ApplydirError(
        change=None,
        error_type=ErrorType.CONFIGURATION,
        severity=ErrorSeverity.ERROR,
        message="Invalid configuration",
        details={"config_key": "validation.non_ascii"},
    )
    assert error.error_type == ErrorType.CONFIGURATION
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "Invalid configuration"
    assert error.details == {"config_key": "validation.non_ascii"}
    logger.debug(f"Configuration error: {error}")

def test_error_serialization():
    """Test JSON serialization of ApplydirError."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd(),
        action=ActionType.REPLACE_LINES,
    )
    error = ApplydirError(
        change=change,
        error_type=ErrorType.SYNTAX,
        severity=ErrorSeverity.ERROR,
        message="Non-ASCII characters found in changed_lines",
        details={"line": "print('Hello World')", "line_number": 1},
    )
    serialized = error.model_dump(mode="json")
    assert serialized["error_type"] == "syntax"
    assert serialized["severity"] == "error"
    assert serialized["message"] == "Non-ASCII characters found in changed_lines"
    assert serialized["details"] == {"line": "print('Hello World')", "line_number": 1}
    assert serialized["change"]["file"] == "src/main.py"
    assert serialized["change"]["action"] == "replace_lines"
    logger.debug(f"Serialized error: {serialized}")

def test_empty_message_raises():
    """Test empty message raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        ApplydirError(
            change=None,
            error_type=ErrorType.JSON_STRUCTURE,
            severity=ErrorSeverity.ERROR,
            message="",
            details={},
        )
    assert "Message cannot be empty or whitespace-only" in str(exc_info.value)
    logger.debug(f"Empty message error: {exc_info.value}")

def test_whitespace_message_raises():
    """Test whitespace-only message raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        ApplydirError(
            change=None,
            error_type=ErrorType.JSON_STRUCTURE,
            severity=ErrorSeverity.ERROR,
            message="   ",
            details={},
        )
    assert "Message cannot be empty or whitespace-only" in str(exc_info.value)
    logger.debug(f"Whitespace message error: {exc_info.value}")