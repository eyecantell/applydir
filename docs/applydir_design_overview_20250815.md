# applydir Design Overview (August 14, 2025)

## Overview
The `applydir` project automates code changes by applying LLM-generated modifications to a codebase, achieving >95% reliability. It works with `prepdir` (supplies full file contents) and `vibedir` (crafts prompts, communicates with the LLM, and orchestrates user interaction). Changes are specified in a JSON array of file objects, using a unified "replace" approach where `original_lines` are replaced with `changed_lines` for modifications, additions, or creations, and an explicit `"action": "delete"` field for file deletions. The design supports modifications, additions, deletions within files, new file creation, and full file deletion, with relative file paths matching `prepdir`’s output.

## Core Design Principles
- **Unified Replace Approach**: Modifications, additions, and creations are treated as replacements:
  - Existing files: Replace `original_lines` (default ≥5 lines, configurable, minimum 3, as specified by `vibedir`) with `changed_lines`.
  - New files: `original_lines` is empty (`[]`), and `changed_lines` contains the full content.
- **File Deletion**: An explicit `"action": "delete"` field in a file object indicates the file should be deleted, omitting or ignoring the `changes` array.
- **Reliability (>95%)**: For existing files, ≥5 lines in `original_lines` (configurable, min 3) ensure unique matching in most cases. The library function `calculate_min_context(file_content: List[str]) -> int` from `min_context.py` (in vibedir) determines the minimal number of lines needed for all consecutive line sets to be unique if multiple matches occur, allowing `vibedir` to request precise context from the LLM. Fuzzy matching handles minor file changes, and new file creation validates non-existent paths.
- **Minimal JSON**: The JSON includes only `file`, optional `action`, and `changes` (with `original_lines` and `changed_lines` for `"action": "replace"`), reducing output token usage. The `action` field adds minimal overhead for clarity.
- **Relative Paths**: File paths (e.g., `src/main.py`) match `prepdir`’s output relative to the base directory (e.g., `/path/to/project`).
- **Validation Simplicity**: `applydir` validates JSON structure, syntax, `original_lines` matching, file existence for deletions, and non-existent paths for new files.

## JSON Format
The LLM returns a JSON array of file objects, each with a relative path, an optional `action`, and a list of changes for replacements.

```json
[
  {
    "file": "<relative_file_path>",
    "action": "delete_file" // Optional; if present, must be "delete_file", "create_file", or "replace_lines" (default)
  },
  {
    "file": "<relative_file_path>",
    "action": "replace_lines", // Optional, default for backward compatibility
    "changes": [
      {
        "original_lines": [<at least 5 lines for existing files (configurable, min 3), or all lines for files <5 lines, or empty for new files>],
        "changed_lines": [<new lines, includes original_lines plus new lines for additions, subset for deletions, or full content for new files>]
      }
    ]
  }
]
```

### Fields
- **Top-Level**: Array of file objects.
- **File Object**:
  - `file`: Relative path (e.g., `src/main.py`, `README.md`) matching `prepdir`’s output.
  - `action`: Optional string, either `"delete_file"` (file deletion, no `changes` needed), `"create_file"` (requires `changes` with empty `original_lines`) or `"replace_lines"` (default, requires `changes`).
  - `changes`: Array of change objects for `"action": "replace_lines"` or missing `action`.
- **Change Object** (for `"action": "replace_lines"`):
  - `original_lines`: For existing files, ≥5 lines (configurable, min 3, or all lines for short files) to ensure a unique match. For new files, empty (`[]`).
  - `changed_lines`: New lines, including `original_lines` plus added lines for additions, a subset for deletions, or full content for new files.

### Example Cases
- **Modification (src/main.py)**: Replace 5 lines (e.g., a function) with a modified version (e.g., adding error handling).
- **Addition (src/main.py)**: Replace 5 lines with the same 5 lines plus new lines (e.g., a new function).
- **Deletion (src/main.py)**: Replace 5 lines with a subset, omitting deleted lines.
- **Creation (src/new_menu.py)**: Create a new file with `original_lines: []` and `changed_lines` containing the full content.
- **File Deletion (src/old_file.py)**: Specify `"action": "delete_file"`, omitting `changes`.
- **Addition (README.md)**: Replace 5 lines with 6 lines, adding a feature description.

