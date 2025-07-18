# applydir

## Overview
`applydir` is a Python tool that automates the application of LLM-generated code changes to a codebase, achieving >95% reliability. It processes changes specified in a JSON format, using a unified "replace" approach to handle modifications, additions, deletions, and new file creation. Designed to work with `prepdir` (supplies full file contents) and `vibedir` (orchestrates prompts, LLM communication, Git integration, and linting), `applydir` validates and applies changes while ensuring consistency with relative file paths and robust error handling.

## Features
- **Unified Replace Approach**: All changes are treated as replacements:
  - Existing files: Replace `original_lines` (typically ≥10 lines, per `vibedir`’s `config.yaml`) with `changed_lines`.
  - New files: Create files with empty `original_lines` (`[]`) and full content in `changed_lines`.
- **Reliability (>95%)**: Uses ≥10 lines for unique matching in existing files, fuzzy matching (e.g., `difflib`) for robustness, and validates non-existent paths for new files.
- **Minimal JSON Format**: Simple structure with `file` and `changes` (`original_lines`, `changed_lines`) to reduce LLM output tokens.
- **Relative Paths**: Matches `prepdir`’s output (e.g., `src/main.py`) relative to the project base directory.
- **Validation**: Checks JSON structure, file paths, and non-ASCII characters (configurable via `src/applydir/config.yaml`).
- **Modular Design**: Separates JSON parsing, change validation, line matching, and file operations for clarity and testability.
- **Git and Linting in vibedir**: `vibedir` handles Git commits, rollbacks, and linting of temporary or actual files.
- **Configuration**: Uses `prepdir`’s `load_config` to read `.applydir/config.yaml` or the bundled `src/applydir/config.yaml`.

## JSON Format
Changes are provided in a JSON array of file objects:

```json
[
  {
    "file": "<relative_file_path>",
    "changes": [
      {
        "original_lines": [≥10 lines for existing files, or all lines if <10, or empty for new files>],
        "changed_lines": [<new lines for replacements or full content for new files>]
      }
    ]
  }
]
```

### Example Cases
- **Modification**: Replace ten lines in `src/main.py` with a modified version containing twelve lines (e.g., add error handling).
- **Addition**: Replace ten lines in `src/main.py` with new lines (e.g., new function plus original ten lines used for context).
- **Deletion**: Replace twenty lines in `src/main.py` with a subset, omitting deleted lines.
- **Creation**: Create `src/new_menu.py` with `original_lines: []` and full content of the new file in `changed_lines`.

## Configuration
- `src/applydir/config.yaml`: Defines validation settings for non-ASCII characters (error, warning, or ignore per file type).
- Uses `prepdir`’s `load_config` to read `.applydir/config.yaml` or the bundled `src/applydir/config.yaml`.

## Class Structure
1. **ApplyDirError (Pydantic)**:
   - Represents a single error or warning, JSON-serializable.
   - Attributes: `change: Optional[ApplyDirFileChange]`, `error_type: ErrorType`, `severity: ErrorSeverity`, `message: str`, `details: Optional[Dict]`.
   - Validates `error_type` (enum: `json_structure`, `file_path`, etc.), `severity` (enum: `error`, `warning`), and non-empty `message`.

2. **ApplyDirChanges (Pydantic)**:
   - Parses and validates JSON, creating `ApplyDirFileChange` objects with `file` injected.
   - Validates JSON structure and file paths.
   - Attributes: `files: List[Dict[str, Union[str, List[ApplyDirFileChange]]]]`.

3. **ApplyDirFileChange (Pydantic)**:
   - Represents and validates a single change, including the file path.
   - Validates file paths (relative, non-empty) and non-ASCII characters (configurable via `src/applydir/config.yaml`).
   - Attributes: `file: str`, `original_lines: List[str]`, `changed_lines: List[str]`.

4. **ApplyDirMatcher**:
   - Matches `original_lines` in existing files using fuzzy matching (e.g., `difflib`).
   - Attributes: `similarity_threshold: float`, `max_search_lines: Optional[int]`.
   - Methods: `match(file_content: List[str], change: ApplyDirFileChange) -> Union[Dict, List[ApplyDirError]]`.

