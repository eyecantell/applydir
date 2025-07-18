# applydir Class Design Document

## Overview
The `applydir` project automates code changes by applying LLM-generated modifications, achieving >95% reliability. It works with `prepdir` (supplies full file contents) and `vibedir` (crafts prompts, communicates with the LLM, manages Git integration, and lints changes). Changes are specified in a JSON array of file objects, using a unified "replace" approach where `original_lines` are replaced with `changed_lines`. The design supports modifications, additions, deletions, and new file creation, with relative paths matching `prepdir`’s output.

## Core Design Principles
- **Unified Replace Approach**: All changes (modifications, additions, deletions, creations) are replacements:
  - Existing files: Replace `original_lines` (typically ≥10 lines, per `vibedir`) with `changed_lines`.
  - New files: `original_lines` is empty (`[]`), `changed_lines` contains the full content.
- **Reliability (>95%)**: ≥10 lines in `original_lines` ensure unique matching for existing files; fuzzy matching handles minor changes. New file creation validates non-existent paths.
- **Minimal JSON**: Only `file` and `changes` (`original_lines`, `changed_lines`), reducing token usage.
- **Relative Paths**: Match `prepdir`’s output (e.g., `src/main.py`).
- **Validation Simplicity**: Validate JSON structure, file paths, and non-ASCII characters; fail if no match or new file path exists.
- **Git and Linting in vibedir**: `vibedir` handles Git integration, rollbacks, and linting of temporary or actual files, keeping `applydir` focused on validation and application.
- **Configuration**: Uses `prepdir`’s `load_config` to read `.applydir/config.yaml` or the bundled `src/applydir/config.yaml`.

