# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Links
- [README](https://github.com/eyecantell/applydir/blob/main/README.md)
- [GitHub Repository](https://github.com/eyecantell/applydir)
- [PyPI](https://pypi.org/project/applydir/)
- [Dynaconf Documentation](https://dynaconf.com)

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