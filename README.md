# applydir

## Overview
`applydir` is a Python tool that automates the application of LLM-generated code changes to a codebase, achieving >95% reliability. It processes changes specified in a JSON format, using a unified "replace" approach to handle modifications, additions, deletions, and new file creation. Designed to work with `prepdir` (supplies full file contents) and `vibedir` (orchestrates prompts, LLM communication, Git integration, and linting), `applydir` validates and applies changes while ensuring consistency with resolvable file paths and robust error handling.

## Features
- **Unified Replace Approach**: All changes are treated as replacements:
  - Existing files: Replace `original_lines` (typically ≥10 lines, per `vibedir`’s `config.yaml`) with `changed_lines`.
  - New files: Create files with empty `original_lines` (`[]`) and full content in `changed_lines`.
- **Reliability (>95%)**: Uses ≥10 lines for unique matching in existing files, fuzzy matching (e.g., `difflib`) for robustness, and validates non-existent paths for new files.
- **Minimal JSON Format**: Simple structure with `file` and `changes` (`original_lines`, `changed_lines`) to reduce LLM output tokens.
- **Resolvable Paths**: Accepts relative or absolute paths, resolved within the project directory, matching `prepdir`’s output (e.g., `src/main.py`).
- **Validation**: Checks JSON structure, file paths, and non-ASCII characters (configurable via `src/applydir/config.yaml`). Warns on extra JSON fields.
- **Modular Design**: Separates JSON parsing, change validation, line matching, and file operations for clarity and testability.
- **Git and Linting in vibedir**: `vibedir` handles Git commits, rollbacks, and linting of temporary or actual files.
- **Configuration**: Uses `prepdir`’s `load_config` to read `.applydir/config.yaml` or the bundled `src/applydir/config.yaml`. Configurable temporary vs. actual file writes.

## JSON Format
The LLM provides changes in a JSON array of file objects:

```json
[
  {
    "file": "<relative_or_absolute_file_path>",
    "changes": [
      {
        "original_lines": [<≥10 lines for existing files, or all lines if <10, or empty for new files>],
        "changed_lines": [<new lines for replacements or full content for new files>]
      }
    ]
  }
]
```

### Example Cases
- **Modification**: Replace 10 lines in `src/main.py` with a modified version (e.g., add error handling).
- **Addition**: Replace 10 lines in `src/main.py` with new lines (e.g., new function).
- **Deletion**: Replace 10 lines in `src/main.py` with a subset, omitting deleted lines.
- **Creation**: Create `src/new_menu.py` with `original_lines: []` and full content in `changed_lines`.
- **Addition in Markdown**: Add a feature description to `README.md`.

## Configuration
- `src/applydir/config.yaml`: Defines validation settings for non-ASCII characters (error, warning, or ignore per file type) and whether to use temporary files (`use_temp_files`).
- Uses `prepdir`’s `load_config` to read `.applydir/config.yaml` or the bundled `src/applydir/config.yaml`.

## Class Structure
1. **ApplydirError (Pydantic)**:
   - Represents a single error or warning, JSON-serializable.
   - Attributes: `change: Optional[ApplydirFileChange]`, `error_type: ErrorType`, `severity: ErrorSeverity`, `message: str`, `details: Optional[Dict]`.
   - Validates `error_type` (enum: `json_structure`, `file_path`, etc.), `severity` (enum: `error`, `warning`), and non-empty `message`.

2. **ApplydirChanges (Pydantic)**:
   - Parses and validates JSON, creating `ApplydirFileChange` objects with `file` injected.
   - Validates JSON structure, file paths, and warns on extra fields.
   - Attributes: `files: List[Dict[str, Union[str, List[ApplydirFileChange]]]]`.

3. **ApplydirFileChange (Pydantic)**:
   - Represents and validates a single change, including the file path.
   - Validates file paths (resolvable within project directory) and non-ASCII characters (configurable via `src/applydir/config.yaml`).
   - Attributes: `file: str`, `original_lines: List[str]`, `changed_lines: List[str]`.

4. **ApplydirMatcher**:
   - Matches `original_lines` in existing files using fuzzy matching (e.g., `difflib`).
   - Attributes: `similarity_threshold: float`, `max_search_lines: Optional[int]`.
   - Methods: `match(file_content: List[str], change: ApplydirFileChange) -> Union[Dict, List[ApplydirError]]`.

5. **ApplydirApplicator**:
   - Applies changes using `ApplydirFileChange` and `ApplydirMatcher`.
   - Writes to temporary files (e.g., `.applydir_temp`) or actual files, configurable via `src/applydir/config.yaml`.
   - Attributes: `base_dir: str`, `changes: ApplydirChanges`, `matcher: ApplydirMatcher`, `logger`.
   - Methods: `apply_changes()`, `apply_single_change(change: ApplydirFileChange)`.