## JSON Format
```json
[
  {
    "file": "<relative_file_path>",
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
  - `file`: Relative path (e.g., `src/main.py`).
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
- `src/applydir/config.yaml`: Defines validation settings for non-ASCII characters (error, warning, or ignore per file type).
- Uses `prepdir`’s `load_config` to read `.applydir/config.yaml` or the bundled `src/applydir/config.yaml`.

## Class Structure
1. **ApplyDirError (Pydantic)**:
   - **Purpose**: Represent a single error or warning with a consistent, JSON-serializable structure.
   - **Attributes**:
     - `change: Optional[ApplyDirFileChange]` (change causing the error, or `None` for global errors).
     - `error_type: ErrorType` (enum: `json_structure`, `file_path`, `changes_empty`, `syntax`, `empty_changed_lines`, `matching`, `file_system`, `linting`).
     - `severity: ErrorSeverity` (enum: `error`, `warning`).
     - `message: str` (human-readable description).
     - `details: Optional[Dict]` (additional context, e.g., linting output).
   - **Validation**:
     - Ensure `error_type` and `severity` are valid enum values.
     - Ensure `message` is non-empty.
     - Default `details` to `{}` if `None`.
   - **Serialization**: Uses Pydantic’s `.dict()` for JSON compatibility.

2. **ApplyDirChanges (Pydantic)**:
   - **Purpose**: Parse and validate JSON, create `ApplyDirFileChange` objects with `file` injected.
   - **Attributes**: `files: List[Dict[str, Union[str, List[ApplyDirFileChange]]]]`.
   - **Validation**:
     - JSON is an array, `file` paths valid (relative, non-empty), `changes` non-empty.
     - Delegates content validation to `ApplyDirFileChange`.
   - **Error Handling**: Returns `List[ApplyDirError]` with `change: None` for JSON or file path errors, collects `ApplyDirError` from `ApplyDirFileChange`.

3. **ApplyDirFileChange (Pydantic)**:
   - **Purpose**: Represent and validate a single change, including the file path.
   - **Attributes**: `file: str`, `original_lines: List[str]`, `changed_lines: List[str]`.
   - **Validation**:
     - Checks file paths (relative, non-empty).
     - Checks for non-ASCII characters in `changed_lines` (configurable via `src/applydir/config.yaml`).
     - New files: `changed_lines` non-empty.
   - **Error Handling**: Returns `List[ApplyDirError]` with `error_type` like `file_path`, `syntax`, or `empty_changed_lines`.

4. **ApplyDirMatcher**:
   - **Purpose**: Match `original_lines` in existing files using fuzzy matching (e.g., `difflib`).
   - **Attributes**: `similarity_threshold: float`, `max_search_lines: Optional[int]`.
   - **Methods**: `match(file_content: List[str], change: ApplyDirFileChange) -> Union[Dict, List[ApplyDirError]]`.
   - **Error Handling**: Returns `List[ApplyDirError]` with `ApplyDirFileChange` as `change` for matching errors.

5. **ApplyDirApplicator**:
   - **Purpose**: Apply changes using `ApplyDirFileChange` and `ApplyDirMatcher`.
   - **Attributes**: `base_dir: str`, `changes: ApplyDirChanges`, `matcher: ApplyDirMatcher`, `logger`.
   - **Methods**:
     - `apply_changes() -> List[ApplyDirError]`.
     - `apply_single_change(change: ApplyDirFileChange) -> List[ApplyDirError]`.
     - `write_changes(file_path: str, changed_lines: List[str], range: Optional[Dict])`.
   - **Error Handling**: Returns `List[ApplyDirError]` for file system or matching errors.

## Error Types
- `json_structure`: Bad JSON structure received (e.g., not an array).
- `file_path`: Invalid file path provided (e.g., absolute).
- `changes_empty`: Empty changes array for file.
- `syntax`: Invalid syntax in changed lines (e.g., non-ASCII characters, configurable as error or warning).
- `empty_changed_lines`: Empty changed lines for new file.
- `matching`: No matching lines found.
- `file_system`: File system operation failed (e.g., file exists, permissions).
- `linting`: Linting failed on file (handled by vibedir, e.g., pylint or markdownlint errors).

## Error Format
Errors are returned as `List[ApplyDirError]`, serialized as JSON:
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

## Workflow
1. **User Input**:
   - User provides prompt (e.g., “add a save button”) and project directory to `vibedir` (01:41 PM MDT, July 18, 2025).
2. **vibedir Orchestrates**:
   - Uses `prepdir`’s `load_config` to read its `config.yaml` and `configure_logging` for logging.
   - Calls `prepdir` for file contents (e.g., `src/main.py`).
   - Sends prompt to LLM, receives JSON.
   - Commits or backs up state (Git or files).
   - Passes JSON to `ApplyDirChanges`.
3. **ApplyDirChanges**:
   - Parses JSON, creates `ApplyDirFileChange` objects with `file`.
   - Validates structure, delegates to `ApplyDirFileChange`.
   - Returns `List[ApplyDirError]`.
4. **ApplyDirFileChange**:
   - Validates file paths and non-ASCII characters (configurable).
   - Returns `List[ApplyDirError]` with self as `change`.
5. **ApplyDirApplicator**:
   - Iterates over `ApplyDirChanges.files` and `changes`.
   - For each `ApplyDirFileChange`:
     - Resolves path using `change.file`.
     - If `original_lines` non-empty:
       - Reads file, calls `ApplyDirMatcher.match(change)`.
       - Writes `changed_lines` to temporary file (e.g., `.applydir_temp/src/main.py`).
     - If `original_lines` empty:
       - Checks path non-existence.
       - Writes `changed_lines` to temporary file.
   - Returns `List[ApplyDirError]`.
6. **ApplyDirMatcher**:
   - Matches `change.original_lines` in file content.
   - Returns range or `List[ApplyDirError]`.
7. **vibedir**:
   - Runs linters (e.g., `pylint`, `markdownlint`) on temporary or actual files, returns `List[ApplyDirError]`.
   - On success: Moves temporary files to codebase, commits (e.g., `git commit -m "Applied changes"`).
   - On errors: Displays `List[ApplyDirError]` or queries LLM, discards temporary files.
   - On rejection: Reverts via Git (e.g., `git reset --hard`) or backups.

## Git and Linting (vibedir)
- **Git Integration**:
  - **Before Validation**: Commit (e.g., `git commit -m "Pre-applydir changes"`) or backup files.
  - **After Application**: Commit changes or revert on errors/rejection.
  - **Non-Git Projects**: Use file backups.
- **Linting**:
  - Runs linters on temporary files (e.g., `.applydir_temp`) or actual files, per `vibedir`’s `config.yaml`.
  - Returns `List[ApplyDirError]` with `error_type: "linting"`, `severity: "error"`.

## Validation Rules
- **ApplyDirChanges**: JSON is an array, `file` paths valid, `changes` non-empty.
- **ApplyDirFileChange**:
  - File paths: Relative, non-empty.
  - Non-ASCII characters: Configurable (error, warning, or ignore) via `src/applydir/config.yaml`.
  - New files: `changed_lines` non-empty.
- **ApplyDirApplicator**: Path non-existence for new files, matching for existing files.
- **ApplyDirMatcher**: Fuzzy matching for `original_lines`.

## Python Best Practices
- **PEP 8**: Clear names (e.g., `ApplyDirError`, `ApplyDirFileChange`).
- **PEP 20**: Explicit `change` and `severity` in `ApplyDirError`, simple class roles.
- **Type Safety**: Pydantic for type-safe errors and changes.
- **Testability**: Small classes and structured errors for testing.
- **Documentation**: Docstrings for all classes and methods.

## Edge Cases and Mitigations
1. **New File Creation**: Validate non-existent path in `ApplyDirApplicator`.
2. **Unmatched original_lines**: `ApplyDirMatcher` uses fuzzy matching, returns `ApplyDirError`.
3. **Invalid Syntax**: `ApplyDirFileChange` detects non-ASCII characters, returns `ApplyDirError` (configurable).
4. **Short Files**: `vibedir`’s prompt allows all lines.
5. **File System Issues**: `ApplyDirApplicator` catches errors, returns `ApplyDirError`.
6. **Linting Failures**: `vibedir` catches linting issues, returns `ApplyDirError`.
7. **Rollback**: `vibedir` reverts via Git or backups.

## Dependencies
- **prepdir**: Provides `load_config` for configuration and `configure_logging` for test and `vibedir` logging.
- **Pydantic**: For JSON parsing, validation, and error handling.
- **difflib**: For fuzzy matching.

## Next Steps
- Specify `ApplyDirMatcher` settings (e.g., `difflib` threshold).
- Plan logging for `ApplyDirApplicator` using `prepdir`’s `configure_logging`.
- Detail `vibedir`’s Git/backup and linting strategy.
- Develop additional test cases for `ApplyDirFileChange`, `ApplyDirChanges`, etc.