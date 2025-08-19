# applydir Class Design Document (August 19, 2025)

## Overview
The `applydir` project automates code changes with >95% reliability, integrating with `prepdir` (file contents) and `vibedir` (LLM prompts, Git, linting). Changes are specified in a JSON array of file objects, using `"replace_lines"` for line-level changes, `"create_file"` for new files, and `"delete_file"` for file deletions. Paths are resolvable within the project directory, matching `prepdir`’s output.

## Core Design Principles
- **Unified Replace Approach**: `"replace_lines"` replaces `original_lines` with `changed_lines`. `"create_file"` uses empty `original_lines`.
- **File Deletion**: `"delete_file"` omits `changes`, controlled by `allow_file_deletion`.
- **Reliability (>95%)**: Hybrid matching (exact first, optional fuzzy fallback) with configurable normalization (whitespace handling, case sensitivity, threshold, metric) per file type. Multiple matches trigger `vibedir` to use `min_context.calculate_min_context` for LLM follow-up.
- **Minimal JSON**: Only `file`, optional `action`, and `changes`.
- **Resolvable Paths**: Relative or absolute paths resolved in project directory.
- **Validation Simplicity**: Validates JSON, actions, paths, syntax, and matching.
- **Git and Linting**: Handled by `vibedir`.
- **Configuration**: Uses `prepdir`’s `load_config` for `config.yaml`, with CLI/`config_override`.

## JSON Format
```json
[
  {
    "file": "<relative_or_absolute_file_path>",
    "action": "<delete_file|replace_lines|create_file>", // Optional; "replace_lines" default
    "changes": [
      {
        "original_lines": [<non-empty for replace_lines, empty for create_file>],
        "changed_lines": [<new lines or full content>]
      }
    ]
  }
]
```

### Fields
- **File Object**:
  - `file`: Path (e.g., `src/main.py`).
  - `action`: `"delete_file"`, `"replace_lines"`, `"create_file"`, or absent (`"replace_lines"`).
  - `changes`: Optional for `"delete_file"`, required for `"replace_lines"` and `"create_file"`.
- **Change Object**:
  - `original_lines`: Non-empty for `"replace_lines"`, empty for `"create_file"`.
  - `changed_lines`: Non-empty for replacements or new files.

### Example Cases
See JSON Format in `applydir_design_overview.md`.

## Configuration
Uses `config.yaml`:
```yaml
validation:
  non_ascii:
    default: warning
    rules:
      - extensions: [".py", ".js"]
        action: error
      - extensions: [".md", ".markdown"]
        action: ignore
      - extensions: [".json", ".yaml"]
        action: warning
  allow_file_deletion: true
matching:
  whitespace:
    default: collapse
    rules:
      - extensions: [".py", ".js"]
        handling: remove
      - extensions: [".md", ".txt"]
        handling: ignore
      - extensions: [".json", ".yaml"]
        handling: strict
  similarity:
    default: 0.95
    rules:
      - extensions: [".py", ".js"]
        threshold: 0.8
      - extensions: [".md", ".txt"]
        threshold: 0.9
      - extensions: [".json", ".yaml"]
        threshold: 0.95
  similarity_metric:
    default: sequence_matcher
    rules:
      - extensions: [".py", ".js"]
        metric: levenshtein
  use_fuzzy:
    default: true
    rules:
      - extensions: [".json", ".yaml"]
        use_fuzzy: false
```

## Class Structure
1. **ApplydirError (Pydantic)**:
   - **Purpose**: JSON-serializable error, warning, or success confirmation.
   - **Attributes**:
     - `change: Optional[ApplydirFileChange]`: Associated change, if applicable.
     - `error_type: ErrorType`: Enum (e.g., `json_structure`, `file_path`, `no_match`, `multiple_matches`, `file_not_found`, `file_already_exists`, `file_system`, `permission_denied`, `file_changes_successful`, `invalid_change`).
     - `severity: ErrorSeverity`: Enum (`error`, `warning`, `info`).
     - `message: str`: Descriptive message.
     - `details: Optional[Dict]`: Additional context (e.g., `match_count` for `multiple_matches`, `action` and `change_count` for `file_changes_successful`).
   - **Validation**: Valid enums, non-empty `message`, `details` defaults to `{}`.
   - **Usage**: Errors (`error`, `warning`) for validation failures, success confirmations (`info`) for successful file changes.

2. **ApplydirChanges (Pydantic)**:
   - **Purpose**: Parse and validate JSON array, create `ApplydirFileChange` objects.
   - **Attributes**:
     - `file_entries: List[FileEntry]`, where `FileEntry` is:
       - `file: str`: Relative file path.
       - `action: Optional[str] = "replace_lines"`: `"delete_file"`, `"replace_lines"`, or `"create_file"`.
       - `changes: Optional[List[Dict]]`: Changes for `"replace_lines"` or `"create_file"`.
   - **Validation**:
     - Array of file entries, valid `file` paths (resolvable within `base_dir`), `action` in `{delete_file, replace_lines, create_file}` or absent.
     - `"delete_file"`: File exists, `changes` ignored.
     - `"replace_lines"`: Non-empty `changes.original_lines` and `changes.changed_lines`.
     - `"create_file"`: Empty `changes.original_lines`, non-empty `changes.changed_lines`.
     - Warn on extra fields.
     - `skip_file_system_checks` in `validate_changes` for testing.
   - **Error Handling**: Returns `List[ApplydirError]` with `error` or `warning` severity for failures, `info` severity with `file_changes_successful` for successful file changes.

