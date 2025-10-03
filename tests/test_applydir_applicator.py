import pytest
from pathlib import Path
from applydir.applydir_applicator import ApplydirApplicator
from applydir.applydir_file_change import ApplydirFileChange, ActionType
from applydir.applydir_error import ApplydirError, ErrorType, ErrorSeverity
from applydir.applydir_matcher import ApplydirMatcher
from applydir.applydir_changes import ApplydirChanges, FileEntry
import logging
import json
from prepdir import configure_logging
from pydantic import ValidationError

logger = logging.getLogger("applydir_test")
configure_logging(logger, level=logging.DEBUG)

logging.getLogger("applydir").setLevel(logging.DEBUG)

TEST_ASCII_CONFIG = {
    "validation": {
        "non_ascii": {
            "default": "warning",
            "rules": [
                {"path": True, "action": "error"},
                {"extensions": [".py", ".js"], "action": "error"},
                {"extensions": [".md", ".markdown"], "action": "ignore"},
                {"extensions": [".json", ".yaml"], "action": "warning"},
            ],
        }
    }
}


@pytest.fixture
def applicator(tmp_path):
    """Create an ApplydirApplicator instance."""
    return ApplydirApplicator(base_dir=str(tmp_path), matcher=ApplydirMatcher(), logger=logger)


def test_replace_lines_exact(tmp_path, applicator):
    """Test replacing lines with exact match."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\nx = 1\n")
    changes = ApplydirChanges(
        file_entries=[
            FileEntry(
                file="main.py",
                action=ActionType.REPLACE_LINES,
                changes=[{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
            )
        ]
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_CHANGES_SUCCESSFUL
    assert errors[0].severity == ErrorSeverity.INFO
    assert errors[0].message == "All changes to file applied successfully"
    assert errors[0].details == {"file": str(file_path), "actions": ["replace_lines"], "change_count": 1}
    assert file_path.read_text() == "print('Hello World')\nx = 1\n"
    logger.debug(f"Replaced lines exactly: {file_path.read_text()}")


def test_replace_lines_exact_from_json(tmp_path, applicator):
    """Test replacing lines with exact match."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\nx = 1\n")
    changes_json = [
        {
            "file": str(file_path),
            "action": "replace_lines",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
        }
    ]
    changes = ApplydirChanges(file_entries=changes_json)
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_CHANGES_SUCCESSFUL
    assert errors[0].severity == ErrorSeverity.INFO
    assert errors[0].message == "All changes to file applied successfully"
    assert errors[0].details == {"file": str(file_path), "actions": ["replace_lines"], "change_count": 1}
    assert file_path.read_text() == "print('Hello World')\nx = 1\n"
    logger.debug(f"Replaced lines exactly: {file_path.read_text()}")