### Merging Logic
- Changes within 5 lines (or as specified in `vibedir`’s `config.yaml`) of each other are merged into a single change by the LLM, combining `original_lines` and `changed_lines`.

## Workflow
1. **User Input**:
   - User provides a prompt to `vibedir` (e.g., “delete src/old_file.py, add a save button to src/main.py”) and specifies the project directory or files.
2. **vibedir Orchestrates**:
   - Reads `config.yaml` (e.g., `context_lines: 5`, `allow_file_deletion: true`).
   - Calls `prepdir` to supply full file contents with relative paths (e.g., `src/main.py`, `README.md`).
   - Sends a prompt with user instructions, file contents, and JSON format requirements (specifying ≥5 lines in `original_lines` for existing files, empty for new files, `"action": "delete"` for deletions).
   - Sends the prompt to the LLM and receives the JSON array response.
   - Parses the JSON and passes it to `applydir` for validation.
3. **applydir Validates**:
   - Validates the JSON:
     - Ensure it’s an array of file objects with valid relative `file` paths.
     - For `"action": "delete_file"`, verify the file exists; ignore `changes`.
     - For `"action": "replace_lines"` or missing `action`, ensure non-empty `changes` arrays.
     - For `"action": "create_file"`, ensure empty `changes.original_lines` array and non-empty `changes.changed_lines` array.
     - For existing files (`original_lines` non-empty):
       - Confirm `original_lines` matches the file (exact or fuzzy match via `difflib`) exactly once.
       - Raise multiple matches error if more than one match is found so `vibedir` can request more context
     - For new files (`original_lines` empty):
       - Verify the `file` path does not yet exist.
       - Check `changed_lines` is non-empty.
     - Return errors to `vibedir` (e.g., “Unmatched original_lines in src/main.py”, “File src/new_menu.py already exists”).
4. **vibedir Handles Errors**:
   - On multiple matches, calls `calculate_min_context(file_content)` to determine the minimal lines needed for uniqueness, then queries the LLM with the exact number.
   - For other errors, displays to the user or sends to the LLM for correction (e.g., “Fix unmatched lines”).
5. **vibedir Displays Diff**:
   - If validation succeeds and `auto_display_diff` is configured, generates a diff-like view (e.g., unified diff for replacements, full `changed_lines` for new files, “Delete src/old_file.py” for deletions).
   - Presents the diff to the user for approval (e.g., via CLI or UI).
6. **User Approval**:
   - User reviews the diff and approves or rejects changes.
   - Approved changes/deletions are compiled into a new JSON (a subset if some changes are rejected).
7. **applydir Applies Changes**:
   - Receives the approved JSON from `vibedir`.
   - For each file:
     - If `"action": "delete_file"`, delete the file.
     - If `"action": "replace_lines"` or missing `action`:
       - If `original_lines` non-empty, match it in the file and replace with `changed_lines`.
     - If `"action": "create_file"`:
       - If `original_lines` empty, create the file with `changed_lines`.
   - Logs changes and errors (e.g., unmatched `original_lines`, file deletion failures).

## Component Roles
- **prepdir**:
  - Supplies full file contents with relative paths (e.g., `src/main.py`, `README.md`) relative to the base directory (e.g., `/path/to/project`).
  - Example output format:
    ```
    File listing generated 2025-08-14 21:44:00.123456 by prepdir version 0.14.1
    Base directory is '/path/to/project'
    =-=-=-=-=-=-=-= Begin File: 'src/main.py' =-=-=-=-=-=-=-=
    print("Hello, World!")
    =-=-=-=-=-=-=-= End File: 'src/main.py' =-=-=-=-=-=-=-=
    ```
