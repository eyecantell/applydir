# applydir Design Overview (August 15, 2025)

## Overview
The `applydir` project automates code changes by applying LLM-generated modifications to a codebase, achieving >95% reliability. It integrates with `prepdir` (supplies file contents) and `vibedir` (manages LLM prompts, user interaction, and Git/linting). Changes are specified in a JSON array of file objects, using a unified replace approach for `"action": "replace_lines"` (modifications, additions, deletions within files), `"create_file"` for new files, and `"delete_file"` for file deletions. File paths are relative, matching `prepdir`’s output.

## Core Design Principles
- **Unified Replace Approach**: For `"replace_lines"`, replace `original_lines` (default ≥5 lines, configurable, min 3) with `changed_lines`. For `"create_file"`, `original_lines` is empty, and `changed_lines` contains full content.
- **File Deletion**: `"action": "delete_file"` indicates file deletion, ignoring `changes`.
- **Reliability (>95%)**: ≥5 lines in `original_lines` ensure unique matching. The `vibedir.min_context.calculate_min_context(file_content: List[str]) -> int` function determines the minimal k for unique k-line sets if multiple matches occur, enabling a single LLM follow-up. Fuzzy matching handles minor changes; new file validation ensures non-existent paths.
- **Minimal JSON**: Includes only `file`, optional `action`, and `changes`, with `action` adding minimal overhead.
- **Relative Paths**: Paths (e.g., `src/main.py`) are relative to the base directory.
- **Validation Simplicity**: Validates JSON structure, `action`, paths, syntax, and matching.

## JSON Format
The LLM returns a JSON array of file objects:

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
- **Top-Level**: Array of file objects.
- **File Object**:
  - `file`: Relative path (e.g., `src/main.py`).
  - `action`: Optional; `"delete_file"` (no `changes` needed), `"create_file"` (empty `original_lines`), or `"replace_lines"` (default, non-empty `changes`).
  - `changes`: Array of change objects for `"replace_lines"` or `"create_file"`.
- **Change Object**:
  - `original_lines`: ≥5 lines (configurable, min 3) for existing files, empty for `"create_file"`.
  - `changed_lines`: New lines for replacements or full content for new files.

### Example Cases
- **Modification**: `"replace_lines"` in `src/main.py`, replacing 5 lines (e.g., a function) with a modified version.
- **Addition**: `"replace_lines"` in `src/main.py`, replacing 5 lines with additional lines (e.g., new function).
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
3. **applydir Validates**: Validates per Validation Rules, returning errors to `vibedir`.
4. **vibedir Handles Errors**: On multiple matches, calls `vibedir.min_context.calculate_min_context` to get min k, queries LLM. Other errors are shown to user or sent to LLM.
5. **vibedir Displays Diff**: If `auto_display_diff: true`, shows unified diff for `"replace_lines"`, full content for `"create_file"`, or “Delete <file>” for `"delete_file"`.
6. **User Approval**: User approves/rejects changes, creating a new JSON subset.
7. **applydir Applies Changes**: Deletes files (`"delete_file"`), replaces lines (`"replace_lines"`), or creates files (`"create_file"`), logging errors.

## Component Roles
- **prepdir**: Supplies file contents with relative paths (e.g., `src/main.py`).
- **vibedir**: Manages LLM prompts, calls `min_context.calculate_min_context` for multiple matches, handles errors, generates diff view, and manages Git/linting.
- **applydir**: Validates JSON, applies changes, and returns errors.
- **min_context.py**: Library in `vibedir` with `calculate_min_context` to compute minimal unique line count.

## Config.yaml for vibedir
```yaml
context_lines: 5
allow_file_deletion: true
auto_display_diff: true
```
- `context_lines`: Default 5, min 3, for `original_lines` in existing files.
- `allow_file_deletion`: Enables/disables `"delete_file"`.
- `auto_display_diff`: Enables/disables automatic diff display.

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
- **JSON Structure**:
  - Array of file objects with valid `file` paths.
  - `action`: `"delete_file"`, `"replace_lines"`, `"create_file"`, or absent (`"replace_lines"`).
  - `"delete_file"`: `changes` optional, ignored.
  - `"replace_lines"`: Non-empty `changes.original_lines` and `changes.changed_lines`.
  - `"create_file"`: Empty `changes.original_lines`, non-empty `changes.changed_lines`.
- **File Deletion (`"delete_file"`)**: Verify file exists.
- **Existing Files (`"replace_lines"`, non-empty `original_lines`)**: Exactly one match via `difflib`.
- **New Files (`"create_file"`)**: Verify path does not exist, `changed_lines` valid.
- **Error Handling**: Return `List[ApplydirError]` (e.g., “Unmatched original_lines”, “File exists for create_file”).

## Ensuring >95% Reliability
- **Unique Matching**: Default 5 lines in `original_lines`, with `vibedir.min_context.calculate_min_context` for multiple matches. Fuzzy matching via `difflib`.
- **Deletion Safety**: Validate file existence for `"delete_file"`, use `allow_file_deletion`.
- **Creation Safety**: Validate non-existent paths for `"create_file"`.
- **Validation**: Check syntax, matching, and paths.
- **User Approval**: `vibedir`’s diff view ensures correct changes.
- **Clear Prompts**: Precise LLM instructions reduce errors.

## Edge Cases and Mitigations
- **New File Creation**: Validate non-existent path for `"create_file"`.
- **File Deletion**: Validate file existence for `"delete_file"`.
- **Multiple Matches**: Call `calculate_min_context` to query LLM with min k.
- **Large Additions**: Use `context_lines` in `original_lines`, full `changed_lines`.
- **Short Files**: Use all lines in `original_lines`.
- **LLM Errors**: Validate syntax, matching, and paths; handle via `vibedir`.

## Dependencies
- **prepdir**: Supplies file contents, `load_config`, `configure_logging`.
- **Pydantic**: JSON parsing, validation, error handling.
- **difflib**: Fuzzy matching in `ApplydirMatcher`.
- **PyYAML**: Parse `config.yaml` via `prepdir`.
- **dynaconf**: Configuration merging.

## Next Steps
- Implement `vibedir.min_context.calculate_min_context`.
- Update `ApplydirChanges` and `ApplydirApplicator` for new actions.
- Test LLM prompt with new actions and `context_lines`.
- Create test cases for all actions, multiple matches, and short files.
- Plan `vibedir`’s diff view for `"delete_file"`.