def test_replace_lines_fuzzy(tmp_path, applicator):
    """Test replacing lines with fuzzy match."""
    file_path = tmp_path / "main.py"
    file_path.write_text("Print('Helo') \nx = 1\n")
    changes = ApplydirChanges(
        file_entries=[
            FileEntry(
                file="main.py",
                action=ActionType.REPLACE_LINES,
                changes=[{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
            )
        ]
    )
    applicator.config.update(
        {
            "matching": {
                "whitespace": {"default": "collapse", "rules": [{"extensions": [".py"], "handling": "remove"}]},
                "similarity": {"default": 0.95, "rules": [{"extensions": [".py"], "threshold": 0.2}]},
                "similarity_metric": {
                    "default": "sequence_matcher",
                    "rules": [{"extensions": [".py"], "metric": "levenshtein"}],
                },
                "use_fuzzy": {"default": True, "rules": [{"extensions": [".py"], "use_fuzzy": True}]},
            },
            "allow_file_deletion": False,
        },
    )
    applicator.matcher.config = applicator.config.as_dict()
    applicator.changes = changes

    errors = applicator.apply_changes()
    print("errors are: \n" + "\n".join([str(err) for err in errors]))
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_CHANGES_SUCCESSFUL
    assert errors[0].severity == ErrorSeverity.INFO
    assert errors[0].message == "All changes to file applied successfully"
    assert errors[0].details == {"file": str(file_path), "actions": ["replace_lines"], "change_count": 1}
    assert file_path.read_text() == "print('Hello World')\nx = 1\n"
    logger.debug(f"Replaced lines fuzzily: {file_path.read_text()}")


def test_create_file(tmp_path, applicator):
    """Test creating a new file."""
    file_path = tmp_path / "new.py"
    changes = ApplydirChanges(
        file_entries=[
            FileEntry(
                file="new.py",
                action=ActionType.CREATE_FILE,
                changes=[{"original_lines": [], "changed_lines": ["print('New file')"]}],
            )
        ]
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_CHANGES_SUCCESSFUL
    assert errors[0].severity == ErrorSeverity.INFO
    assert errors[0].message == "All changes to file applied successfully"
    assert errors[0].details == {"file": str(file_path), "actions": ["create_file"], "change_count": 1}
    assert file_path.read_text() == "print('New file')\n"
    logger.debug(f"Created file: {file_path.read_text()}")


def test_delete_file(tmp_path, applicator):
    """Test deleting a file."""
    file_path = tmp_path / "old.py"
    file_path.write_text("print('Old file')\n")
    changes = ApplydirChanges(file_entries=[FileEntry(file="old.py", action=ActionType.DELETE_FILE, changes=[])])
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_CHANGES_SUCCESSFUL
    assert errors[0].severity == ErrorSeverity.INFO
    assert errors[0].message == "All changes to file applied successfully"
    assert errors[0].details == {"file": str(file_path), "actions": ["delete_file"], "change_count": 1}
    assert not file_path.exists()
    logger.debug("Deleted file successfully")


def test_create_file_exists(tmp_path, applicator):
    """Test creating a file that already exists produces FILE_ALREADY_EXISTS error."""
    file_path = tmp_path / "existing.py"
    file_path.write_text("print('Existing')\n")
    changes = ApplydirChanges(
        file_entries=[
            FileEntry(
                file="existing.py",
                action=ActionType.CREATE_FILE,
                changes=[{"original_lines": [], "changed_lines": ["print('New content')"]}],
            )
        ]
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_ALREADY_EXISTS
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "File already exists for new file creation"
    assert isinstance(errors[0].change, ApplydirFileChange)
    assert errors[0].change.changed_lines == ["print('New content')"]
    assert file_path.read_text() == "print('Existing')\n"  # File unchanged
    logger.debug(f"Create file exists error: {errors[0].message}")


def test_delete_file_not_found(tmp_path, applicator):
    """Test deleting a non-existent file produces FILE_NOT_FOUND error."""
    file_path = tmp_path / "non_existent.py"
    changes = ApplydirChanges(
        file_entries=[FileEntry(file="non_existent.py", action=ActionType.DELETE_FILE, changes=[])]
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_NOT_FOUND
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "File does not exist for deletion"
    assert isinstance(errors[0].change, ApplydirFileChange)
    assert errors[0].change.action == ActionType.DELETE_FILE
    logger.debug(f"Delete file not found error: {errors[0].message}")


def test_replace_lines_non_ascii_error(tmp_path, applicator):
    """Test non-ASCII in changed_lines triggers error in apply_changes if configured as error."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    change_dict = {
        "original_lines": ["print('Hello')"],
        "changed_lines": ["print('Hello😊')"],  # Non-ASCII 😊
    }
    changes = ApplydirChanges(
        file_entries=[FileEntry(file="main.py", action=ActionType.REPLACE_LINES, changes=[change_dict])]
    )

    print(f"applicator.config starts as: {json.dumps(applicator.config.as_dict(), indent=4)}")
    applicator.config.update(TEST_ASCII_CONFIG)
    print(f"applicator.config after update is: {json.dumps(applicator.config.as_dict(), indent=4)}")

    """applicator.config.update(
        {
            "validation": {"non_ascii": {"default": "error", "rules": [{"extensions": [".py"], "action": "error"}]}},
        }
    )"""
    errors = changes.validate_changes(tmp_path, config=applicator.config.as_dict())
    applicator.changes = changes
    errors = applicator.apply_changes()
    print("errors are: \n" + "\n".join([str(err) for err in errors]))
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.NON_ASCII_CHARS
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Non-ASCII characters found in changed_lines"
    assert isinstance(errors[0].change, ApplydirFileChange)
    assert errors[0].change.changed_lines == ["print('Hello😊')"]
    assert file_path.read_text() == "print('Hello')\n"  # File unchanged
    logger.debug(f"Non-ASCII error: {errors[0].message}")


def test_replace_lines_multiple_matches_no_fuzzy(tmp_path, applicator):
    """Test multiple matches with fuzzy disabled."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\nprint('Hello')\n")
    change_dict = {"original_lines": ["print('Hello')"], "changed_lines": ["print('Updated')"]}
    changes = ApplydirChanges(
        file_entries=[FileEntry(file="main.py", action=ActionType.REPLACE_LINES, changes=[change_dict])]
    )
    applicator.config.update(
        {
            "matching": {"use_fuzzy": {"default": False}},
        }
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.MULTIPLE_MATCHES
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Multiple matches found for original_lines"
    assert isinstance(errors[0].change, ApplydirFileChange)
    assert errors[0].change.changed_lines == ["print('Updated')"]
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
    errors = applicator.apply_changes()
    assert len(errors) == 3
    assert all(e.error_type == ErrorType.FILE_CHANGES_SUCCESSFUL for e in errors)
    assert all(e.severity == ErrorSeverity.INFO for e in errors)
    assert sorted([e.details["file"] for e in errors]) == sorted([str(file1), str(file2), str(file3)])
    assert errors[0].details["actions"] == ["replace_lines"]
    assert errors[0].details["change_count"] == 1
    assert errors[1].details["actions"] == ["delete_file"]
    assert errors[1].details["change_count"] == 1
    assert errors[2].details["actions"] == ["create_file"]
    assert errors[2].details["change_count"] == 1
    assert file1.read_text() == "print('New')\n"
    assert not file2.exists()
    assert file3.read_text() == "print('Created')\n"
    logger.debug("Applied multi-file changes: replace, delete, create")


def test_delete_file_with_changes_ignored(tmp_path, applicator):
    """Test DELETE_FILE with changes array produces warning and deletion occurs."""
    file_path = tmp_path / "old.py"
    file_path.write_text("print('Old file')\n")
    changes = ApplydirChanges(
        file_entries=[
            FileEntry(
                file="old.py",
                action=ActionType.DELETE_FILE,
                changes=[{"original_lines": ["print('Old file')"], "changed_lines": ["print('New content')"]}],
            )
        ]
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 2
    assert errors[0].error_type == ErrorType.INVALID_CHANGE
    assert errors[0].severity == ErrorSeverity.WARNING
    assert errors[0].message == "The original_lines and changed_lines should be empty for delete_file"
    assert isinstance(errors[0].change, ApplydirFileChange)
    assert errors[0].change.changed_lines == ["print('New content')"]
    assert errors[1].error_type == ErrorType.FILE_CHANGES_SUCCESSFUL
    assert errors[1].severity == ErrorSeverity.INFO
    assert errors[1].message == "All changes to file applied successfully"
    assert errors[1].details == {"file": str(file_path), "actions": ["delete_file"], "change_count": 1}
    assert not file_path.exists()
    logger.debug("DELETE_FILE with invalid changes produces warning and deletes successfully")


def test_delete_disabled(tmp_path, applicator):
    """Test deletion disabled in config produces PERMISSION_DENIED error."""
    file_path = tmp_path / "old.py"
    file_path.write_text("print('Old')\n")
    changes = ApplydirChanges(file_entries=[FileEntry(file="old.py", action=ActionType.DELETE_FILE, changes=[])])
    applicator.config.update({"allow_file_deletion": False})
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.PERMISSION_DENIED
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "File deletion is disabled in configuration"
    assert isinstance(errors[0].change, ApplydirFileChange)
    assert errors[0].change.action == ActionType.DELETE_FILE
    assert file_path.exists()  # File unchanged
    logger.debug(f"Delete disabled error: {errors[0].message}")


def test_file_system_error(tmp_path, applicator):
    """Test file system error (e.g., permission denied) produces FILE_SYSTEM error."""
    file_path = tmp_path / "protected.py"
    file_path.write_text("print('Protected')\n")
    file_path.chmod(0o444)  # Read-only
    change_dict = {"original_lines": ["print('Protected')"], "changed_lines": ["print('Updated')"]}
    changes = ApplydirChanges(
        file_entries=[FileEntry(file="protected.py", action=ActionType.REPLACE_LINES, changes=[change_dict])]
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_SYSTEM
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message.startswith("File operation failed")
    assert isinstance(errors[0].change, ApplydirFileChange)
    assert errors[0].change.changed_lines == ["print('Updated')"]
    assert file_path.read_text() == "print('Protected')\n"  # File unchanged
    logger.debug(f"File system error: {errors[0].message}")


def test_multiple_changes_single_file(tmp_path, applicator):
    """Test multiple changes in a single file produce one FILE_CHANGES_SUCCESSFUL."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\nx = 1\ny = 2\n")
    changes = ApplydirChanges(
        file_entries=[
            FileEntry(
                file="main.py",
                action=ActionType.REPLACE_LINES,
                changes=[
                    {"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]},
                    {"original_lines": ["x = 1"], "changed_lines": ["x = 10"]},
                ],
            )
        ]
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_CHANGES_SUCCESSFUL
    assert errors[0].severity == ErrorSeverity.INFO
    assert errors[0].message == "All changes to file applied successfully"
    assert errors[0].details == {"file": str(file_path), "actions": ["replace_lines"], "change_count": 2}
    assert file_path.read_text() == "print('Hello World')\nx = 10\ny = 2\n"
    logger.debug(f"Multiple changes single file: {file_path.read_text()}")


def test_mixed_success_failure_single_file(tmp_path, applicator):
    """Test mixed success and failure in a single file with change object in errors."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\nprint('Hello')\nx = 1\n")  # Notice duplicate print statement
    change_dict_failure = {"original_lines": ["print('Hello')"], "changed_lines": ["print('Updated')"]}
    change_dict_success = {"original_lines": ["x = 1"], "changed_lines": ["x = 10"]}
    changes = ApplydirChanges(
        file_entries=[
            FileEntry(
                file="main.py",
                action=ActionType.REPLACE_LINES,
                changes=[change_dict_failure, change_dict_success],
            )
        ]
    )
    applicator.config.update(
        {
            "matching": {"use_fuzzy": {"default": False}},
        }
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    print("errors are:\n" + "\n".join([str(err) for err in errors]))
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.MULTIPLE_MATCHES
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Multiple matches found for original_lines"
    assert isinstance(errors[0].change, ApplydirFileChange)
    assert errors[0].change.changed_lines == ["print('Updated')"]

    assert file_path.read_text() == "print('Hello')\nprint('Hello')\nx = 10\n"
    logger.debug(f"Mixed success/failure: {file_path.read_text()}")


def test_empty_changes_create_file(tmp_path, applicator):
    """Test CREATE_FILE with empty changed_lines produces CHANGED_LINES_EMPTY error."""
    file_path = tmp_path / "new.py"
    changes = ApplydirChanges(
        file_entries=[
            FileEntry(
                file="new.py", action=ActionType.CREATE_FILE, changes=[{"original_lines": [], "changed_lines": []}]
            )
        ]
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.CHANGED_LINES_EMPTY
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Empty changed_lines not allowed for create_file"
    assert isinstance(errors[0].change, ApplydirFileChange)
    assert errors[0].change.changed_lines == []
    assert not file_path.exists()
    logger.debug(f"Empty changed_lines for CREATE_FILE error: {errors[0].message}")


def test_empty_changes_replace_lines(tmp_path, applicator):
    """Test REPLACE_LINES with empty changes produces CHANGED_LINES_EMPTY and ORIG_LINES_EMPTY errors."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    changes = ApplydirChanges(
        file_entries=[
            FileEntry(
                file="main.py", action=ActionType.REPLACE_LINES, changes=[{"original_lines": [], "changed_lines": []}]
            )
        ]
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    assert len(errors) == 2
    assert errors[0].error_type == ErrorType.ORIG_LINES_EMPTY
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Empty original_lines not allowed for replace_lines"
    assert isinstance(errors[0].change, ApplydirFileChange)
    assert errors[0].change.changed_lines == []
    assert errors[1].error_type == ErrorType.CHANGED_LINES_EMPTY
    assert errors[1].severity == ErrorSeverity.ERROR
    assert errors[1].message == "Empty changed_lines not allowed for replace_lines"
    assert isinstance(errors[1].change, ApplydirFileChange)
    assert file_path.read_text() == "print('Hello')\n"  # File unchanged
    logger.debug(f"Empty changes for REPLACE_LINES error: {errors[0].message}, {errors[1].message}")


def test_malformed_change_dict(tmp_path, applicator):
    """Test malformed change_dict with None original_lines produces ORIG_LINES_EMPTY and CHANGED_LINES_EMPTY errors."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    changes = ApplydirChanges(
        file_entries=[
            FileEntry(
                file="main.py",
                action=ActionType.REPLACE_LINES,
                changes=[{"original_lines": None, "changed_lines": ["print('Updated')"]}],
            )
        ]
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    print("errors are:\n" + "\n".join([str(err) for err in errors]))
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.INVALID_CHANGE
    assert errors[0].severity == ErrorSeverity.ERROR
    assert "original_lines\n  Input should be a valid list" in errors[0].message
    assert errors[0].change is None

    assert file_path.read_text() == "print('Hello')\n"  # File unchanged


def test_invalid_action(tmp_path, applicator):
    """Test invalid action produces VaidationError."""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")
    with pytest.raises(ValidationError) as exc_info:
        ApplydirChanges(
            file_entries=[
                FileEntry(
                    file="main.py",
                    action="invalid_action",  # Invalid action
                    changes=[{"original_lines": ["print('Hello')"], "changed_lines": ["print('Updated')"]}],
                )
            ]
        )

    print(f"exc_info.value is {exc_info.value}")
    print(f"exc_info is {exc_info}")
    assert "1 validation error for FileEntry" in str(exc_info.value)
    assert "Invalid action: invalid_action" in str(exc_info.value)


def test_non_dict_change_dict(tmp_path, applicator):
    """Test non-dict change_dict produces ValidationError"""
    file_path = tmp_path / "main.py"
    file_path.write_text("print('Hello')\n")

    with pytest.raises(ValidationError) as exc_info:
        FileEntry(file="main.py", action=ActionType.REPLACE_LINES, changes=["invalid_change_dict"])

    print(f"exc_info.value is {exc_info.value}")
    print(f"exc_info is {exc_info}")
    assert "1 validation error for FileEntry" in str(exc_info.value)
    assert "Input should be a valid dictionary" in str(exc_info.value)

    assert file_path.read_text() == "print('Hello')\n"  # File unchanged


def test_replace_lines_fuzzy_sequence_matcher(tmp_path, applicator):
    """Test fuzzy matching with SequenceMatcher explicitly (expects failure due to high threshold)."""
    file_path = tmp_path / "main.py"
    file_path.write_text("Print('Helo') \nx = 1\n")
    changes = ApplydirChanges(
        file_entries=[
            FileEntry(
                file="main.py",
                action=ActionType.REPLACE_LINES,
                changes=[{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}],
            )
        ]
    )
    applicator.config.update(
        {
            "matching": {
                "whitespace": {"default": "collapse", "rules": [{"extensions": [".py"], "handling": "remove"}]},
                "similarity": {"default": 0.95, "rules": [{"extensions": [".py"], "threshold": 0.95}]},
                "similarity_metric": {
                    "default": "levenshtein",
                    "rules": [{"extensions": [".py"], "metric": "sequence_matcher"}],
                },
                "use_fuzzy": {"default": True, "rules": [{"extensions": [".py"], "use_fuzzy": True}]},
            },
            "allow_file_deletion": False,
        }
    )
    applicator.changes = changes
    errors = applicator.apply_changes()
    print("errors are: \n" + "\n".join([str(err) for err in errors]))
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.NO_MATCH  # SequenceMatcher fails due to ratio ~0.889 < 0.95
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "No matching lines found"
    assert file_path.read_text() == "Print('Helo') \nx = 1\n"  # File unchanged
    logger.debug(f"SequenceMatcher fuzzy match failed as expected: {file_path.read_text()}")