- **vibedir**:
  - Reads `config.yaml` (e.g., `context_lines: 5`, `allow_file_deletion: true`) to set minimum lines and deletion policy.
  - Calls `prepdir` for file contents.
  - Crafts and sends the LLM prompt, receives and parses the JSON response.
  - Calls `calculate_min_context(file_content)` if multiple matches occur, requesting precise context from the LLM.
  - Passes the JSON to `applydir` for validation.
  - Handles errors by calling the context function, querying the LLM, or displaying to the user.
  - Generates a diff view and manages user approval.
- **applydir**:
  - Validates the JSON structure, `action` field, `changed_lines` syntax, `original_lines` matching, and file existence/non-existence.
  - Applies changes by deleting files, replacing `original_lines` with `changed_lines`, or creating new files.
  - Returns errors to `vibedir` and logs changes.
- **min_context.py**:
  - A library (in `vibedir`) containing the function `calculate_min_context(file_content: List[str]) -> int`.
  - Analyzes a file to determine the minimum number of consecutive lines needed for all sets of consecutive lines to be unique.
  - Used by `vibedir` when `ApplydirMatcher` reports multiple matches, informing the LLM prompt the minumum number of lines needed for context.

## Config.yaml for vibedir
```yaml
context_lines: 5
allow_file_deletion: true
auto_display_diff: true
```
- `context_lines`: Minimum lines for `original_lines` in existing files (min 3, default 5). Included in the LLM prompt.
- `allow_file_deletion`: Enables/disables file deletion via `"action": "delete"`.
- `auto_display_diff`: Enables/disables automatic diff display after changes received.
- Adjustable (e.g., `context_lines: 10`, `allow_file_deletion: false`, `auto_display_diff: false`).

## Prompt Design (Managed by vibedir)
```
You are an expert code editor. For the provided files, apply the requested changes and return a JSON array with the following structure:
[
  {
    "file": "<relative_file_path>",
    "action": "<delete_file|replace_lines|create_file>", // Optional; "replace_lines" is default
    "changes": [ // Required for "replace_lines" and "create_file", ignored for "delete_file"
      {
        "original_lines": [<at least <context_lines> lines for existing files, or all lines for files shorter than 5, or empty for new files>],
        "changed_lines": [<new lines, includes original_lines plus new lines for additions, subset for deletions, or full content for new files>]
      }
    ]
  }
]
- All changes (modifications, additions, creations) for "action": "replace_lines" are treated as replacements (changed_lines for original_lines).
- For file deletion, use "action": "delete_file" and omit or set "changes" to [].
- For existing files, include at least <context_lines> lines in original_lines (or all lines for files shorter than <context_lines>) to ensure a unique match.
- For additions/modifications, include <context_lines> lines for context in original_lines, and include all lines that are to replace original_lines in changed_lines.
- For deletions within a file, include the lines to delete in original_lines (with surrounding lines to reach <context_lines>) and exclude deleted lines from changed_lines.
- For new files, use "action": "create_file", empty original_lines ([]) and include the full content in changed_lines.
- Merge changes within <context_lines> lines of each other into a single change for existing files.
- Ensure changed_lines are syntactically correct for the language (e.g., Python for .py files, Markdown for .md files).
- Use relative file paths (e.g., src/main.py) matching the provided file listing.

Files:
- src/main.py:
<insert full file content from prepdir>
- README.md:
<insert full file content from prepdir>

Changes: <user-supplied prompt, e.g., "Delete src/old_file.py, add a save button to src/main.py">
```

## Validation Rules (applydir)
- **JSON Structure**:
  - Must be an array of file objects with valid relative `file` paths.
  - `action` must be `"delete_file"`, `"replace_lines"`, `"create_file"`, or absent (defaults to `"replace_lines"`).
  - For `"action": "delete_file"`, `changes` is optional and ignored.
  - For `"action": "replace_lines"`, `changes.original_lines` and `changes.changed_lines` must be non-empty.
  - For `"action": "create_file"`, `changes.original_lines` must be empty and `changes.changed_lines` must be non-empty.
