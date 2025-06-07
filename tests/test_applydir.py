import pytest
import os
from pathlib import Path
from unittest.mock import mock_open, patch
from applydir.applydir import parse_prepped_dir, compare_files, show_diff, apply_changes, load_config, setup_logging
import yaml
import logging
from io import StringIO

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
    return {
        "apply_changes": {"auto_apply": False},
        "commands": {"shell_type": "bash"},
        "logging": {"level": "INFO"}
    }

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
        files, commands = parse_prepped_dir("dummy_path.txt")
    
    assert len(files) == 2
    assert files["test_file.py"] == 'print("Hello, World!")'
    assert files["new_file.py"] == 'print("New content")'
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
        files, commands = parse_prepped_dir("dummy_path.txt")
    
    assert len(files) == 2
    assert files["test_file.py"] == 'print("Hello, World!")'
    assert files["new_file.py"] == 'print("New content")'
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
        with pytest.raises(ValueError, match=r"Mismatched End File marker: expected 'test_file.py', got 'wrong_file.py'"):
            parse_prepped_dir("dummy_path.txt")

def test_parse_prepped_dir_empty_file():
    """Test parsing an empty prepped_dir.txt."""
    with patch("builtins.open", mock_open(read_data="")):
        files, commands = parse_prepped_dir("dummy_path.txt")
    
    assert files == {}
    assert commands == []

def test_compare_files():
    """Test comparing original and modified files."""
    original = {
        "test_file.py": 'print("Hello, World!")',
        "unchanged.py": "print('same')"
    }
    modified = {
        "test_file.py": 'print("Updated World!")',
        "unchanged.py": "print('same')",
        "new_file.py": 'print("New content")'
    }
    updates, new_files = compare_files(original, modified)
    
    assert updates == {"test_file.py": 'print("Updated World!")'}
    assert new_files == {"new_file.py": 'print("New content")'}

def test_show_diff(capsys):
    """Test displaying unified diff."""
    original = 'print("Hello, World!")\n'
    modified = 'print("Updated World!")\n'
    show_diff(original, modified, "test_file.py")
    captured = capsys.readouterr()
    
    assert "Original: test_file.py" in captured.out
    assert "Modified: test_file.py" in captured.out
    assert '-print("Hello, World!")' in captured.out
    assert '+print("Updated World!")' in captured.out

def test_apply_changes_interactive(tmp_path, sample_config_content, capsys, capture_log):
    """Test applying changes interactively with user input."""
    base_dir = tmp_path / "codebase"
    base_dir.mkdir()
    original_file = base_dir / "test_file.py"
    original_file.write_text('print("Hello, World!")')
    
    updates = {"test_file.py": 'print("Updated World!")'}
    new_files = {"new_file.py": 'print("New content")'}
    commands = ['git commit -m "Apply changes"']
    
    with patch("builtins.input", side_effect=["y", "y", ""]):
        apply_changes(updates, new_files, commands, str(base_dir), sample_config_content, dry_run=False)
    
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
    
    updates = {"test_file.py": 'print("Updated World!")'}
    new_files = {"new_file.py": 'print("New content")'}
    commands = ['git commit -m "Apply changes"']
    
    config = sample_config_content.copy()
    config["apply_changes"]["auto_apply"] = True
    
    apply_changes(updates, new_files, commands, str(base_dir), config, dry_run=False)
    
    assert original_file.read_text() == 'print("Updated World!")'
    assert (base_dir / "new_file.py").read_text() == 'print("New content")'
    
    captured = capsys.readouterr()
    assert "Automatically updated test_file.py" in captured.out
    assert "Automatically created new_file.py" in captured.out
    assert "Commands not executed automatically in auto_apply mode" in captured.out
    
    log_output = capture_log.getvalue()
    assert "Automatically updated test_file.py" in log_output
    assert "Automatically created new_file.py" in log_output
    assert "Commands not executed automatically in auto_apply mode" in log_output

def test_apply_changes_dry_run(tmp_path, sample_config_content, capsys, capture_log):
    """Test dry-run mode."""
    base_dir = tmp_path / "codebase"
    base_dir.mkdir()
    original_file = base_dir / "test_file.py"
    original_file.write_text('print("Hello, World!")')
    
    updates = {"test_file.py": 'print("Updated World!")'}
    new_files = {"new_file.py": 'print("New content")'}
    commands = ['git commit -m "Apply changes"']
    
    apply_changes(updates, new_files, commands, str(base_dir), sample_config_content, dry_run=True)
    
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

def test_load_config(sample_config_content):
    """Test loading and validating configuration."""
    config_yaml = yaml.dump(sample_config_content)
    with patch("builtins.open", mock_open(read_data=config_yaml)):
        config = load_config("dummy_config.yaml")
    
    assert config["apply_changes"]["auto_apply"] is False
    assert config["commands"]["shell_type"] == "bash"
    assert config["logging"]["level"] == "INFO"

def test_load_config_invalid_shell(sample_config_content):
    """Test handling invalid shell_type in config."""
    invalid_config = sample_config_content.copy()
    invalid_config["commands"]["shell_type"] = "invalid"
    config_yaml = yaml.dump(invalid_config)
    with patch("builtins.open", mock_open(read_data=config_yaml)):
        config = load_config("dummy_config.yaml")
    
    assert config["commands"]["shell_type"] == "bash"  # Defaults to bash

def test_load_config_missing_file():
    """Test handling missing config file."""
    logger = logging.getLogger()
    original_level = logger.level
    original_handlers = logger.handlers[:]
    
    with patch("builtins.open", side_effect=FileNotFoundError):
        config = load_config("dummy_config.yaml")
    
    assert config["apply_changes"]["auto_apply"] is False
    assert config["commands"]["shell_type"] == "bash"
    
    # Restore original logging configuration
    logger.setLevel(original_level)
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    for h in original_handlers:
        logger.addHandler(h)