5. **ApplyDirApplicator**:
   - Applies changes using `ApplyDirFileChange` and `ApplyDirMatcher`.
   - Handles file operations (replace or create) in temporary files.
   - Attributes: `base_dir: str`, `changes: ApplyDirChanges`, `matcher: ApplyDirMatcher`, `logger`.
   - Methods: `apply_changes()`, `apply_single_change(change: ApplyDirFileChange)`.

## Error Format
Errors and warnings are returned as `List[ApplyDirError]`, serialized as JSON:

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
    "severity": "error",
    "message": "JSON is not an array",
    "details": {}
  }
]
```

### Error Types
- `json_structure`: Bad JSON structure received.
- `file_path`: Invalid file path provided.
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
   - Passes JSON to `ApplyDirChanges`.
3. **ApplyDirChanges**: Parses JSON, creates and validates `ApplyDirFileChange` objects, returns `List[ApplyDirError]`.
4. **ApplyDirFileChange**: Validates file paths and non-ASCII characters, returns `List[ApplyDirError]`.
5. **ApplyDirApplicator**: Iterates over changes, uses `ApplyDirMatcher`, writes to temporary files, returns `List[ApplyDirError]`.
6. **ApplyDirMatcher**: Matches `original_lines`, returns range or `List[ApplyDirError]`.
7. **vibedir**:
   - Runs linters (e.g., `pylint`, `markdownlint`) on temporary or actual files, returns `List[ApplyDirError]`.
   - On success: Moves files to codebase, commits.
   - On errors: Displays errors or queries LLM, discards temporary files.
   - On rejection: Reverts via Git or backups.

## Git and Linting
- **Git Integration (vibedir)**:
  - Before validation: Commit (e.g., `git commit -m "Pre-applydir changes"`) or backup files.
  - After application: Commit changes or revert on errors/rejection.
  - Non-Git projects: Use file backups.
- **Linting (vibedir)**:
  - Runs linters on temporary files (e.g., `.applydir_temp`) or actual files, per `vibedir`’s `config.yaml`.
  - Returns `List[ApplyDirError]` with `error_type: "linting"`, `severity: "error"`.

## Validation
- **ApplyDirChanges**: Validates JSON structure and file paths.
- **ApplyDirFileChange**: Checks file paths (relative, non-empty) and non-ASCII characters (configurable).
- **ApplyDirApplicator**: Verifies path non-existence for new files, relies on `ApplyDirMatcher`.
- **ApplyDirMatcher**: Ensures `original_lines` matches file content using fuzzy matching.

## Python Best Practices
- **PEP 8**: Clear, descriptive names (e.g., `ApplyDirError`).
- **PEP 20**: Explicit `change` and `severity` in `ApplyDirError`, simple class roles.
- **Type Safety**: Pydantic for type-safe errors and changes.
- **Testability**: Small classes and structured errors.
- **Documentation**: Docstrings for all classes and methods.

## Edge Cases
- **New File Creation**: Validate non-existent paths.
- **Unmatched Lines**: Fuzzy matching with `ApplyDirError`.
- **Invalid Syntax**: Detected by `ApplyDirFileChange` (e.g., non-ASCII warnings).
- **Short Files**: Handled by `vibedir`’s prompt.
- **File System Issues**: Caught by `ApplyDirApplicator`.
- **Linting Failures**: Caught by `vibedir`.

## Dependencies
- **prepdir**: Provides `load_config` for configuration and `configure_logging` for test and `vibedir` logging.
- **Pydantic**: For JSON parsing, validation, and error handling.
- **difflib**: For fuzzy matching.
- **PyYAML**: For parsing `src/applydir/config.yaml` (via `prepdir`’s `load_config`).

## Next Steps
- Specify `ApplyDirMatcher` settings (e.g., `difflib` threshold).
- Plan logging for `ApplyDirApplicator` using `prepdir`’s `configure_logging`.
- Detail `vibedir`’s Git/backup and linting strategy.
- Develop additional test cases for `ApplyDirFileChange`, `ApplyDirChanges`, etc.