## Error Format
Errors and warnings are returned as `List[ApplydirError]`, serialized as JSON:

```json
[
  {
    "change": {
      "file": "src/main.py",
      "original_lines": ["print('Hello')"],
      "changed_lines": ["print('Hello 😊')"]
    },
    "error_type": "syntax",
    "severity": "warning",
    "message": "Non-ASCII characters found in changed_lines",
    "details": {"line": "print('Hello 😊')", "line_number": 1}
  },
  {
    "change": null,
    "error_type": "json_structure",
    "severity": "warning",
    "message": "Extra fields found in JSON",
    "details": {"extra_keys": ["confidence"]}
  }
]
```

## Error Types
- `json_structure`: Bad JSON structure received (e.g., not an array or extra fields).
- `file_path`: Invalid file path provided (e.g., outside project directory).
- `changes_empty`: Empty changes array for file.
- `syntax`: Invalid syntax in changed lines (e.g., non-ASCII characters, configurable via `src/applydir/config.yaml`).
- `empty_changed_lines`: Empty changed lines for new file.
- `matching`: No matching lines found.
- `file_system`: File system operation failed.
- `linting`: Linting failed on file (handled by vibedir).

## Workflow
1. **User Input**: User provides a prompt (e.g., “add a save button”) and project directory to `vibedir`.
2. **vibedir**:
   - Uses `prepdir`’s `load_config` to read its `config.yaml` and `configure_logging` for logging.
   - Calls `prepdir` for file contents (e.g., `src/main.py`).
   - Sends prompt to LLM, receives JSON.
   - Commits or backs up state (Git or files).
   - Passes JSON to `ApplydirChanges`.
3. **ApplydirChanges**: Parses JSON, creates and validates `ApplydirFileChange` objects, returns `List[ApplydirError]`.
4. **ApplydirFileChange**: Validates file paths and non-ASCII characters, returns `List[ApplydirError]`.
5. **ApplydirApplicator**: Iterates over changes, uses `ApplydirMatcher`, writes to temporary or actual files, returns `List[ApplydirError]`.
6. **ApplydirMatcher**: Matches `original_lines`, returns range or `List[ApplydirError]`.
7. **vibedir**:
   - Runs linters (e.g., `pylint`, `markdownlint`) on temporary or actual files, returns `List[ApplydirError]`.
   - On success: Moves temporary files to codebase (if using temp files), commits.
   - On errors: Displays errors or queries LLM, discards temporary files or reverts via Git.
   - On rejection: Reverts via Git or backups.

## Git and Linting
- **Git Integration (vibedir)**:
  - Before validation: Commit (e.g., `git commit -m "Pre-applydir changes"`) or backup files.
  - After application: Commit changes or revert on errors/rejection.
  - Non-Git projects: Use file backups.
- **Linting (vibedir)**:
  - Runs linters on temporary files (e.g., `.applydir_temp`) or actual files, per `vibedir`’s `config.yaml`.
  - Returns `List[ApplydirError]` with `error_type: "linting"`, `severity: "error"`.

## Validation
- **ApplydirChanges**: Validates JSON structure, file paths, and warns on extra fields.
- **ApplydirFileChange**: Checks file paths (resolvable within project) and non-ASCII characters (configurable).
- **ApplydirApplicator**: Verifies path non-existence for new files, relies on `ApplydirMatcher`.
- **ApplydirMatcher**: Ensures `original_lines` matches file content using fuzzy matching.

## Python Best Practices
- **PEP 8**: Clear, descriptive names (e.g., `ApplydirError`).
- **PEP 20**: Explicit `change` and `severity` in `ApplydirError`, simple class roles.
- **Type Safety**: Pydantic for type-safe errors and changes.
- **Testability**: Small classes and structured errors.
- **Documentation**: Docstrings for all classes and methods.

## Edge Cases
- **New File Creation**: Validate non-existent paths.
- **Unmatched Lines**: Fuzzy matching with `ApplydirError`.
- **Invalid Syntax**: Detected by `ApplydirFileChange` (e.g., non-ASCII warnings).
- **Short Files**: Handled by `vibedir`’s prompt.
- **File System Issues**: Caught by `ApplydirApplicator`.
- **Linting Failures**: Caught by `vibedir`.

## Dependencies
- **prepdir**: Provides `load_config` for configuration and `configure_logging` for test and `vibedir` logging.
- **Pydantic**: For JSON parsing, validation, and error handling.
- **difflib**: For fuzzy matching.
- **PyYAML**: For parsing `src/applydir/config.yaml` (via `prepdir`’s `load_config`).

## Next Steps
- Specify `ApplydirMatcher` settings (e.g., `difflib` threshold).
- Plan logging for `ApplydirApplicator` using `prepdir`’s `configure_logging`.
- Detail `vibedir`’s Git/backup and linting strategy.
- Develop additional test cases for `ApplydirFileChange`, `ApplydirChanges`, etc.