import pytest
from pathlib import Path
from datetime import datetime
from prepdir.prepdir_processor import PrepdirProcessor
from applydir.prepdir_applicator import PrepdirApplicator
from prepdir.prepdir_output_file import PrepdirOutputFile
from prepdir.config import __version__
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture
def config():
    from dynaconf import Dynaconf
    return Dynaconf(
        settings_files=[],
        DEFAULT_EXTENSIONS=["py", "txt"],
        DEFAULT_OUTPUT_FILE="output.txt",
        EXCLUDE={
            "DIRECTORIES": ["__pycache__", "*.egg-info", "build", "dist"],
            "FILES": ["*.pyc", "*.pyo"],
        },
        SCRUB_HYPHENATED_UUIDS=True,
        SCRUB_HYPHENLESS_UUIDS=True,
        REPLACEMENT_UUID="00000000-0000-0000-0000-000000000000",
        USE_UNIQUE_PLACEHOLDERS=True,
        IGNORE_EXCLUSIONS=False,
        INCLUDE_PREPDIR_FILES=False,
        VERBOSE=True,
    )

@pytest.fixture
def temp_dir(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "file1.py").write_text(
        'print("Hello")\n# UUID: 123e4567-e89b-12d3-a456-426614174000\n', encoding="utf-8"
    )
    (project_dir / "file2.txt").write_text("Hello, World!\n", encoding="utf-8")
    yield project_dir

@pytest.fixture
def output_file(temp_dir, config):
    processor = PrepdirProcessor(directory=str(temp_dir), config_path=None, use_unique_placeholders=True)
    processor.config = config
    content = (
        f"File listing generated {datetime.now().isoformat()} by test_validator\n"
        f"Base directory is '{temp_dir}'\n\n"
        "=-=-= Begin File: 'file1.py' =-=-=\n"
        "print(\"Hello, modified\")\n# UUID: PREPDIR_UUID_PLACEHOLDER_1\n"
        "=-=-= End File: 'file1.py' =-=-=\n"
        "=-=-= Begin File: 'new_file.py' =-=-=\n"
        "print(\"New file\")\n"
        "=-=-= End File: 'new_file.py' =-=-=\n"
    )
    return processor.validate_output(
        content=content,
        metadata={"creator": "test_validator"},
        highest_base_directory=str(temp_dir),
    )

def test_apply_changes(temp_dir, config, output_file):
    applicator = PrepdirApplicator(highest_base_directory=str(temp_dir), verbose=True)
    failed_files = applicator.apply_changes(output_file)
    assert not failed_files
    assert (temp_dir / "file1.py").read_text(encoding="utf-8") == (
        "print(\"Hello, modified\")\n# UUID: 123e4567-e89b-12d3-a456-426614174000\n"
    )
    assert (temp_dir / "new_file.py").read_text(encoding="utf-8") == "print(\"New file\")\n"

def test_apply_changes_dry_run(temp_dir, config, output_file, caplog):
    applicator = PrepdirApplicator(highest_base_directory=str(temp_dir), verbose=True)
    with caplog.at_level(logging.INFO):
        failed_files = applicator.apply_changes(output_file, dry_run=True)
    assert not failed_files
    assert "Dry run: Would write to" in caplog.text
    assert "print(\"Hello, modified\")" in caplog.text
    assert (temp_dir / "file1.py").read_text(encoding="utf-8") == (
        "print(\"Hello\")\n# UUID: 123e4567-e89b-12d3-a456-426614174000\n"
    )
    assert not (temp_dir / "new_file.py").exists()

def test_apply_changes_path_outside_highest_base(temp_dir, config):
    content = (
        f"File listing generated {datetime.now().isoformat()} by test_validator\n"
        f"Base directory is '{temp_dir}'\n\n"
        "=-=-= Begin File: '../outside.py' =-=-=\n"
        "print(\"Outside\")\n"
        "=-=-= End File: '../outside.py' =-=-=\n"
    )
    processor = PrepdirProcessor(directory=str(temp_dir), config_path=None, use_unique_placeholders=True)
    processor.config = config
    output = processor.validate_output(content=content, highest_base_directory=str(temp_dir))
    applicator = PrepdirApplicator(highest_base_directory=str(temp_dir), verbose=True)
    failed_files = applicator.apply_changes(output)
    assert failed_files == ["../outside.py"]

def test_get_diffs(temp_dir, config, output_file):
    applicator = PrepdirApplicator(highest_base_directory=str(temp_dir), verbose=True)
    diffs = applicator.get_diffs(output_file)
    assert "file1.py" in diffs
    assert "new_file.py" in diffs
    assert "-print(\"Hello\")" in diffs["file1.py"]
    assert "+print(\"Hello, modified\")" in diffs["file1.py"]
    assert "print(\"New file\")" in diffs["new_file.py"]

def test_list_changed_files(temp_dir, config, output_file):
    applicator = PrepdirApplicator(highest_base_directory=str(temp_dir), verbose=True)
    changed_files = applicator.list_changed_files(output_file)
    assert sorted(changed_files) == ["file1.py", "new_file.py"]

def test_list_new_files(temp_dir, config, output_file):
    applicator = PrepdirApplicator(highest_base_directory=str(temp_dir), verbose=True)
    new_files = applicator.list_new_files(output_file)
    assert new_files == ["new_file.py"]

if __name__ == "__main__":
    pytest.main([__file__])