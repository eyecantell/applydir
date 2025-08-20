import pytest
from pathlib import Path
from applydir.applydir_applicator import ApplydirApplicator
from applydir.applydir_file_change import ApplydirFileChange, ActionType
from applydir.applydir_error import ApplydirError, ErrorType, ErrorSeverity
from applydir.applydir_matcher import ApplydirMatcher
from applydir.applydir_changes import ApplydirChanges, FileEntry
import logging
from prepdir import configure_logging

logger = logging.getLogger("applydir_test")
configure_logging(logger, level=logging.DEBUG)


@pytest.fixture
def applicator(tmp_path):
    """Create an ApplydirApplicator instance."""
    return ApplydirApplicator(base_dir=str(tmp_path), matcher=ApplydirMatcher(), logger=logger)


def test_apply_replace_lines_exact(tmp_path, applicator):
    """Test replacing lines with exact match."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\nx = 1\n")
    change = ApplydirFileChange(
        file_path=file_path,
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    config = {
        "matching": {
            "whitespace": {"default": "collapse", "rules": [{"extensions": [".py"], "handling": "remove"}]},
            "use_fuzzy": {"default": True, "rules": [{"extensions": [".py"], "use_fuzzy": False}]},
        },
        "allow_file_deletion": False,
    }
    errors = applicator.apply_single_change(file_path, change)
    assert len(errors) == 0
    assert file_path.read_text() == "print('Hello World')\nx = 1\n"
    logger.debug(f"Replaced lines exactly: {file_path.read_text()}")


def test_apply_replace_lines_fuzzy(tmp_path, applicator):
    """Test replacing lines with fuzzy match."""
    file_path = tmp_path / "main.py"
    file_path.write_text("Print('Helo') \nx = 1\n")
    change = ApplydirFileChange(
        file_path=file_path,
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    config = {
        "matching": {
            "whitespace": {"default": "collapse", "rules": [{"extensions": [".py"], "handling": "remove"}]},
            "similarity": {"default": 0.95, "rules": [{"extensions": [".py"], "threshold": 0.5}]},
            "similarity_metric": {
                "default": "sequence_matcher",
                "rules": [{"extensions": [".py"], "metric": "levenshtein"}],
            },
            "use_fuzzy": {"default": True, "rules": [{"extensions": [".py"], "use_fuzzy": True}]},
        },
        "allow_file_deletion": False,
    }
    errors = applicator.apply_single_change(file_path, change)
    assert len(errors) == 0
    assert file_path.read_text() == "print('Hello World')\nx = 1\n"
    logger.debug(f"Replaced lines fuzzily: {file_path.read_text()}")


def test_apply_create_file(tmp_path, applicator):
    """Test creating a new file."""
    file_path = tmp_path / "new.py"
    change = ApplydirFileChange(
        file_path=file_path,
        original_lines=[],
        changed_lines=["print('New file')"],
        action=ActionType.CREATE_FILE,
    )
    errors = applicator.apply_single_change(file_path, change)
    assert len(errors) == 0
    assert file_path.read_text() == "print('New file')\n"
    logger.debug(f"Created file: {file_path.read_text()}")


def test_apply_delete_file(tmp_path, applicator):
    """Test deleting a file."""
    file_path = tmp_path / "old.py"
    file_path.write_text("print('Old file')\n")
    errors = applicator.delete_file(file_path, "old.py")
    assert len(errors) == 0
    assert not file_path.exists()
    logger.debug("Deleted file successfully")


def test_apply_create_file_exists(tmp_path, applicator):
    """Test creating a file that already exists produces FILE_ALREADY_EXISTS error."""
    file_path = tmp_path / "existing.py"
    file_path.write_text("print('Existing')\n")
    change = ApplydirFileChange(
        file_path=file_path,
        original_lines=[],
        changed_lines=["print('New content')"],
        action=ActionType.CREATE_FILE,
    )
    errors = applicator.apply_single_change(file_path, change)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_ALREADY_EXISTS
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "File already exists for new file creation"
    assert file_path.read_text() == "print('Existing')\n"  # File unchanged
    logger.debug(f"Create file exists error: {errors[0].message}")


def test_apply_delete_file_not_found(tmp_path, applicator):
    """Test deleting a non-existent file produces FILE_NOT_FOUND error."""
    file_path = tmp_path / "non_existent.py"
    errors = applicator.delete_file(file_path, "non_existent.py")
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_NOT_FOUND
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "File does not exist for deletion"
    logger.debug(f"Delete file not found error: {errors[0].message}")


def test_apply_replace_lines_non_ascii_error(tmp_path, applicator):
    """Test non-ASCII in changed_lines triggers error per config."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    change = ApplydirFileChange(
        file_path=file_path,
        original_lines=["print('Hello')"],
        changed_lines=["print('Héllo')"],  # Non-ASCII é
        action=ActionType.REPLACE_LINES,
    )
    config = {
        "validation": {"non_ascii": {"default": "error", "rules": [{"extensions": [".py"], "action": "error"}]}},
    }
    errors = applicator.apply_single_change(file_path, change)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.SYNTAX
    assert errors[0].severity == ErrorSeverity.ERROR
    assert "Non-ASCII characters found" in errors[0].message
    assert file_path.read_text() == "print('Hello')\n"  # File unchanged
    logger.debug(f"Non-ASCII error: {errors[0].message}")


