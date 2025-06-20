import logging
from io import StringIO
from unittest.mock import mock_open, patch
import pytest
from dynaconf import Dynaconf
from pathlib import Path
from applydir.applydir import apply_changes, parse_prepped_dir, setup_logging, execute_commands
from applydir.file_for_applydir import FileForApplyDir
from applydir.config import load_config

@pytest.fixture
def sample_prepped_dir_content():
    return """File listing generated 2025-06-07 03:56:22.143067 by prepdir
Base directory is '/mounted/dev/applydir'
=-= Begin File: 'test_file.py' =-=
print("Hello, World!")
=-= End File: 'test_file.py' =-=
===---=== Begin File: 'new_file.py' =
print("New content")
====----==== End File: 'new_file.py' ====
====----==== Begin Additional Commands =
git commit -m "Apply changes"
=-= End Additional Commands ===--
"""

@pytest.fixture
def sample_config_content():
    return Dynaconf(
        settings_files=[],
        APPLY_CHANGES={"AUTO_APPLY": False},
        COMMANDS={"SHELL_TYPE": "bash"},
        LOGGING={"LEVEL": "INFO"},
    )

@pytest.fixture
def capture_log(sample_config_content):
    """Capture logging output."""
    log_output = StringIO()
    handler = logging.StreamHandler(log_output)
    setup_logging(sample_config_content, handler)
    yield log_output
    # Reset logging configuration
    logger = logging.getLogger()
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    logger.setLevel(logging.NOTSET)

def test_parse_prepped_dir(sample_prepped_dir_content):
    """Test parsing of prepped_dir.txt into files and commands with flexible delimiters."""
    with patch("builtins.open", mock_open(read_data=sample_prepped_dir_content)):
        files, commands = parse_prepped_dir("dummy_path.txt", Path("/mounted/dev/applydir"), {})

    assert len(files) == 2
    assert files[0].relative_path == "test_file.py"
    assert files[0].modified_content == 'print("Hello, World!")'
    assert files[1].relative_path == "new_file.py"
    assert files[1].modified_content == 'print("New content")'
    assert commands == ['git commit -m "Apply changes"']

def test_parse_prepped_dir_varied_delimiters():
    """Test parsing with different delimiter styles."""
    varied_content = """File listing generated 2025-06-07 by prepdir
Base directory is '/mounted/dev/applydir'
=-= Begin File: 'test_file.py' =
print("Hello, World!")
===---=== End File: 'test_file.py' ===---===
====----==== Begin File: 'new_file.py' ====
print("New content")
=-= End File: 'new_file.py' ==
=-= Begin Additional Commands =-=
git commit -m "Apply changes"
===---=== End Additional Commands =-=-=
"""
    with patch("builtins.open", mock_open(read_data=varied_content)):
        files, commands = parse_prepped_dir("dummy_path.txt", Path("/mounted/dev/applydir"), {})

    assert len(files) == 2
    assert files[0].relative_path == "test_file.py"
    assert files[0].modified_content == 'print("Hello, World!")'
    assert files[1].relative_path == "new_file.py"
    assert files[1].modified_content == 'print("New content")'
    assert commands == ['git commit -m "Apply changes"']

def test_parse_prepped_dir_mismatched_end_file():
    """Test parsing with mismatched End File marker filename raises ValueError."""
    mismatched_content = """File listing generated 2025-06-07 by prepdir
Base directory is '/mounted/dev/applydir'
=-= Begin File: 'test_file.py' =-=
print("Hello, World!")
=-= End File: 'wrong_file.py' =-=
"""
    with patch("builtins.open", mock_open(read_data=mismatched_content)):
        with pytest.raises(
            ValueError, match=r"Mismatched End File marker: expected 'test_file.py', got 'wrong_file.py'"
        ):
            parse_prepped_dir("dummy_path.txt", Path("/mounted/dev/applydir"), {})

def test_parse_prepped_dir_empty_file():
    """Test parsing an empty prepped_dir.txt."""
    with patch("builtins.open", mock_open(read_data="")):
        files, commands = parse_prepped_dir("dummy_path.txt", Path("/mounted/dev/applydir"), {})

    assert files == []
    assert commands == []

def test_compare_files():
    """Test comparing original and modified files."""
    base_dir = Path("/tmp")
    files = [
        FileForApplyDir("test_file.py", base_dir, 'print("Updated World!")', 'print("Hello, World!")'),
        FileForApplyDir("unchanged.py", base_dir, "print('same')", "print('same')"),
        FileForApplyDir("new_file.py", base_dir, 'print("New content")', None)
    ]
    updates = [f for f in files if not f.is_new and f.has_changes()]
    new_files = [f for f in files if f.is_new]

    assert len(updates) == 1
    assert updates[0].relative_path == "test_file.py"
    assert len(new_files) == 1
    assert new_files[0].relative_path == "new_file.py"

def test_show_diff(capsys):
    """Test displaying unified diff."""
    base_dir = Path("/tmp")
    file_obj = FileForApplyDir("test.py", base_dir, 'print("Updated World!")', 'print("Hello, World!")')
    file_obj.compute_diff()
    print("".join(file_obj.diff))
    captured = capsys.readouterr()

    assert "Original: test.py" in captured.out
    assert "Modified: test.py" in captured.out
    assert '-print("Hello, World!")' in captured.out
    assert '+print("Updated World!")' in captured.out

