import pytest
import logging
from pathlib import Path
from prepdir import configure_logging
from applydir.applydir_file_change import ApplydirFileChange
from applydir.applydir_error import ApplydirError, ErrorType, ErrorSeverity
from pydantic import ValidationError

# Set up logging for tests
logger = logging.getLogger("applydir_test")
configure_logging(logger, level=logging.DEBUG)


def test_valid_file_path():
    """Test valid file path resolution."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd()
    )
    assert change.file == "src/main.py"
    logger.debug(f"Valid file path: {change.file}")


def test_invalid_file_path_outside_base_dir():
    """Test file path outside base_dir raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirFileChange(
            file="../outside.py",
            original_lines=["print('Hello')"],
            changed_lines=["print('Hello World')"],
            base_dir=Path.cwd()
        )
    logger.debug(f"Validation error for path outside base_dir: {exc_info.value}")
    assert "File path is outside project directory" in str(exc_info.value)


def test_empty_file_path():
    """Test empty file path raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ApplydirFileChange(
            file="",
            original_lines=["print('Hello')"],
            changed_lines=["print('Hello World')"],
            base_dir=Path.cwd()
        )
    logger.debug(f"Validation error for empty file path: {exc_info.value}")
    assert "File path must be non-empty" in str(exc_info.value)


def test_non_ascii_error():
    """Test non-ASCII characters with error action."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        base_dir=Path.cwd()
    )
    errors = change.validate_change(config_override={"validation": {"non_ascii": {"default": "error"}}})
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.SYNTAX
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Non-ASCII characters found in changed_lines"
    assert errors[0].details == {"line": "print('Hello 😊')", "line_number": 1}
    logger.debug(f"Non-ASCII error: {errors[0]}")


def test_non_ascii_ignore():
    """Test non-ASCII characters with ignore action."""
    change = ApplydirFileChange(
        file="README.md",
        original_lines=["# Hello"],
        changed_lines=["# Hello 😊"],
        base_dir=Path.cwd()
    )
    errors = change.validate_change(config_override={"validation": {"non_ascii": {"default": "ignore"}}})
    assert len(errors) == 0
    logger.debug("Non-ASCII ignored as expected")


def test_non_ascii_rule_override():
    """Test non-ASCII validation with rule-based action override."""
    change = ApplydirFileChange(
        file="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello 😊')"],
        base_dir=Path.cwd()
    )
    config_override = {
        "validation": {
            "non_ascii": {
                "default": "error",
                "rules": [
                    {"extensions": [".py"], "action": "ignore"}
                ]
            }
        }
    }
    errors = change.validate_change(config_override=config_override)
    assert len(errors) == 0
    logger.debug("Non-ASCII ignored due to rule override for .py files")


def test_empty_changed_lines_new_file():
    """Test empty changed_lines for new file raises error."""
    change = ApplydirFileChange(
        file="src/new.py",
        original_lines=[],
        changed_lines=[],
        base_dir=Path.cwd()
    )
    errors = change.validate_change()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.EMPTY_CHANGED_LINES
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "changed_lines cannot be empty for new files"
    logger.debug(f"Empty changed_lines error: {errors[0]}")


def test_valid_change_no_original_lines():
    """Test valid new file change."""
    change = ApplydirFileChange(
        file="src/new.py",
        original_lines=[],
        changed_lines=["print('Hello World')"],
        base_dir=Path.cwd()
    )
    errors = change.validate_change()
    assert len(errors) == 0
    logger.debug("Valid new file change")