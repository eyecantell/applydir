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
def setup_file(tmp_path):
    """Create a temporary file with content."""
    file_path = tmp_path / "main.py"
    return file_path

@pytest.fixture
def applicator(tmp_path):
    """Create an ApplydirApplicator instance."""
    return ApplydirApplicator(
        base_dir=str(tmp_path),
        changes=None,
        matcher=ApplydirMatcher(),
        logger=logger
    )

def test_apply_replace_lines_exact(setup_file, applicator):
    """Test replacing lines with exact match."""
    file_path = setup_file
    file_path.write_text("print('Hello')\nx = 1\n")
    change = ApplydirFileChange(
        file="main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=file_path.parent,
        action=ActionType.REPLACE_LINES,
    )
    config = {
        "matching": {
            "whitespace": {"default": "collapse", "rules": [{"extensions": [".py"], "handling": "remove"}]},
            "use_fuzzy": {"default": True, "rules": [{"extensions": [".py"], "use_fuzzy": False}]}
        },
        "allow_file_deletion": False
    }
    errors = applicator.apply_single_change(file_path, change, config)
    assert len(errors) == 0
    assert file_path.read_text() == "print('Hello World')\nx = 1\n"
    logger.debug(f"Replaced lines exactly: {file_path.read_text()}")

def test_apply_replace_lines_fuzzy(setup_file, applicator):
    """Test replacing lines with fuzzy match."""
    file_path = setup_file
    file_path.write_text("Print('Helo') \nx = 1\n")
    change = ApplydirFileChange(
        file="main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=file_path.parent,
        action=ActionType.REPLACE_LINES,
    )
    config = {
        "matching": {
            "whitespace": {"default": "collapse", "rules": [{"extensions": [".py"], "handling": "remove"}]},
            "similarity": {"default": 0.95, "rules": [{"extensions": [".py"], "threshold": 0.5}]},
            "similarity_metric": {"default": "sequence_matcher", "rules": [{"extensions": [".py"], "metric": "levenshtein"}]},
            "use_fuzzy": {"default": True, "rules": [{"extensions": [".py"], "use_fuzzy": True}]}
        },
        "allow_file_deletion": False
    }
    errors = applicator.apply_single_change(file_path, change, config)
    assert len(errors) == 0
    assert file_path.read_text() == "print('Hello World')\nx = 1\n"
    logger.debug(f"Replaced lines fuzzily: {file_path.read_text()}")

def test_apply_create_file(tmp_path, applicator):
    """Test creating a new file."""
    file_path = tmp_path / "new.py"
    change = ApplydirFileChange(
        file="new.py",
        original_lines=[],
        changed_lines=["print('New file')"],
        base_dir=tmp_path,
        action=ActionType.CREATE_FILE,
    )
    config = {"allow_file_deletion": False}
    errors = applicator.apply_single_change(file_path, change, config)
    assert len(errors) == 0
    assert file_path.exists()
    assert file_path.read_text() == "print('New file')\n"
    logger.debug(f"Created file: {file_path.read_text()}")

def test_apply_delete_file(setup_file, applicator):
    """Test deleting a file with allow_file_deletion=True."""
    file_path = setup_file
    file_path.write_text("print('Hello')\n")
    change = ApplydirFileChange(
        file="main.py",
        original_lines=[],
        changed_lines=[],
        base_dir=file_path.parent,
        action=ActionType.DELETE_FILE,
    )
    config = {"allow_file_deletion": True}
    errors = applicator.apply_single_change(file_path, change, config)
    assert len(errors) == 0
    assert not file_path.exists()
    logger.debug(f"Deleted file: {file_path}")

def test_apply_delete_file_not_allowed(setup_file, applicator):
    """Test deleting a file with allow_file_deletion=False."""
    file_path = setup_file
    file_path.write_text("print('Hello')\n")
    change = ApplydirFileChange(
        file="main.py",
        original_lines=[],
        changed_lines=[],
        base_dir=file_path.parent,
        action=ActionType.DELETE_FILE,
    )
    config = {"allow_file_deletion": False}
    errors = applicator.apply_single_change(file_path, change, config)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.PERMISSION_DENIED
    assert errors[0].severity == ErrorSeverity.ERROR
    assert "File deletion is disabled in configuration" in errors[0].message
    assert file_path.exists()
    logger.debug(f"Deletion blocked: {errors[0].message}")

def test_apply_replace_lines_no_match(setup_file, applicator):
    """Test replace_lines when no match is found."""
    file_path = setup_file
    file_path.write_text("x = 1\n")
    change = ApplydirFileChange(
        file="main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=file_path.parent,
        action=ActionType.REPLACE_LINES,
    )
    config = {
        "matching": {
            "whitespace": {"default": "collapse", "rules": [{"extensions": [".py"], "handling": "remove"}]},
            "use_fuzzy": {"default": True, "rules": [{"extensions": [".py"], "use_fuzzy": True}]}
        },
        "allow_file_deletion": False
    }
    errors = applicator.apply_single_change(file_path, change, config)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.NO_MATCH
    assert errors[0].severity == ErrorSeverity.ERROR
    assert "No matching lines found" in errors[0].message
    assert file_path.read_text() == "x = 1\n"
    logger.debug(f"No match error: {errors[0].message}")

