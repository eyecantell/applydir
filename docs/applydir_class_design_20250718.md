# applydir Class Design Document

## Overview
The `applydir` project automates code changes by applying LLM-generated modifications, achieving >95% reliability. It works with `prepdir` (supplies full file contents) and `vibedir` (crafts prompts, communicates with the LLM, manages Git integration, and lints changes). Changes are specified in a JSON array of file objects, using a unified "replace" approach where `original_lines` are replaced with `changed_lines`. The design supports modifications, additions, deletions, and new file creation, with paths resolvable within the project directory matching `prepdir`’s output.

## Core Design Principles
- **Unified Replace Approach**: All changes (modifications, additions, deletions, creations) are replacements:
  - Existing files: Replace `original_lines` (typically ≥10 lines, per `vibedir`) with `changed_lines`.
  - New files: `original_lines` is empty (`[]`), `changed_lines` contains the full content.
- **Reliability (>95%)**: ≥10 lines in `original_lines` ensure unique matching for existing files; fuzzy matching handles minor changes. New file creation validates non-existent paths.
- **Minimal JSON**: Only `file` and `changes` (`original_lines`, `changed_lines`), reducing token usage. Warns on extra fields.
- **Resolvable Paths**: Accepts relative or absolute paths, resolved within the project directory (e.g., `src/main.py`).
- **Validation Simplicity**: Validate JSON structure, file paths, and non-ASCII characters; fail if no match or new file path exists.
- **Git and Linting in vibedir**: `vibedir` handles Git integration, rollbacks, and linting of temporary or actual files, keeping `applydir` focused on validation and application.
- **Configuration**: Uses `prepdir`’s `load_config` to read `.applydir/config.yaml` or the bundled `src/applydir/config.yaml`.

## JSON Format
```json
[
  {
    "file": "<relative_or_absolute_file_path>",
    "changes": [
      {
        "original_lines": [<at least 10 lines for existing files, or all lines for files <10 lines, or empty for new files>],
        "changed_lines": [<new lines, replaces original_lines or full content for new files>]
      }
    ]
  }
]
```

### Fields
- **Top-Level**: Array of file objects.
- **File Object**:
  - `file`: Relative or absolute path (e.g., `src/main.py` or `/workspaces/applydir/src/main.py`).
  - `changes`: Array of change objects.
- **Change Object**:
  - `original_lines`: ≥10 lines for existing files (per `vibedir`’s `config.yaml`), empty for new files.
  - `changed_lines`: New lines for replacements or full content for new files.

### Example Cases
- **Modification (src/main.py)**: Replace 10 lines with modified version.
- **Addition (src/main.py)**: Replace 10 lines with new lines.
- **Deletion (src/main.py)**: Replace 10 lines with a subset.
- **Creation (src/new_menu.py)**: Create file with `original_lines: []`.
- **Addition (README.md)**: Replace lines with added content.
- **Merging**: Changes within 10 lines merged by LLM.

## Configuration
- `src/applydir/config.yaml`: Defines validation settings for non-ASCII characters (error, warning, or ignore per file type) and whether to use temporary files (`use_temp_files`).
- Uses `prepdir`’s `load_config` to read `.applydir/config.yaml` or the bundled `src/applydir/config.yaml`.

## Class Structure
1. **ApplydirError (Pydantic)**:
   - **Purpose**: Represent a single error or warning with a consistent, JSON-serializable structure.
   - **Attributes**:
     - `change: Optional[ApplydirFileChange]` (change causing the error, or `None` for global errors).
     - `error_type: ErrorType` (enum: `json_structure`, `file_path`, `changes_empty`, `syntax`, `empty_changed_lines`, `matching`, `file_system`, `linting`).
     - `severity: ErrorSeverity` (enum: `error`, `warning`).
     - `message: str` (human-readable description).
     - `details: Optional[Dict]` (additional context, e.g., linting output or extra JSON fields).
   - **Validation**:
     - Ensure `error_type` and `severity` are valid enum values.
     - Ensure `message` is non-empty.
     - Default `details` to `{}` if `None`.
   - **Serialization**: Uses Pydantic’s `.dict()` for JSON compatibility.

2. **ApplydirChanges (Pydantic)**:
   - **Purpose**: Parse and validate JSON, create `ApplydirFileChange` objects with `file` injected.
   - **Attributes**: `files: List[Dict[str, Union[str, List[ApplydirFileChange]]]]`.
   - **Validation**:
     - JSON is an array, `file` paths valid (resolvable within project), `changes` non-empty.
     - Warns on extra fields in JSON.
     - Delegates content validation to `ApplydirFileChange`.
   - **Error Handling**: Returns `List[ApplydirError]` with `change: None` for JSON or file path errors, collects `ApplydirError` from `ApplydirFileChange`.

3. **ApplydirFileChange (Pydantic)**:
   - **Purpose**: Represent and validate a single change, including the file path.
   - **Attributes**: `file: str`, `original_lines: List[str]`, `changed_lines: List[str]`.
   - **Validation**:
     - Checks file paths (resolvable within project directory).
     - Checks for non-ASCII characters in `changed_lines` (configurable via `src/applydir/config.yaml`).
     - New files: `changed_lines` non-empty.
   - **Error Handling**: Returns `List[ApplydirError]` with `error_type` like `file_path`, `syntax`, or `empty_changed_lines`.

4. **ApplydirMatcher**:
   - **Purpose**: Match `original_lines` in existing files using fuzzy matching (e.g., `difflib`).
   - **Attributes**: `similarity_threshold: float`, `max_search_lines: Optional[int]`.
   - **Methods**: `match(file_content: List[str], change: ApplydirFileChange) -> Union[Dict, List[ApplydirError]]`.
   - **Error Handling**: Returns `List[ApplydirError]` with `ApplydirFileChange` as `change` for matching errors.