def test_apply_changes_interactive(tmp_path, sample_config_content, capsys, capture_log):
    """Test applying changes interactively with user input."""
    base_dir = tmp_path / "codebase"
    base_dir.mkdir()
    original_file = base_dir / "test_file.py"
    original_file.write_text('print("Hello, World!")')

    files = [
        FileForApplyDir("test_file.py", base_dir, 'print("Updated World!")', 'print("Hello, World!")'),
        FileForApplyDir("new_file.py", base_dir, 'print("New content")', None)
    ]
    commands = ['git commit -m "Apply changes"']

    with patch("builtins.input", side_effect=["y", "y", ""]):
        apply_changes(files, commands, sample_config_content, dry_run=False, selected_files=["-all"], execute_commands_flag=False)

    assert original_file.read_text() == 'print("Updated World!")'
    assert (base_dir / "new_file.py").read_text() == 'print("New content")'

    captured = capsys.readouterr()
    assert "Proposed changes for test_file.py" in captured.out
    assert "New file proposed: new_file.py" in captured.out
    assert "Proposed additional commands (bash)" in captured.out
    assert 'git commit -m "Apply changes"' in captured.out
    assert "Skipped command execution" in captured.out

    log_output = capture_log.getvalue()
    assert "Proposed changes for test_file.py" in log_output
    assert "Updated test_file.py" in log_output
    assert "Created new_file.py" in log_output
    assert "Skipped command execution" in log_output

def test_apply_changes_auto_apply(tmp_path, sample_config_content, capsys, capture_log):
    """Test applying changes automatically."""
    base_dir = tmp_path / "codebase"
    base_dir.mkdir()
    original_file = base_dir / "test_file.py"
    original_file.write_text('print("Hello, World!")')

    files = [
        FileForApplyDir("test_file.py", base_dir, 'print("Updated World!")', 'print("Hello, World!")'),
        FileForApplyDir("new_file.py", base_dir, 'print("New content")', None)
    ]
    commands = ['git commit -m "Apply changes"']

    config = Dynaconf(
        settings_files=[],
        APPLY_CHANGES={"AUTO_APPLY": True},
        COMMANDS={"SHELL_TYPE": "bash"},
        LOGGING={"LEVEL": "INFO"},
    )

    apply_changes(files, commands, config, dry_run=False, selected_files=["-all"], execute_commands_flag=False)

    assert original_file.read_text() == 'print("Updated World!")'
    assert (base_dir / "new_file.py").read_text() == 'print("New content")'

    captured = capsys.readouterr()
    assert "Automatically updated test_file.py" in captured.out
    assert "Automatically created new_file.py" in captured.out
    assert "Proposed additional commands (bash)" in captured.out
    assert "Skipped command execution" in captured.out

    log_output = capture_log.getvalue()
    assert "Automatically updated test_file.py" in log_output
    assert "Automatically created new_file.py" in log_output
    assert "Skipped command execution" in log_output

def test_apply_changes_dry_run(tmp_path, sample_config_content, capsys, capture_log):
    """Test dry-run mode."""
    base_dir = tmp_path / "codebase"
    base_dir.mkdir()
    original_file = base_dir / "test_file.py"
    original_file.write_text('print("Hello, World!")')

    files = [
        FileForApplyDir("test_file.py", base_dir, 'print("Updated World!")', 'print("Hello, World!")'),
        FileForApplyDir("new_file.py", base_dir, 'print("New content")', None)
    ]
    commands = ['git commit -m "Apply changes"']

    apply_changes(files, commands, sample_config_content, dry_run=True, selected_files=["-all"], execute_commands_flag=False)

    assert original_file.read_text() == 'print("Hello, World!")'  # Original unchanged
    assert not (base_dir / "new_file.py").exists()  # New file not created

    captured = capsys.readouterr()
    assert "Dry run: Would update test_file.py" in captured.out
    assert "Dry run: Would create new_file.py" in captured.out
    assert "Dry run: Commands not executed" in captured.out

    log_output = capture_log.getvalue()
    assert "Dry run: Would update test_file.py" in log_output
    assert "Dry run: Would create new_file.py" in log_output
    assert "Dry run: Commands not executed" in log_output

def test_load_config(tmp_path):
    """Test loading and validating configuration."""
    config_content = """
APPLY_CHANGES:
  AUTO_APPLY: false
COMMANDS:
  SHELL_TYPE: "bash"
LOGGING:
  LEVEL: "INFO"
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)

    config = load_config("applydir", str(config_path))

    assert config.APPLY_CHANGES.AUTO_APPLY is False
    assert config.COMMANDS.SHELL_TYPE == "bash"
    assert config.LOGGING.LEVEL == "INFO"

def test_load_config_invalid_shell(tmp_path):
    """Test handling invalid shell_type in config."""
    config_content = """
APPLY_CHANGES:
  AUTO_APPLY: false
COMMANDS:
  SHELL_TYPE: "invalid"