def test_apply_replace_lines_multiple_matches(setup_file, applicator):
    """Test replace_lines when multiple matches are found."""
    file_path = setup_file
    file_path.write_text("print('Hello')\nx = 1\nprint('Hello')\n")
    change = ApplydirFileChange(
        file="main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=file_path.parent,
        action=ActionType.REPLACE_LINES,
    )
    config = {
        "matching": {
            "whitespace": {"default": "collapse", "rules": [{"extensions": [".py"], "handling": "remove"}]},
            "use_fuzzy": {"default": True, "rules": [{"extensions": [".py"], "use_fuzzy": False}]}
        },
        "allow_file_deletion": False
    }
    errors = applicator.apply_single_change(file_path, change, config)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.MULTIPLE_MATCHES
    assert errors[0].severity == ErrorSeverity.ERROR
    assert "Multiple matches found" in errors[0].message
    assert file_path.read_text() == "print('Hello')\nx = 1\nprint('Hello')\n"
    logger.debug(f"Multiple matches error: {errors[0].message}")

def test_apply_file_not_found(tmp_path, applicator):
    """Test applying a change to a non-existent file."""
    file_path = tmp_path / "missing.py"
    change = ApplydirFileChange(
        file="missing.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        base_dir=tmp_path,
        action=ActionType.REPLACE_LINES,
    )
    config = {
        "matching": {
            "whitespace": {"default": "collapse", "rules": [{"extensions": [".py"], "handling": "remove"}]},
            "use_fuzzy": {"default": True, "rules": [{"extensions": [".py"], "use_fuzzy": True}]}
        },
        "allow_file_deletion": False
    }
    errors = applicator.apply_single_change(file_path, change, config)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.FILE_PATH
    assert errors[0].severity == ErrorSeverity.ERROR
    assert "File does not exist" in errors[0].message
    assert not file_path.exists()
    logger.debug(f"File not found error: {errors[0].message}")

def test_apply_replace_lines_non_ascii_error(setup_file, applicator):
    """Test non-ASCII in changed_lines triggers error per config."""
    file_path = setup_file
    file_path.write_text("print('Hello')\n")
    change = ApplydirFileChange(
        file="main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Héllo')"],  # Non-ASCII é
        base_dir=file_path.parent,
        action=ActionType.REPLACE_LINES,
    )
    config = {
        "validation": {"non_ascii": {"default": "error", "rules": [{"extensions": [".py"], "action": "error"}]}},
    }
    errors = change.validate_change(config.get("validation", {}))
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.SYNTAX
    assert errors[0].severity == ErrorSeverity.ERROR
    assert "Non-ASCII characters found" in errors[0].message
    logger.debug(f"Non-ASCII error: {errors[0].message}")

def test_apply_replace_lines_multiple_matches_no_fuzzy(setup_file, applicator):
    """Test multiple matches with fuzzy disabled."""
    file_path = setup_file
    file_path.write_text("print('Hello')\nprint('Hello')\n")
    change = ApplydirFileChange(
        file="main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Updated')"],
        base_dir=file_path.parent,
        action=ActionType.REPLACE_LINES,
    )
    config = {
        "matching": {
            "use_fuzzy": {"default": False}
        },
    }
    errors = applicator.apply_single_change(file_path, change, config)
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.MULTIPLE_MATCHES
    assert errors[0].severity == ErrorSeverity.ERROR
    assert "Multiple matches found" in errors[0].message
    assert file_path.read_text() == "print('Hello')\nprint('Hello')\n"
    logger.debug(f"Multiple matches no fuzzy error: {errors[0].message}")

def test_apply_multiple_files(tmp_path, applicator):
    """Test applying changes to multiple files (replace, create, delete)."""
    file1 = tmp_path / "file1.py"
    file2 = tmp_path / "file2.py"
    file3 = tmp_path / "file3.py"
    file1.write_text("print('Old')\n")
    file2.write_text("x = 1\n")
    
    changes = ApplydirChanges(files=[
        FileEntry(
            file="file1.py",
            action=ActionType.REPLACE_LINES,
            changes=[{
                "original_lines": ["print('Old')"],
                "changed_lines": ["print('New')"]
            }]
        ),
        FileEntry(
            file="file2.py",
            action=ActionType.DELETE_FILE,
            changes=[]
        ),
        FileEntry(
            file="file3.py",
            action=ActionType.CREATE_FILE,
            changes=[{
                "original_lines": [],
                "changed_lines": ["print('Created')"]
            }]
        )
    ])
    applicator.changes = changes
    val_errors = changes.validate_changes(base_dir=str(tmp_path))
    assert len(val_errors) == 0
    app_errors = applicator.apply_changes()
    assert len(app_errors) == 0
    assert file1.read_text() == "print('New')\n"
    assert not file2.exists()
    assert file3.read_text() == "print('Created')\n"
    logger.debug("Applied multi-file changes: replace, delete, create")