5. **ApplydirApplicator**:
   - **Purpose**: Apply changes using `ApplydirFileChange` and `ApplydirMatcher`.
   - **Attributes**: `base_dir: str`, `changes: ApplydirChanges`, `matcher: ApplydirMatcher`, `logger`.
   - **Methods**:
     - `apply_changes() -> List[ApplydirError]`.
     - `apply_single_change(change: ApplydirFileChange) -> List[ApplydirError]`.
     - `write_changes(file_path: str, changed_lines: List[str], range: Optional[Dict])`.
   - **Error Handling**: Returns `List[ApplydirError]` for file system or matching errors.
   - **Configuration**: Writes to temporary files (e.g., `.applydir_temp`) or actual files, per `src/applydir/config.yaml`.

## Error Types
- `json_structure`: Bad JSON structure received (e.g., not an array or extra fields).
- `file_path`: Invalid file path provided (e.g., outside project directory).
- `changes_empty`: Empty changes array for file.
- `syntax`: Invalid syntax in changed lines (e.g., non-ASCII characters, configurable as error or warning).
- `empty_changed_lines`: Empty changed lines for new file.
- `matching`: No matching lines found.
- `file_system`: File system operation failed (e.g., file exists, permissions).
- `linting`: Linting failed on file (handled by vibedir, e.g., pylint or markdownlint errors).

## Error Format
Errors are returned as `List[ApplydirError]`, serialized as JSON:
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

## Workflow
1. **User Input**:
   - User provides prompt (e.g., “add a save button”) and project directory to `vibedir` (04:38 PM MDT, July 18, 2025).
2. **vibedir Orchestrates**:
   - Uses `prepdir`’s `load_config` to read its `config.yaml` and `configure_logging` for logging.
   - Calls `prepdir` for file contents (e.g., `src/main.py`).
   - Sends prompt to LLM, receives JSON.
   - Commits or backs up state (Git or files).
   - Passes JSON to `ApplydirChanges`.
3. **ApplydirChanges**:
   - Parses JSON, creates `ApplydirFileChange` objects with `file`.
   - Validates structure, warns on extra fields, delegates to `ApplydirFileChange`.
   - Returns `List[ApplydirError]`.
4. **ApplydirFileChange**:
   - Validates file paths (resolvable within project) and non-ASCII characters (configurable).
   - Returns `List[ApplydirError]` with self as `change`.
5. **ApplydirApplicator**:
   - Iterates over `ApplydirChanges.files` and `changes`.
   - For each `ApplydirFileChange`:
     - Resolves path using `change.file`.
     - If `original_lines` non-empty:
       - Reads file, calls `ApplydirMatcher.match(change)`.
       - Writes `changed_lines` to temporary or actual file (per `use_temp_files`).
     - If `original_lines` empty:
       - Checks path non-existence.
       - Writes `changed_lines` to temporary or actual file.
   - Returns `List[ApplydirError]`.
6. **ApplydirMatcher**:
   - Matches `change.original_lines` in file content.
   - Returns range or `List[ApplydirError]`.
7. **vibedir**:
   - Runs linters (e.g., `pylint`, `markdownlint`) on temporary or actual files, returns `List[ApplydirError]`.
   - On success: Moves temporary files to codebase (if using temp files), commits (e.g., `git commit -m "Applied changes"`).
   - On errors: Displays `List[ApplydirError]` or queries LLM, discards temporary files or reverts via Git.
   - On rejection: Reverts via Git (e.g., `git reset --hard`) or backups.

## Git and Linting (vibedir)
- **Git Integration**:
  - **Before Validation**: Commit (e.g., `git commit -m "Pre-applydir changes"`) or backup files.
  - **After Application**: Commit changes or revert on errors/rejection.
  - **Non-Git Projects**: Use file backups.
- **Linting**:
  - Runs linters on temporary files (e.g., `.applydir_temp`) or actual files, per `vibedir`’s `config.yaml`.
  - Returns `List[ApplydirError]` with `error_type: "linting"`, `severity: "error"`.

## Validation Rules
- **ApplydirChanges**: JSON is an array, `file` paths valid, `changes` non-empty, warns on extra fields.
- **ApplydirFileChange**:
  - File paths: Resolvable within project directory.
  - Non-ASCII characters: Configurable (error, warning, or ignore) via `src/applydir/config.yaml`.
  - New files: `changed_lines` non-empty.
- **ApplydirApplicator**: Path non-existence for new files, matching for existing files.
- **ApplydirMatcher**: Fuzzy matching for `original_lines`.

## Python Best Practices
- **PEP 8**: Clear names (e.g., `ApplydirError`, `ApplydirFileChange`).
- **PEP 20**: Explicit `change` and `severity` in `ApplydirError`, simple class roles.
- **Type Safety**: Pydantic for type-safe errors and changes.
- **Testability**: Small classes and structured errors for testing.
- **Documentation**: Docstrings for all classes and methods.

## Edge Cases and Mitigations
1. **New File Creation**: Validate non-existent path in `ApplydirApplicator`.
2. **Unmatched original_lines**: `ApplydirMatcher` uses fuzzy matching, returns `ApplydirError`.
3. **Invalid Syntax**: `ApplydirFileChange` detects non-ASCII characters, returns `ApplydirError` (configurable).
4. **Short Files**: `vibedir`’s prompt allows all lines.
5. **File System Issues**: `ApplydirApplicator` catches errors, returns `ApplydirError`.
6. **Linting Failures**: `vibedir` catches linting issues, returns `ApplydirError`.
7. **Rollback**: `vibedir` reverts via Git or backups.

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