# applydir Design Overview (August 19, 2025)

## Overview
The `applydir` project automates code changes by applying LLM-generated modifications to a codebase, achieving >95% reliability. It integrates with `prepdir` (supplies file contents) and `vibedir` (manages LLM prompts, user interaction, and Git/linting). Changes are specified in a JSON array of file entries, using a unified replace approach for `"action": "replace_lines"` (modifications, additions, deletions within files), `"create_file"` for new files, and `"delete_file"` for file deletions. File paths are relative, matching `prepdir`’s output.

## Core Design Principles
- **Unified Replace Approach**: For `"replace_lines"`, replace `original_lines` (default ≥5 lines, configurable, min 3) with `changed_lines`. For `"create_file"`, `original_lines` is empty, and `changed_lines` contains full content.
- **File Deletion**: `"action": "delete_file"` indicates file deletion, ignoring `changes`.
- **Reliability (>95%)**: ≥5 lines in `original_lines` ensure unique matching. The `vibedir.min_context.calculate_min_context(file_content: List[str]) -> int` function determines the minimal k for unique k-line sets if multiple matches occur, enabling a single LLM follow-up. Hybrid matching (exact first, optional fuzzy fallback) handles minor changes; new file validation ensures non-existent paths.
- **Minimal JSON**: Includes only `file`, optional `action`, and `changes`, with `action` adding minimal overhead.
- **Relative Paths**: Paths (e.g., `src/main.py`) are relative to the base directory.
- **Validation Simplicity**: Validates JSON structure, `action`, paths, syntax, and matching.

## JSON Format
The LLM returns a JSON array of file entries:

```json
[
  {
    "file": "<relative_file_path>",
    "action": "delete_file" // Optional; "delete_file", "create_file", or "replace_lines" (default)
  },
  {
    "file": "<relative_file_path>",
    "action": "replace_lines", // Optional, default
    "changes": [
      {
        "original_lines": [<≥5 lines (configurable, min 3) for existing files, or all lines for short files, or empty for new files>],
        "changed_lines": [<new lines, includes original_lines plus additions, subset for deletions, or full content>]
      }
    ]
  },
  {
    "file": "<relative_file_path>",
    "action": "create_file",
    "changes": [
      {
        "original_lines": [],
        "changed_lines": [<full content>]
      }
    ]
  }
]
```

### Fields
- **Top-Level**: Array of file entries.
- **File Entry**:
  - `file`: Relative path (e.g., `src/main.py`).
  - `action`: Optional; `"delete_file"` (no `changes` needed), `"create_file"` (empty `original_lines`), or `"replace_lines"` (default, non-empty `changes`).
  - `changes`: Array of change objects for `"replace_lines"` or `"create_file"`.
- **Change Object**:
  - `original_lines`: ≥5 lines (configurable, min 3) for existing files, empty for `"create_file"`.
  - `changed_lines`: Modified lines for replacements or full content for new files.

### Example Cases
- **Modification**: `"replace_lines"` in `src/main.py`, replacing 5 lines (e.g., a function) with a modified version.
- **Addition**: `"replace_lines"` in `src/main.py`, replacing 5 lines with lines that include additional lines (e.g., new function).
- **Deletion**: `"replace_lines"` in `src/main.py`, replacing 5 lines with a subset.
- **Creation**: `"create_file"` for `src/new_menu.py`, with empty `original_lines` and full `changed_lines`.
- **File Deletion**: `"delete_file"` for `src/old_file.py`, no `changes`.
- **Addition (Prose)**: `"replace_lines"` in `README.md`, adding a feature description.

### Merging Logic
Changes within `context_lines` (default 5) are merged by the LLM into a single change.

## Workflow
1. **User Input**: User provides a prompt to `vibedir` (e.g., “delete src/old_file.py, add save button to src/main.py”) and project directory.
2. **vibedir Orchestrates**:
   - Reads `config.yaml` (`context_lines: 5`, `allow_file_deletion: true`, `auto_display_diff: true`).
   - Calls `prepdir` for file contents.
   - Sends LLM prompt (see Prompt Design), receives JSON.
   - Passes JSON to `applydir` for validation.
3. **applydir Validates**: Validates per Validation Rules, returning a `List[ApplydirError]` containing errors (severity `ERROR` or `WARNING`) or success confirmations (severity `INFO` with `FILE_CHANGES_SUCCESSFUL` for all changes to a file).
4. **vibedir Handles Errors and Successes**: On multiple matches, calls `vibedir.min_context.calculate_min_context` to get min k, queries LLM. Other errors are shown to user or sent to LLM. Success confirmations (`FILE_CHANGES_SUCCESSFUL`) are displayed with action-specific details (e.g., “All changes to src/main.py applied successfully”).
5. **vibedir Displays Diff**: If `auto_display_diff: true`, shows unified diff for `"replace_lines"`, full content for `"create_file"`, or “Delete <file>” for `"delete_file"`. Success confirmations use `FILE_CHANGES_SUCCESSFUL` details to indicate the action performed for the entire file.
6. **User Approval**: User approves/rejects changes, creating a new JSON subset.
7. **applydir Applies Changes**: Deletes files (`"delete_file"`), replaces lines (`"replace_lines"`), or creates files (`"create_file"`), returning `FILE_CHANGES_SUCCESSFUL` with action-specific details on success for all changes to a file, or logging errors for individual failed changes.

## Component Roles
- **prepdir**: Supplies file contents with relative paths (e.g., `src/main.py`).
- **vibedir**: Manages LLM prompts, calls `min_context.calculate_min_context` for multiple matches, handles errors and success confirmations, generates diff view, and manages Git/linting.
- **applydir**: Validates JSON, applies changes, and returns errors or success confirmations.
- **min_context.py**: Library in `vibedir` with `calculate_min_context` to compute minimal unique line count.