LOGGING:
  LEVEL: "INFO"
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)

    config = load_config("applydir", str(config_path))

    assert config.COMMANDS.SHELL_TYPE == "bash"  # Defaults to bash

def test_load_config_precedence(tmp_path):
    """Test configuration file precedence."""
    custom_config = tmp_path / "custom_config.yaml"
    custom_config.write_text("""
APPLY_CHANGES:
  AUTO_APPLY: true
COMMANDS:
  SHELL_TYPE: "powershell"
LOGGING:
  LEVEL: "DEBUG"
""")

    local_config = tmp_path / ".applydir" / "config.yaml"
    local_config.parent.mkdir()
    local_config.write_text("""
APPLY_CHANGES:
  AUTO_APPLY: false
COMMANDS:
  SHELL_TYPE: "cmd"
LOGGING:
  LEVEL: "WARNING"
""")

    config = load_config("applydir", str(custom_config))

    assert config.APPLY_CHANGES.AUTO_APPLY is True
    assert config.COMMANDS.SHELL_TYPE == "powershell"
    assert config.LOGGING.LEVEL == "DEBUG"

def test_file_for_applydir_restore_uuids(tmp_path, sample_config_content):
    """Test UUID restoration in FileForApplyDir."""
    base_dir = tmp_path / "codebase"
    base_dir.mkdir()
    uuid_mapping = {"PREPDIR_UUID_PLACEHOLDER_1": "123e4567-e89b-12d3-a456-426614174000"}
    file_obj = FileForApplyDir(
        relative_path="test.py",
        base_dir=base_dir,
        modified_content='print("UUID: PREPDIR_UUID_PLACEHOLDER_1")',
        original_content='print("UUID: 123e4567-e89b-12d3-a456-426614174000")',
        uuid_mapping=uuid_mapping
    )
    file_obj.restore_uuids()
    assert file_obj.modified_content == 'print("UUID: 123e4567-e89b-12d3-a456-426614174000")'

def test_file_for_applydir_apply_changes_auto(tmp_path, sample_config_content, capsys):
    """Test applying changes automatically."""
    base_dir = tmp_path / "codebase"
    base_dir.mkdir()
    original_file = base_dir / "test.py"
    original_file.write_text('print("Original")')

    file_obj = FileForApplyDir(
        relative_path="test.py",
        base_dir=base_dir,
        modified_content='print("Updated")',
        original_content='print("Original")'
    )
    file_obj.apply_changes(dry_run=False, auto_apply=True)
    assert file_obj.is_updated
    assert original_file.read_text() == 'print("Updated")'
    captured = capsys.readouterr()
    assert "Automatically updated test.py" in captured.out

def test_parse_prepped_dir_with_uuids(sample_config_content, tmp_path):
    """Test parsing prepped_dir.txt with UUID restoration."""
    prepped_content = """File listing generated 2025-06-20 by prepdir
Base directory is '/codebase'
=-=-=-= Begin File: 'test.py' =-=-=-=
print("UUID: PREPDIR_UUID_PLACEHOLDER_1")
=-=-=-= End File: 'test.py' =-=-=-=
=-=-=-= Begin Additional Commands =-=-=-=
git commit -m "Update"
=-=-=-= End Additional Commands =-=-=-=
"""
    prepped_file = tmp_path / "prepped_dir.txt"
    prepped_file.write_text(prepped_content)
    base_dir = tmp_path / "codebase"
    base_dir.mkdir()
    (base_dir / "test.py").write_text('print("UUID: 123e4567-e89b-12d3-a456-426614174000")')
    uuid_mapping = {"PREPDIR_UUID_PLACEHOLDER_1": "123e4567-e89b-12d3-a456-426614174000"}

    files, commands = parse_prepped_dir(str(prepped_file), base_dir, uuid_mapping)
    assert len(files) == 1
    assert files[0].modified_content == 'print("UUID: 123e4567-e89b-12d3-a456-426614174000")'
    assert commands == ['git commit -m "Update"']

def test_apply_changes_selective(tmp_path, sample_config_content):
    """Test applying changes to selected files."""
    base_dir = tmp_path / "codebase"
    base_dir.mkdir()
    (base_dir / "file1.py").write_text('print("Original1")')
    (base_dir / "file2.py").write_text('print("Original2")')

    files = [
        FileForApplyDir("file1.py", base_dir, 'print("Updated1")', 'print("Original1")'),
        FileForApplyDir("file2.py", base_dir, 'print("Updated2")', 'print("Original2")')
    ]
    with patch("builtins.input", side_effect=["y"]):
        apply_changes(files, [], sample_config_content, dry_run=False, selected_files=["file1.py"])
    assert (base_dir / "file1.py").read_text() == 'print("Updated1")'
    assert (base_dir / "file2.py").read_text() == 'print("Original2")'

def test_execute_commands_dry_run(sample_config_content, capsys):
    """Test command execution in dry-run mode."""
    commands = ['echo "Test"']
    execute_commands(commands, "bash", dry_run=True)
    captured = capsys.readouterr()
    assert "Dry run: Would execute: echo \"Test\"" in captured.out