- **File Deletion (`"action": "delete_file"`)**:
  - Verify the `file` path exists in the project directory.
- **Existing Files (`"action": "replace_lines"`, `original_lines` non-empty)**:
  - Confirm `original_lines` matches the file (exact or fuzzy match via `difflib`) exactly once.
- **New Files (`"action": "create_file"`, `original_lines` empty)**:
  - Verify the `file` path does not exist.
  - Check `changed_lines` is non-empty and has valid syntax.
- **Context Lines**:
  - Do not enforce `context_lines` ≥ 3 via configuration, we will just check to see if we get a exactly one match
  - If multiple matches, call `calculate_min_context(file_content)` to determine the exact number of lines needed.
- **Error Handling**:
  - Return structured errors to `vibedir` (e.g., JSON with messages like “Unmatched original_lines in src/main.py”, “File src/old_file.py does not exist for deletion”).

## Ensuring >95% Reliability
- **Unique Matching**: The prompt specifies ≥5 lines (configurable, min 3) in `original_lines` for existing files. `calculate_min_context(file_content)` ensures uniqueness by calculating the minimal k where all consecutive k-line sets are unique. Fuzzy matching (e.g., `difflib`) handles minor file changes.
- **Deletion Safety**: Validating file existence for `"action": "delete_file"` prevents errors. `allow_file_deletion` config prevents accidental deletions.
- **Creation Safety**: Validating non-existent `file` paths for new files prevents overwrites.
- **Validation**: `applydir` checks syntax, matching, and file existence, returning errors for `vibedir` to handle.
- **User Approval**: `vibedir`’s diff view and approval process ensure only correct changes are applied.
- **Clear Prompts**: `vibedir`’s precise instructions reduce LLM errors.

## Edge Cases and Mitigations
1. **New File Creation**:
   - **Challenge**: LLM specifies an existing file path for creation.
   - **Mitigation**: `applydir` validates that the `file` path does not exist for empty `original_lines`.
2. **File Deletion**:
   - **Challenge**: LLM specifies a non-existent file for deletion.
   - **Mitigation**: `applydir` validates file existence for `"action": "delete"`.
3. **Multiple Matches**:
   - **Challenge**: `original_lines` matches multiple locations in a file.
   - **Mitigation**: `ApplydirMatcher` reports multiple matches, `vibedir` calls `calculate_min_context(file_content)` to get the min k, and queries the LLM once.
4. **Large Additions**:
   - **Challenge**: Large additions increase token usage.
   - **Mitigation**: Use 5 lines in `original_lines`, duplicated in `changed_lines` plus new lines. Full file input ensures context.
5. **File Changes**:
   - **Challenge**: Edits shift content in existing files.
   - **Mitigation**: Fuzzy matching of `original_lines`. `calculate_min_context(file_content)` provides min k if needed.
6. **Short Files**:
   - **Challenge**: File has <5 lines.
   - **Mitigation**: Use all lines in `original_lines`.
7. **LLM Errors**:
   - **Challenge**: Incorrect `original_lines`, invalid syntax, or existing path for new files.
   - **Mitigation**: `applydir` validates syntax, matching, and file existence. `vibedir` handles errors via user or LLM.

## Dependencies
- **prepdir**: Supplies file contents and provides `load_config` and `configure_logging`.
- **Pydantic**: For JSON parsing, validation, and error handling.
- **difflib**: For fuzzy matching in `ApplydirMatcher`.
- **PyYAML**: For parsing `config.yaml` (via `prepdir`’s `load_config`).
- **dynaconf**: For configuration merging and overrides.

## Next Steps
- Implement the library function `calculate_min_context(file_content: List[str]) -> int` in `calculate_min_context.py`.
- Update `ApplydirChanges` and `ApplydirApplicator` to handle `action` field and context line validation.
- Test LLM prompt with `action` and configurable `context_lines`.
- Create test cases for deletions, multiple matches, short files, and large files.
- Plan `vibedir`’s diff view for deletions (e.g., “Delete src/old_file.py”).