3. **ApplydirFileChange (Pydantic)**:
   - **Purpose**: Container for a single change for `"replace_lines"`, `"create_file"`, or `"delete_file"`.
   - **Attributes**:
     - `file_path: Path`: Resolved file path within project directory.
     - `original_lines: List[str]`: Lines to replace or empty for `"create_file"`.
     - `changed_lines: List[str]`: New lines or full content.
     - `action: ActionType`: Enum (`replace_lines`, `create_file`, `delete_file`).
   - **Validation**:
     - Non-empty `file_path`.
     - Non-ASCII per `config.yaml`.
     - `"replace_lines"`: Non-empty `original_lines` and `changed_lines`.
     - `"create_file"`: Empty `original_lines`, non-empty `changed_lines`.
     - `"delete_file"`: Empty `original_lines` and `changed_lines`.
   - **Error Handling**: Returns `List[ApplydirError]` with `error` or `warning` severity.

4. **ApplydirMatcher**:
   - **Purpose**: Match `original_lines` using hybrid approach (exact first, optional fuzzy with `difflib` or Levenshtein).
   - **Attributes**: `similarity_threshold: float`, `max_search_lines: Optional[int]`, `case_sensitive: bool`, `config: Dict` (for whitespace, similarity, use_fuzzy, similarity_metric).
   - **Methods**: `match(file_content: List[str], change: ApplydirFileChange) -> Tuple[Optional[Dict], List[ApplydirError]]`
   - **Error Handling**: Returns `ApplydirError` with `error_type=NO_MATCH` for no matches or `MULTIPLE_MATCHES` for multiple matches, including `match_count` in `details`.

5. **ApplydirApplicator**:
   - **Purpose**: Apply changes using `ApplydirFileChange` and `ApplydirMatcher`.
   - **Attributes**: `base_dir: str`, `changes: ApplydirChanges`, `matcher: ApplydirMatcher`, `logger`, `config_override: Optional[Dict]`.
   - **Methods**:
     - `apply_changes() -> List[ApplydirError]`
     - `apply_single_change(change: ApplydirFileChange) -> List[ApplydirError]`
     - `delete_file(file_path: str) -> List[ApplydirError]`
     - `write_changes(file_path: str, changed_lines: List[str], range: Optional[Dict])`
   - **Error Handling**: Returns `List[ApplydirError]` with `error` or `warning` severity for file system/matching errors, `info` severity with `file_changes_successful` for successful file changes.

6. **vibedir.min_context.calculate_min_context**:
   - **Purpose**: Compute minimal k for unique k-line sets.
   - **Inputs**: `file_content: List[str]`
   - **Output**: `int` (min k) or error.
   - **Logic**: Check k=1, 2, 3, etc., until all k-line windows are unique.
   - **Usage**: Called by `vibedir` for `MULTIPLE_MATCHES` errors.

## CLI Utility
```bash
applydir changes.json --base-dir /path/to/project --no-allow-file-deletion --non-ascii-action=error --log-level=DEBUG
```

## Error Types
- `json_structure`: Invalid JSON or `action`.
- `file_path`: Invalid path or path outside project directory.
- `changes_empty`: Empty `changes` for `"replace_lines"` or `"create_file"`.
- `syntax`: Invalid `changed_lines` syntax.
- `empty_changed_lines`: Empty `changed_lines`.
- `no_match`: No matches for `original_lines`.
- `multiple_matches`: Multiple matches for `original_lines`.
- `file_not_found`: File does not exist for `"delete_file"` or `"replace_lines"`.
- `file_already_exists`: File exists for `"create_file"`.
- `file_system`: Other file operation errors (e.g., disk full).
- `permission_denied`: Access denied for file operations.
- `configuration`: Invalid config (e.g., deletion disabled).
- `linting`: Linting errors (via `vibedir`).
- `file_changes_successful`: All changes to a file (`create_file`, `replace_lines`, `delete_file`) applied successfully.
- `orig_lines_empty`: Empty `original_lines` for `"replace_lines"`.
- `orig_lines_not_empty`: Non-empty `original_lines` for `"create_file"`.
- `invalid_change`: Invalid change content for the specified action.

## Error Format
```json
[
  {
    "change": {"file_path": "src/main.py", "original_lines": ["..."], "changed_lines": ["..."], "action": "replace_lines"},
    "error_type": "multiple_matches",
    "severity": "error",
    "message": "Multiple matches found for original_lines",
    "details": {"file": "src/main.py", "match_count": 3}
  },
  {
    "change": {"file_path": "src/main.py", "original_lines": ["..."], "changed_lines": ["..."], "action": "replace_lines"},
    "error_type": "file_changes_successful",
    "severity": "info",
    "message": "All changes to file applied successfully",
    "details": {"file": "src/main.py", "action": "replace_lines", "change_count": 2}
  }
]
```

## Workflow
See Workflow in `applydir_design_overview.md`.

## Dependencies
- **prepdir**: `load_config`, `configure_logging`.
- **Pydantic**: JSON parsing/validation.
- **difflib**: Fuzzy matching.
- **PyYAML**: Parse `config.yaml`.
- **dynaconf**: Configuration merging.

## Next Steps
- Test all `ErrorType` values, including `file_changes_successful` for successful file changes (`create_file`, `replace_lines`, `delete_file`) and edge cases (multiple matches, short files).
- Integrate `vibedir.min_context.calculate_min_context` for `multiple_matches` errors.
- Implement `vibedir`’s diff view for `"delete_file"` and success confirmations using `file_changes_successful`.
- Add `ValidationError` handling in `main.py`.