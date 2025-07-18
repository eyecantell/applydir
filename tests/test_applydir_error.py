import pytest
import logging
from prepdir import configure_logging
from applydir.applydir_error import ApplydirError, ErrorType, ErrorSeverity
from applydir.applydir_file_change import ApplydirFileChange
from pydantic import ValidationError

# Set up logging for tests
logger = logging.getLogger("applydir_test")
configure_logging(logger, level=logging.DEBUG)


def test_error_creation_all_types():
    """Test creating ApplydirError for all ErrorType values with ERROR severity."""
    for error_type in ErrorType:
        error = ApplydirError(
            change=None,
            error_type=error_type,
            severity=ErrorSeverity.ERROR,
            message=f"Test {error_type.value} error",
            details={"test": "value"},
        )
        logger.debug(f"Created error: {error}")
        assert error.error_type == error_type
        assert error.severity == ErrorSeverity.ERROR
        assert error.message == f"Test {error_type.value} error"
        assert error.details == {"test": "value"}
        assert error.change is None


def test_error_creation_warning_severity():
    """Test creating ApplydirError with WARNING severity."""
    error = ApplydirError(
        change=None,
        error_type=ErrorType.SYNTAX,
        severity=ErrorSeverity.WARNING,
        message="Non-ASCII characters found",
        details={"line": "print('Hello 😊')", "line_number": 1},
    )
    logger.debug(f"Created warning: {error}")
    assert error.error_type == ErrorType.SYNTAX
    assert error.severity == ErrorSeverity.WARNING
    assert error.message == "Non-ASCII characters found"
    assert error.details == {"line": "print('Hello 😊')", "line_number": 1}


def test_error_with_file_change():
    """Test ApplydirError with an ApplydirFileChange."""
    change = ApplydirFileChange(
        file="src/main.py", original_lines=["print('Hello')"], changed_lines=["print('Hello 😊')"], base_dir=Path.cwd()
    )
    error = ApplydirError(
        change=change,
        error_type=ErrorType.SYNTAX,
        severity=ErrorSeverity.WARNING,
        message="Non-ASCII characters found",
        details={"line": "print('Hello 😊')", "line_number": 1},
    )
    logger.debug(f"Created error with change: {error}")
    assert error.change == change
    assert error.error_type == ErrorType.SYNTAX
    assert error.severity == ErrorSeverity.WARNING
    assert error.message == "Non-ASCII characters found"
    assert error.details == {"line": "print('Hello 😊')", "line_number": 1}


def test_error_serialization():
    """Test JSON serialization of ApplydirError."""
    change = ApplydirFileChange(
        file="src/main.py", original_lines=["print('Hello')"], changed_lines=["print('Hello 😊')"], base_dir=Path.cwd()
    )
    error = ApplydirError(
        change=change,
        error_type=ErrorType.SYNTAX,
        severity=ErrorSeverity.WARNING,
        message="Non-ASCII characters found",
        details={"line": "print('Hello 😊')", "line_number": 1},
    )
    error_dict = error.dict()
    logger.debug(f"Serialized error: {error_dict}")
    assert error_dict["change"] == {
        "file": "src/main.py",
        "original_lines": ["print('Hello')"],
        "changed_lines": ["print('Hello 😊')"],
    }
    assert error_dict["error_type"] == "syntax"
    assert error_dict["severity"] == "warning"
    assert error_dict["message"] == "Non-ASCII characters found"
    assert error_dict["details"] == {"line": "print('Hello 😊')", "line_number": 1}


def test_error_descriptions():
    """Test ERROR_DESCRIPTIONS mapping for all ErrorType values."""
    for error_type in ErrorType:
        assert error_type in ApplydirError.ERROR_DESCRIPTIONS
        assert isinstance(ApplydirError.ERROR_DESCRIPTIONS[error_type], str)
        logger.debug(f"Error description for {error_type}: {ApplydirError.ERROR_DESCRIPTIONS[error_type]}")


def test_invalid_message():
    """Test that empty message raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirError(
            change=None, error_type=ErrorType.JSON_STRUCTURE, severity=ErrorSeverity.ERROR, message="", details={}
        )
    logger.debug(f"Validation error for empty message: {exc_info.value}")
    assert "Message cannot be empty" in str(exc_info.value)


def test_details_default():
    """Test that details defaults to empty dict if None."""
    error = ApplydirError(
        change=None,
        error_type=ErrorType.JSON_STRUCTURE,
        severity=ErrorSeverity.ERROR,
        message="Test error",
        details=None,
    )
    logger.debug(f"Error with None details: {error}")
    assert error.details == {}


def test_invalid_error_type():
    """Test that invalid error_type raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirError(
            change=None,
            error_type="invalid_type",  # Not an ErrorType value
            severity=ErrorSeverity.ERROR,
            message="Invalid error type",
            details={},
        )
    logger.debug(f"Validation error for invalid error_type: {exc_info.value}")
    assert "value is not a valid enumeration member" in str(exc_info.value)


def test_invalid_severity():
    """Test that invalid severity raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirError(
            change=None,
            error_type=ErrorType.JSON_STRUCTURE,
            severity="invalid_severity",  # Not an ErrorSeverity value
            message="Invalid severity",
            details={},
        )
    logger.debug(f"Validation error for invalid severity: {exc_info.value}")
    assert "value is not a valid enumeration member" in str(exc_info.value)
