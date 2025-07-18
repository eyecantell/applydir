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
- **Validation Simplicity**: Validate JSON structure, syntax, and `original_lines` matching; fail if no match or new file path exists.
- **Git and Linting in vibedir**: `vibedir` handles Git integration, rollbacks, and linting of temporary files, keeping `applydir` focused on validation and application.

## JSON Format
```json
[
  {
    "file": "<relative_file_path>",
    "changes": [
      {
        "original_lines": [<at least 10 lines for existing files, or all lines for files <10 lines, or empty for new files>],
        "changed_lines": [<new lines, includes original_lines plus new lines for additions, subset for deletions, or full content for new files>]
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
- **Addition (src/main.py)**: Replace 10 lines with 10 lines plus new lines.
- **Deletion (src/main.py)**: Replace 10 lines with a subset.
- **Creation (src/new_menu.py)**: Create file with `original_lines: []`.
- **Addition (README.md)**: Replace 10 lines with added content.
- **Merging**: Changes within 10 lines merged by LLM.

## Class Structure
1. **ApplyDirError (Pydantic)**:
   - **Purpose**: Represent a single error with a consistent, JSON-serializable structure.
   - **Attributes**:
     - `change: Optional[ApplyDirFileChange]` (change causing the error, or `None` for global errors).
     - `error_type: str` (e.g., `json_structure`, `syntax`, `addition_mismatch`, `empty_changed_lines`, `matching`, `file_system`, `linting`).
     - `message: str` (human-readable description).
     - `details: Optional[Dict]` (additional context, e.g., linting output).
   - **Validation**:
     - Ensure `error_type` is valid (e.g., using Pydantic `Enum` or validator).
     - Ensure `message` is non-empty.
     - Allow `change` and `details` to be `None` or empty.
   - **Serialization**: Uses Pydantic’s `.dict()` for JSON compatibility; truncates large `original_lines`/`changed_lines` if needed.

2. **ApplyDirChanges (Pydantic)**:
   - **Purpose**: Parse and validate JSON, create `ApplyDirFileChange` objects with `file` injected.
   - **Attributes**: `files: List[Dict[str, Union[str, List[ApplyDirFileChange]]]]` (file path, changes).
   - **Validation**:
     - JSON is an array, `file` paths valid (relative, non-empty), `changes` non-empty.
     - Delegates content validation to `ApplyDirFileChange`.
   - **Error Handling**: Returns `List[ApplyDirError]` with `change: None` for JSON or file path errors, collects `ApplyDirError` from `ApplyDirFileChange`.

3. **ApplyDirFileChange (Pydantic)**:
   - **Purpose**: Represent and validate a single change, including the file path.
   - **Attributes**: `file: str`, `original_lines: List[str]`, `changed_lines: List[str]`.
   - **Validation**:
     - Existing files: `changed_lines` valid syntax (e.g., `pylint`, `markdownlint`), additions start with `original_lines`.
     - New files: `changed_lines` non-empty, valid syntax.
   - **Error Handling**: Returns `List[ApplyDirError]` with self as `change`.

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

## Error Format
Errors are returned as `List[ApplyDirError]`, serialized as JSON:

```json
[
  {
    "change": {
      "file": "src/main.py",
      "original_lines": ["print(\"Hello\")", "..."],
      "changed_lines": ["print(x)", "..."]
    },
    "error_type": "syntax",
    "message": "Invalid Python syntax in changed_lines",
    "details": {"pylint_error": "undefined-variable: 'x' at line 5"}
  },
  {
    "change": null,
    "error_type": "json_structure",
    "message": "JSON is not an array",
    "details": {}
  }
]
```

### Error Types
- `json_structure`: Invalid JSON (e.g., not an array).
- `file_path`: Invalid `file` path (e.g., absolute).
- `changes_empty`: Empty `changes` array.
- `syntax`: Invalid `changed_lines` syntax.
- `addition_mismatch`: `changed_lines` doesn’t start with `original_lines` for additions.
- `empty_changed_lines`: `changed_lines` empty for new files.
- `matching`: No match for `original_lines`.
- `file_system`: File exists for new files, permissions, disk errors.
- `linting`: Linting failures in `vibedir` (e.g., undefined variables).

## Workflow
1. **User Input**:
   - User provides prompt (e.g., “add a save button”) and project directory to `vibedir` (12:59 AM MDT, July 18, 2025).
2. **vibedir Orchestrates**:
   - Reads `config.yaml` (e.g., `context_lines: 10`).
   - Calls `prepdir` for file contents (e.g., `src/main.py`).
   - Sends prompt to LLM, receives JSON.
   - Commits or backs up state (Git or files).
   - Passes JSON to `ApplyDirChanges`.
3. **ApplyDirChanges**:
   - Parses JSON, creates `ApplyDirFileChange` objects with `file`.
   - Validates structure, delegates to `ApplyDirFileChange`.
   - Returns `List[ApplyDirError]`.
4. **ApplyDirFileChange**:
   - Validates `original_lines`, `changed_lines` (syntax, additions).
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
   - Runs linters (e.g., `pylint`, `markdownlint`) on temporary files, returns `List[ApplyDirError]`.
   - On success: Moves temporary files to codebase, commits (e.g., `git commit -m "Applied changes"`).
   - On errors: Displays `List[ApplyDirError]` or queries LLM, discards temporary files.
   - On rejection: Reverts via Git (e.g., `git reset --hard`) or backups.

## Git and Linting (vibedir)
- **Git Integration**:
  - **Before Validation**: Commit (e.g., `git commit -m "Pre-applydir changes"`) or backup files.
  - **After Application**: Commit changes or revert on errors/rejection.
  - **Non-Git Projects**: Use file backups.
- **Linting**:
  - Runs linters on temporary files (e.g., `.applydir_temp`).
  - Returns `List[ApplyDirError]` with `error_type: "linting"`.
  - Tools: `pylint` (Python), `markdownlint` (Markdown).

## Validation Rules
- **ApplyDirChanges**: JSON is an array, `file` paths valid, `changes` non-empty.
- **ApplyDirFileChange**:
  - Existing files: `changed_lines` valid syntax, additions start with `original_lines`.
  - New files: `changed_lines` non-empty, valid syntax.
- **ApplyDirApplicator**: Path non-existence for new files, matching for existing files.
- **ApplyDirMatcher**: Fuzzy matching for `original_lines`.

## Python Best Practices
- **PEP 8**: Clear names (e.g., `ApplyDirError`, `ApplyDirFileChange`).
- **PEP 20**: Explicit `change` in `ApplyDirError`, simple class roles.
- **Type Safety**: Pydantic for type-safe errors and changes.
- **Testability**: Small classes and structured errors for testing.
- **Documentation**: Plan docstrings for all classes and methods.

## Edge Cases and Mitigations
1. **New File Creation**: Validate non-existent path in `ApplyDirApplicator`.
2. **Unmatched original_lines**: `ApplyDirMatcher` uses fuzzy matching, returns `ApplyDirError`.
3. **Invalid Syntax**: `ApplyDirFileChange` validates syntax, returns `ApplyDirError`.
4. **Short Files**: `vibedir`’s prompt allows all lines.
5. **File System Issues**: `ApplyDirApplicator` catches errors, returns `ApplyDirError`.
6. **Linting Failures**: `vibedir` catches linting issues, returns `ApplyDirError`.
7. **Rollback**: `vibedir` reverts via Git or backups.

## Next Steps
- Finalize `ApplyDirError`:
  - Define `error_type` enum (e.g., `Literal["json_structure", ...]`).
  - Specify truncation for large `original_lines`/`changed_lines`.
- Specify `ApplyDirMatcher` settings (e.g., `difflib` threshold).
- Plan logging format for `ApplyDirApplicator`.
- Detail `vibedir`’s Git/backup and linting strategy.
- Design test cases for all scenarios.