def test_apply_replace_lines_multiple_matches_no_fuzzy(tmp_path, applicator):
    """Test multiple matches with fuzzy disabled."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\nprint('Hello')\n")
    change = ApplydirFileChange(
        file_path=file_path,
        original_lines=["print('Hello')"],
        changed_lines=["print('Updated')"],
        action=ActionType.REPLACE_LINES,
    )
    config = {
        "matching": {"use_fuzzy": {"default": False}},
    }
    applicator.config.update(config)
    errors = applicator.apply_single_change(file_path, change)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.MULTIPLE_MATCHES
    assert errors[0].severity == ErrorSeverity.ERROR
    assert "Multiple matches found" in errors[0].message
    assert file_path.read_text() == "print('Hello')\nprint('Hello')\n"  # File unchanged
    logger.debug(f"Multiple matches no fuzzy error: {errors[0].message}")


def test_apply_multiple_files(tmp_path, applicator):
    """Test applying changes to multiple files (replace, create, delete)."""
    file1 = tmp_path / "file1.py"
    file2 = tmp_path / "file2.py"
    file3 = tmp_path / "file3.py"
    file1.write_text("print('Old')\n")
    file2.write_text("x = 1\n")

    changes = ApplydirChanges(
        file_entries=[
            FileEntry(
                file="file1.py",
                action=ActionType.REPLACE_LINES,
                changes=[{"original_lines": ["print('Old')"], "changed_lines": ["print('New')"]}],
            ),
            FileEntry(file="file2.py", action=ActionType.DELETE_FILE, changes=[]),
            FileEntry(
                file="file3.py",
                action=ActionType.CREATE_FILE,
                changes=[{"original_lines": [], "changed_lines": ["print('Created')"]}],
            ),
        ]
    )
    applicator.changes = changes
    app_errors = applicator.apply_changes()
    assert len(app_errors) == 0
    assert file1.read_text() == "print('New')\n"
    assert not file2.exists()
    assert file3.read_text() == "print('Created')\n"
    logger.debug("Applied multi-file changes: replace, delete, create")


def test_apply_success_reporting(tmp_path, applicator):
    """Test successful application produces FILE_CHANGES_SUCCESSFUL info."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    change = ApplydirFileChange(
        file_path=file_path,
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    errors = applicator.apply_single_change(file_path, change)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_CHANGES_SUCCESSFUL
    assert errors[0].severity == ErrorSeverity.INFO
    assert errors[0].message == "All changes to file applied successfully"
    assert errors[0].details == {"file": str(file_path), "action": "replace_lines", "change_count": 1}
    logger.debug(f"Success reporting: {errors[0].message}")


def test_apply_delete_disabled(tmp_path, applicator):
    """Test deletion disabled in config produces PERMISSION_DENIED error."""
    file_path = tmp_path / "old.py"
    file_path.write_text("print('Old')\n")
    applicator.config.update({"allow_file_deletion": False})
    errors = applicator.delete_file(file_path, "old.py")
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.PERMISSION_DENIED
    assert errors[0].severity == ErrorSeverity.ERROR
    assert "File deletion is disabled" in errors[0].message
    assert file_path.exists()  # File unchanged
    logger.debug(f"Delete disabled error: {errors[0].message}")


def test_apply_file_system_error(tmp_path, applicator):
    """Test file system error (e.g., permission denied) produces FILE_SYSTEM error."""
    file_path = tmp_path / "protected.py"
    file_path.write_text("print('Protected')\n")
    file_path.chmod(0o444)  # Read-only
    change = ApplydirFileChange(
        file_path=file_path,
        original_lines=["print('Protected')"],
        changed_lines=["print('Updated')"],
        action=ActionType.REPLACE_LINES,
    )
    errors = applicator.apply_single_change(file_path, change)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_SYSTEM
    assert errors[0].severity == ErrorSeverity.ERROR
    assert "File operation failed" in errors[0].message
    assert file_path.read_text() == "print('Protected')\n"  # File unchanged
    logger.debug(f"File system error: {errors[0].message}")
