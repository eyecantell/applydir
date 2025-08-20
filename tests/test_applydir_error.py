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


@pytest.mark.parametrize(
    "error_type,message,details",
    [
        (ErrorType.JSON_STRUCTURE, "Invalid JSON structure", {"field": "files"}),
        (ErrorType.FILE_PATH, "File path missing or empty", {"file": "src/main.py"}),
        (ErrorType.CONFIGURATION, "Invalid configuration", {"config_key": "validation.non_ascii"}),
        (
            ErrorType.LINTING,
            "Linting failed on file (handled by vibedir)",
            {"file": "src/main.py", "linting_output": "Syntax error at line 10"},
        ),
        (ErrorType.CHANGES_EMPTY, "Empty changes array for replace_lines or create_file", {"file": "src/main.py"}),
    ],
)
def test_basic_error_types(error_type, message, details):
    """Test ApplydirError creation for basic error types."""
    error = ApplydirError(
        change=None,
        error_type=error_type,
        severity=ErrorSeverity.ERROR,
        message=message,
        details=details,
    )
    assert error.error_type == error_type
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == message
    assert error.details == details
    assert error.change is None
    logger.debug(f"Basic error ({error_type}): {error}")


@pytest.mark.parametrize(
    "error_type,message,details",
    [
        (ErrorType.FILE_NOT_FOUND, "File does not exist for deletion", {"file": "src/main.py"}),
        (ErrorType.FILE_ALREADY_EXISTS, "File already exists for create_file", {"file": "src/main.py"}),
        (ErrorType.FILE_SYSTEM, "File system operation failed due to insufficient disk space", {"file": "src/main.py"}),
        (ErrorType.PERMISSION_DENIED, "Permission denied when accessing file", {"file": "src/main.py"}),
    ],
)
def test_file_operation_errors(error_type, message, details):
    """Test ApplydirError creation for file operation errors."""
    error = ApplydirError(
        change=None,
        error_type=error_type,
        severity=ErrorSeverity.ERROR,
        message=message,
        details=details,
    )
    assert error.error_type == error_type
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == message
    assert error.details == details
    assert error.change is None
    logger.debug(f"File operation error ({error_type}): {error}")


@pytest.mark.parametrize(
    "action,file,original_lines,changed_lines,change_count",
    [
        (ActionType.REPLACE_LINES, "src/main.py", ["print('Hello')"], ["print('Hello World')"], 1),
        (ActionType.REPLACE_LINES, "src/main.py", ["def func():", "    pass"], ["def func():", "    return 42"], 2),
        (ActionType.CREATE_FILE, "src/new.py", [], ["print('Hello World')"], 1),
        (ActionType.DELETE_FILE, "src/old.py", [], [], 1),
    ],
)
def test_file_changes_successful(action, file, original_lines, changed_lines, change_count):
    """Test ApplydirError creation for FILE_CHANGES_SUCCESSFUL with different actions."""
    change = ApplydirFileChange(
        file_path=file,
        original_lines=original_lines,
        changed_lines=changed_lines,
        action=action,
    )
    error = ApplydirError(
        change=change,
        error_type=ErrorType.FILE_CHANGES_SUCCESSFUL,
        severity=ErrorSeverity.INFO,
        message="All changes to file applied successfully",
        details={"file": file, "action": action.value, "change_count": change_count},
    )
    assert error.error_type == ErrorType.FILE_CHANGES_SUCCESSFUL
    assert error.severity == ErrorSeverity.INFO
    assert error.message == "All changes to file applied successfully"
    assert error.details == {"file": file, "action": action.value, "change_count": change_count}
    assert error.change == change
    logger.debug(f"File changes successful ({action}, {change_count} changes): {error}")


def test_orig_lines_not_empty_error():
    """Test ApplydirError creation for ORIG_LINES_NOT_EMPTY."""
    change = ApplydirFileChange(
        file_path="src/new.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
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
        file_path="src/main.py",
        original_lines=[],
        changed_lines=["print('Hello World')"],
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
        file_path="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
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
    """Test ApplydirError creation for CHANGED_LINES_EMPTY."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=[],
        action=ActionType.REPLACE_LINES,
    )
    error = ApplydirError(
        change=change,
        error_type=ErrorType.CHANGED_LINES_EMPTY,
        severity=ErrorSeverity.ERROR,
        message="Empty changed_lines for replace_lines or create_file",
        details={"file": "src/main.py"},
    )
    assert error.error_type == ErrorType.CHANGED_LINES_EMPTY
    assert error.severity == ErrorSeverity.ERROR
    assert error.message == "Empty changed_lines for replace_lines or create_file"
    assert error.details == {"file": "src/main.py"}
    assert error.change == change
    logger.debug(f"Empty changed lines error: {error}")


def test_no_match_error():
    """Test ApplydirError creation for NO_MATCH with ApplydirMatcher."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Unique')"],
        changed_lines=["print('Modified')"],
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
        file_path="src/main.py",
        original_lines=["print('Common')"],
        changed_lines=["print('Modified')"],
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


def test_all_error_types_instantiable():
    """Test that all ErrorType values can be instantiated with minimal configuration."""
    for error_type in ErrorType:
        error = ApplydirError(
            change=None,
            error_type=error_type,
            severity=ErrorSeverity.ERROR if error_type != ErrorType.FILE_CHANGES_SUCCESSFUL else ErrorSeverity.INFO,
            message=str(error_type),
            details={},
        )
        assert error.error_type == error_type
        assert error.message == str(error_type)
        assert error.details == {}
        assert error.change is None
        logger.debug(f"Instantiable error type ({error_type}): {error}")


def test_error_serialization():
    """Test JSON serialization of ApplydirError."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    error = ApplydirError(
        change=change,
        error_type=ErrorType.FILE_CHANGES_SUCCESSFUL,
        severity=ErrorSeverity.INFO,
        message="All changes to file applied successfully",
        details={"file": "src/main.py", "action": "replace_lines", "change_count": 1},
    )
    serialized = error.model_dump(mode="json")
    assert serialized["error_type"] == "file_changes_successful"
    assert serialized["severity"] == "info"
    assert serialized["message"] == "All changes to file applied successfully"
    assert serialized["details"] == {"file": "src/main.py", "action": "replace_lines", "change_count": 1}
    assert serialized["change"]["file_path"] == "src/main.py"
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
