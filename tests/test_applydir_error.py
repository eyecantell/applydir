import pytest
import logging
from pathlib import Path
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
        details={"line": "print('Hello World')", "line_number": 1},
    )
    logger.debug(f"Created warning: {error}")
    assert error.error_type == ErrorType.SYNTAX
    assert error.severity == ErrorSeverity.WARNING
    assert error.message == "Non-ASCII characters found"
    assert error.details == {"line": "print('Hello World')", "line_number": 1}


def test_error_with_file_change():
    """Test ApplydirError with an ApplydirFileChange."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd()
    )
    error = ApplydirError(
        change=change,
        error_type=ErrorType.SYNTAX,
        severity=ErrorSeverity.WARNING,
        message="Non-ASCII characters found",
        details={"line": "print('Hello World')", "line_number": 1},
    )
    logger.debug(f"Created error with change: {error}")
    assert error.change == change
    assert error.error_type == ErrorType.SYNTAX
    assert error.severity == ErrorSeverity.WARNING
    assert error.message == "Non-ASCII characters found"
    assert error.details == {"line": "print('Hello World')", "line_number": 1}


def test_error_serialization():
    """Test JSON serialization of ApplydirError."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd()
    )
    error = ApplydirError(
        change=change,
        error_type=ErrorType.SYNTAX,
        severity=ErrorSeverity.WARNING,
        message="Non-ASCII characters found",
        details={"line": "print('Hello World')", "line_number": 1},
    )
    error_dict = error.model_dump()
    logger.debug(f"Serialized error: {error_dict}")
    assert error_dict["change"] == {
        "file": "src/main.py",
        "original_lines": ["print('Hello')"],
        "changed_lines": ["print('Hello World')"],
        "base_dir": Path.cwd()
    }
    assert error_dict["error_type"] == "syntax"
    assert error_dict["severity"] == "warning"
    assert error_dict["message"] == "Non-ASCII characters found"
    assert error_dict["details"] == {"line": "print('Hello World')", "line_number": 1}
    assert "ERROR_DESCRIPTIONS" not in error_dict  # ClassVar not serialized


def test_error_serialization_none_change():
    """Test JSON serialization with explicit None for change."""
    error = ApplydirError(
        change=None,
        error_type=ErrorType.JSON_STRUCTURE,
        severity=ErrorSeverity.ERROR,
        message="Invalid JSON structure",
        details={"error": "Missing files array"},
    )
    error_dict = error.model_dump()
    logger.debug(f"Serialized error with None change: {error_dict}")
    assert error_dict["change"] is None
    assert error_dict["error_type"] == "json_structure"
    assert error_dict["severity"] == "error"
    assert error_dict["message"] == "Invalid JSON structure"
    assert error_dict["details"] == {"error": "Missing files array"}
    assert "ERROR_DESCRIPTIONS" not in error_dict


def test_error_descriptions():
    """Test ERROR_DESCRIPTIONS mapping for all ErrorType values."""
    for error_type in ErrorType:
        assert error_type in ApplydirError.ERROR_DESCRIPTIONS
        assert isinstance(ApplydirError.ERROR_DESCRIPTIONS[error_type], str)
        logger.debug(f"Error description for {error_type}: {ApplydirError.ERROR_DESCRIPTIONS[error_type]}")


def test_default_severity():
    """Test default severity is ERROR."""
    error = ApplydirError(
        change=None,
        error_type=ErrorType.JSON_STRUCTURE,
        message="Test default severity",
        details={"test": "value"},
    )
    logger.debug(f"Created error with default severity: {error}")
    assert error.severity == ErrorSeverity.ERROR


def test_invalid_message_empty():
    """Test that empty message raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirError(
            change=None,
            error_type=ErrorType.JSON_STRUCTURE,
            severity=ErrorSeverity.ERROR,
            message="",
            details={}
        )
    logger.debug(f"Validation error for empty message: {exc_info.value}")
    assert "Message cannot be empty or whitespace-only" in str(exc_info.value)


def test_invalid_message_whitespace_only():
    """Test that whitespace-only message raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirError(
            change=None,
            error_type=ErrorType.JSON_STRUCTURE,
            severity=ErrorSeverity.ERROR,
            message="   ",
            details={}
        )
    logger.debug(f"Validation error for whitespace-only message: {exc_info.value}")
    assert "Message cannot be empty or whitespace-only" in str(exc_info.value)


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


def test_invalid_details_type():
    """Test that non-dict details raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirError(
            change=None,
            error_type=ErrorType.JSON_STRUCTURE,
            severity=ErrorSeverity.ERROR,
            message="Test error",
            details=["invalid"]  # Non-dict type
        )
    logger.debug(f"Validation error for invalid details type: {exc_info.value}")
    assert "Input should be a valid dictionary" in str(exc_info.value)


def test_complex_details():
    """Test serialization with complex nested details dictionary."""
    complex_details = {
        "error": "Complex issue",
        "nested": {"line": 1, "column": 10, "details": {"code": "print('Hello')"}},
        "list": [1, 2, 3]
    }
    error = ApplydirError(
        change=None,
        error_type=ErrorType.SYNTAX,
        severity=ErrorSeverity.WARNING,
        message="Complex error",
        details=complex_details
    )
    error_dict = error.model_dump()
    logger.debug(f"Serialized error with complex details: {error_dict}")
    assert error_dict["details"] == complex_details
    assert error_dict["message"] == "Complex error"
    assert error_dict["error_type"] == "syntax"
    assert error_dict["severity"] == "warning"


def test_error_str_representation():
    """Test string representation of ApplydirError."""
    error = ApplydirError(
        change=None,
        error_type=ErrorType.JSON_STRUCTURE,
        severity=ErrorSeverity.ERROR,
        message="Invalid JSON structure",
        details={"error": "Missing files array"}
    )
    error_str = str(error)
    logger.debug(f"Error string representation: {error_str}")
    assert "Invalid JSON structure" in error_str
    assert "json_structure" in error_str
    assert "error" in error_str
    assert "Missing files array" in error_str


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
    assert "Input should be 'json_structure'" in str(exc_info.value)


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
    assert "Input should be 'error' or 'warning'" in str(exc_info.value)