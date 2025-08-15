# applydir Class Design Document (August 15, 2025)

## Overview
The `applydir` project automates code changes with >95% reliability, integrating with `prepdir` (file contents) and `vibedir` (LLM prompts, Git, linting). Changes are specified in a JSON array of file objects, using `"replace_lines"` for line-level changes, `"create_file"` for new files, and `"delete_file"` for file deletions. Paths are resolvable within the project directory, matching `prepdir`’s output.

## Core Design Principles
- **Unified Replace Approach**: `"replace_lines"` replaces `original_lines` (default ≥5 lines, configurable, min 3) with `changed_lines`. `"create_file"` uses empty `original_lines`.
- **File Deletion**: `"delete_file"` omits `changes`.
- **Reliability (>95%)**: ≥5 lines in `original_lines`, with `vibedir.min_context.calculate_min_context` for unique matching. Fuzzy matching and path validation ensure reliability.
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
        "original_lines": [<≥5 lines (configurable, min 3) for existing files, or empty>],
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
  - `changes`: Required for `"replace_lines"` and `"create_file"`.
- **Change Object**:
  - `original_lines`: ≥5 lines for `"replace_lines"`, empty for `"create_file"`.
  - `changed_lines`: Replacement or full content.

### Example Cases
See JSON Format in `applydir_design_overview_20250815.md`.

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
use_temp_files: true
auto_display_diff: true
```

## Class Structure
1. **ApplydirError (Pydantic)**:
   - **Purpose**: JSON-serializable error/warning.
   - **Attributes**:
     - `change: Optional[ApplydirFileChange]`
     - `error_type: ErrorType` (e.g., `json_structure`, `file_path`, `matching`)
     - `severity: ErrorSeverity` (`error`, `warning`)
     - `message: str`
     - `details: Optional[Dict]` (e.g., `match_count`, `context_lines`)
   - **Validation**: Valid enums, non-empty `message`, `details` defaults to `{}`.

2. **ApplydirChanges (Pydantic)**:
   - **Purpose**: Parse/validate JSON, create `ApplydirFileChange` objects.
   - **Attributes**: `files: List[Dict[str, Union[str, str, List[ApplydirFileChange]]]]`
   - **Validation**:
     - Array of file objects, valid `file` paths, `action` in `{delete_file, replace_lines, create_file}` or absent.
     - `"delete_file"`: File exists, ignore `changes`.
     - `"replace_lines"`: Non-empty `changes.original_lines` and `changes.changed_lines`.
     - `"create_file"`: Empty `changes.original_lines`, non-empty `changes.changed_lines`.
     - Warn on extra fields.
   - **Error Handling**: Returns `List[ApplydirError]`.

3. **ApplydirFileChange (Pydantic)**:
   - **Purpose**: Validate single change for `"replace_lines"` or `"create_file"`.
   - **Attributes**: `file: str`, `original_lines: List[str]`, `changed_lines: List[str]`.
   - **Validation**:
     - Resolvable paths.
     - Non-ASCII per `config.yaml`.
     - `"create_file"`: Empty `original_lines`, non-empty `changed_lines`.
     - `"replace_lines"`: Non-empty `original_lines` (≥3 lines or all for short files).
   - **Error Handling**: Returns `List[ApplydirError]`.

4. **ApplydirMatcher**:
   - **Purpose**: Match `original_lines` using `difflib`.
   - **Attributes**: `similarity_threshold: float`, `max_search_lines: Optional[int]`, `context_lines: int` (default 5).
   - **Methods**: `match(file_content: List[str], change: ApplydirFileChange) -> Union[Dict, List[ApplydirError]]`
   - **Error Handling**: Returns `ApplydirError` for no/multiple matches, with `match_count`.

5. **ApplydirApplicator**:
   - **Purpose**: Apply changes using `ApplydirFileChange` and `ApplydirMatcher`.
   - **Attributes**: `base_dir: str`, `changes: ApplydirChanges`, `matcher: ApplydirMatcher`, `logger`, `config_override: Optional[Dict]`.
   - **Methods**:
     - `apply_changes() -> List[ApplydirError]`
     - `apply_single_change(change: ApplydirFileChange) -> List[ApplydirError]`
     - `write_changes(file_path: str, changed_lines: List[str], range: Optional[Dict])`
     - `delete_file(file_path: str) -> List[ApplydirError]`
   - **Error Handling**: Returns `List[ApplydirError]` for file system/matching errors.

6. **vibedir.min_context.calculate_min_context**:
   - **Purpose**: Compute minimal k for unique k-line sets.
   - **Inputs**: `file_content: List[str]`
   - **Output**: `int` (min k) or error.
   - **Logic**: Check k=1, 2, 3, etc., until all k-line windows are unique.
   - **Usage**: Called by `vibedir` for multiple matches.

## CLI Utility
```bash
applydir changes.json --base-dir /path/to/project --context-lines 5 --no-temp-files --allow-file-deletion true --non-ascii-action=error --log-level=DEBUG
```

## Error Types
- `json_structure`: Invalid JSON or `action`.
- `file_path`: Invalid path (e.g., non-existent for `"delete_file"`).
- `changes_empty`: Empty `changes` for `"replace_lines"`.
- `syntax`: Invalid `changed_lines` syntax.
- `empty_changed_lines`: Empty `changed_lines` for `"create_file"`.
- `matching`: No/multiple matches for `original_lines`.
- `file_system`: File operation errors.
- `linting`: Linting errors (via `vibedir`).
- `configuration`: Invalid config (e.g., `context_lines` < 3).

## Error Format
```json
[
  {
    "change": {"file": "src/main.py", "original_lines": ["..."], "changed_lines": ["..."]},
    "error_type": "matching",
    "severity": "error",
    "message": "Multiple matches found",
    "details": {"match_count": 3, "context_lines": 5}
  }
]
```

## Workflow
See Workflow in `applydir_design_overview_20250815.md`.

## Dependencies
- **prepdir**: `load_config`, `configure_logging`.
- **Pydantic**: JSON parsing/validation.
- **difflib**: Fuzzy matching.
- **PyYAML**: Parse `config.yaml`.
- **dynaconf**: Configuration merging.

## Next Steps
- Implement `vibedir.min_context.calculate_min_context`.
- Update `ApplydirChanges`/`ApplydirApplicator` for new actions.
- Test LLM prompt and test cases.
- Plan `vibedir`’s diff view for `"delete_file"`.