## Config.yaml for vibedir
```yaml
context_lines: 5
allow_file_deletion: true
auto_display_diff: true
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

## Prompt Design
The LLM prompt (managed by `vibedir`) specifies:
- JSON format per JSON Format section.
- For `"replace_lines"`, include ≥`context_lines` lines in `original_lines`, all replacement lines in `changed_lines`.
- For `"create_file"`, use empty `original_lines`, full content in `changed_lines`.
- For `"delete_file"`, omit `changes`.
- Merge changes within `context_lines` lines.
- Ensure `changed_lines` syntax matches file type (e.g., Python for `.py`).
- If multiple matches, provide exactly `<N>` lines as specified by `calculate_min_context`.

## Validation Rules
- **JSON Structure (in `ApplydirChanges`)**:
  - Array of file entries with valid `file` paths (contained within `base_dir`).
  - `action`: `"delete_file"`, `"replace_lines"`, `"create_file"`, or absent (`"replace_lines"`).
  - `"delete_file"`: `changes` optional, ignored.
  - `"replace_lines"`: Non-empty `changes.original_lines` and `changes.changed_lines`.
  - `"create_file"`: Empty `changes.original_lines`, non-empty `changes.changed_lines`.
  - Errors: `JSON_STRUCTURE` (invalid structure or action), `FILE_PATH` (invalid or out-of-bounds path).
- **Content Validation (in `ApplydirFileChange`)**:
  - Errors: `ORIG_LINES_EMPTY` (empty `original_lines` for `"replace_lines"`), `ORIG_LINES_NOT_EMPTY` (non-empty for `"create_file"`), `EMPTY_CHANGED_LINES` (empty `changed_lines`), `SYNTAX` (invalid syntax in `changed_lines`).
- **File System Existence (in `ApplydirApplicator`)**:
  - `"delete_file"`: Verify file exists. Errors: `FILE_NOT_FOUND` (does not exist), `PERMISSION_DENIED` (deletion disabled), `FILE_SYSTEM` (other failures, e.g., disk full).
  - `"replace_lines"`: Verify file exists. Errors: `FILE_NOT_FOUND` (does not exist).
  - `"create_file"`: Verify path does not exist. Errors: `FILE_ALREADY_EXISTS` (exists).
- **Configuration**: Validate `config.yaml` settings. Errors: `CONFIGURATION` (invalid settings), `LINTING` (linting failures, handled by `vibedir`).
- **Success Reporting**: On successful application of all changes to a file (`create_file`, `replace_lines`, `delete_file`), return `FILE_CHANGES_SUCCESSFUL` with `INFO` severity and `details` containing `file`, `action`, and `change_count` (e.g., `{"file": "src/main.py", "action": "replace_lines", "change_count": 1}`).

## Ensuring >95% Reliability
- **Unique Matching**: Default 5 lines in `original_lines`, with `vibedir.min_context.calculate_min_context` for multiple matches. Hybrid matching (exact first, optional fuzzy fallback) handles minor changes, with configurable whitespace, case sensitivity, similarity threshold, and metric per file type.
- **Deletion Safety**: Validate file existence for `"delete_file"`, use `allow_file_deletion`.
- **Creation Safety**: Validate non-existent paths for `"create_file"`.
- **Validation**: Check syntax, matching, and paths, with specific error types (`FILE_NOT_FOUND`, `FILE_ALREADY_EXISTS`, `PERMISSION_DENIED`, `FILE_SYSTEM`).
- **Success Confirmation**: Use `FILE_CHANGES_SUCCESSFUL` with action-specific details for clear user feedback on all changes to a file.
- **User Approval**: `vibedir`’s diff view ensures correct changes.
- **Clear Prompts**: Precise LLM instructions reduce errors.

## Edge Cases and Mitigations
- **New File Creation**: Validate non-existent path for `"create_file"` (`FILE_ALREADY_EXISTS`, `PERMISSION_DENIED`, `FILE_SYSTEM`).
- **File Deletion**: Validate file existence for `"delete_file"` (`FILE_NOT_FOUND`, `PERMISSION_DENIED`, `FILE_SYSTEM`).
- **Multiple Matches**: Call `calculate_min_context` to query LLM with min k (`MULTIPLE_MATCHES`).
- **Large Additions**: Use `context_lines` in `original_lines`, full `changed_lines`.
- **Short Files**: Use all lines in `original_lines`.
- **LLM Errors**: Validate syntax (`SYNTAX`), matching (`NO_MATCH`, `MULTIPLE_MATCHES`), and paths (`FILE_PATH`).
- **Success Cases**: Report `FILE_CHANGES_SUCCESSFUL` with `action` and `change_count` in `details` for all changes to a file (`create_file`, `replace_lines`, `delete_file`).

## Dependencies
- **prepdir**: Supplies file contents, `load_config`, `configure_logging`.
- **Pydantic**: JSON parsing, validation, error handling.
- **difflib**: Fuzzy matching in `ApplydirMatcher`.
- **PyYAML**: Parse `config.yaml` via `prepdir`.
- **dynaconf**: Configuration merging.

## Next Steps
- Implement `vibedir.min_context.calculate_min_context`.
- Test `ApplydirApplicator` with `pytest.tmp_path` for all actions.
- Test LLM prompt with new actions and `context_lines`.
- Create test cases for all `ErrorType` values, including `FILE_CHANGES_SUCCESSFUL` for success cases, multiple matches, and short files.
- Plan `vibedir`’s diff view for `"delete_file"`.