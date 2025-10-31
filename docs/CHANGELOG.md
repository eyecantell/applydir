# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Links
- [README](https://github.com/eyecantell/applydir/blob/main/README.md)
- [GitHub Repository](https://github.com/eyecantell/applydir)
- [PyPI](https://pypi.org/project/applydir/)
- [Dynaconf Documentation](https://dynaconf.com)

## [0.5.0] - 2025-10-30
### Added

- Optional top-level message field in JSON input for Git commit messages, with validation (non-empty string if provided).
- New ApplydirResult dataclass returned by ApplydirApplicator.apply_changes(), including errors, commit_message, and success flag.
- Configurable include_commit_message parameter in applydir_format_description to control LLM prompting for commit messages.
- Logging of available commit message in CLI output on successful application.

### Changed

- Updated ApplydirChanges model to parse and validate the new message field.
- Modified ApplydirApplicator and main.py to handle the new ApplydirResult return type.
- Adjusted Pydantic validator signatures in ApplydirChanges for compatibility and proper error handling.
- Updated tests in tests/test_main.py to cover commit message handling, multi-line support, validation errors, and mixed severity results.

### Fixed

- Consistent error handling and logging for invalid JSON structures, including empty file_entries and invalid commit messages.

## [0.4.0] - 2025-10-04

### Added
- New `applydir_format_description` function in `applydir_format.py` to generate a prompt for LLMs, guiding them to produce `applydir`-compatible JSON changes for `vibedir` integration.
  - Includes a `filename` parameter (default: `"applydir_changes.json"`) to specify the output JSON file.
  - Directly addresses the LLM with instructions to return JSON in the specified file, separate from other output.
  - Provides a detailed description of the JSON format, including top-level structure, file entry structure, change object structure, constraints, and additional notes.
  - Features a valid example JSON with multiple `replace_lines` changes, a `create_file` action, and a `delete_file` action.
  - Includes guidance on multiple changes for `replace_lines` and avoiding overlapping `original_lines` in `replace_lines` changes.

### Changed
- Streamlined `applydir_format_description` to reduce redundancy in "Constraints and Validation" and "Additional Notes" sections, optimizing token usage for LLM prompts.
- Corrected example JSON syntax in `applydir_format_description` to use single curly braces, ensuring validity for `applydir` parsing.
- Updated `README.md` to include a subsection on `applydir_format_description` under "JSON Format," detailing its role in `vibedir` integration.
## [0.3.0] - 2025-10-02

### Added
- New `.prepdir/config.yaml` file for configuring directory traversal and file processing exclusions, UUID scrubbing, and other prepdir settings.
- Additional tests in `tests/test_main.py`:
  - `test_main_invalid_log_level`: Verifies handling of invalid `--log-level` arguments.
  - `test_main_invalid_non_ascii_action`: Verifies handling of invalid `--non-ascii-action` arguments.
  - `test_main_missing_file_entries`: Verifies error handling for JSON missing `file_entries` key.
  - `test_main_warning_errors`: Verifies handling of warning-level errors from `apply_changes`.
  - `test_main_empty_file_entries`: Verifies error handling for empty `file_entries` array.
  - `test_main_mixed_severity_errors`: Verifies handling of mixed severity errors from `apply_changes`.

### Changed
- Updated `.devcontainer/Dockerfile`:
  - Installed additional development tools via pip: `build`, `GitPython`, `pdm`, `pydantic`, `pytest`, `ruff`, `twine`.
- Updated `.devcontainer/devcontainer.json`:
  - Removed `consistency: "cached"` from volume bind for `/mounted/stuff_for_containers_home`.
  - Changed Python interpreter paths to point to the virtual environment (`/mounted/dev/applydir/.venv/bin/python`).
- Overhauled `README.md` with detailed sections on overview, features, JSON format, installation, usage, configuration, error handling, class structure, workflow, dependencies, best practices, edge cases, testing, and next steps.