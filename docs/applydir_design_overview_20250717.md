# applydir Design Overview

## Overview
The `applydir` project automates code changes by applying LLM-generated modifications to a codebase, achieving >95% reliability. It works with `prepdir` (supplies full file contents) and `vibedir` (crafts prompts, communicates with the LLM, and orchestrates user interaction). Changes are specified in a JSON array of file objects, using a unified "replace" approach where `original_lines` are replaced with `changed_lines`. The design supports modifications, additions, deletions, and new file creation, with relative file paths matching `prepdir`’s output.

## Core Design Principles
- **Unified Replace Approach**: All changes (modifications, additions, deletions, creations) are treated as replacements:
  - Existing files: Replace `original_lines` (typically ≥10 lines, as specified by `vibedir`) with `changed_lines`.
  - New files: `original_lines` is empty (`[]`), and `changed_lines` contains the full content of the new file.
- **Reliability (>95%)**: For existing files, ≥10 lines in `original_lines` ensure unique matching. Fuzzy matching handles minor file changes. New file creation validates non-existent paths.
- **Minimal JSON**: The JSON format includes only `file` and `changes` (with `original_lines` and `changed_lines`), reducing output token usage.
- **Relative Paths**: File paths (e.g., `src/main.py`) match `prepdir`’s output relative to the base directory (e.g., `/path/to/project`).
- **Validation Simplicity**: `applydir` validates JSON structure, syntax, and `original_lines` matching, failing if no match is found or if a new file’s path already exists.

## JSON Format
The LLM returns a JSON array of file objects, each with a relative path and a list of changes.

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
  - `file`: Relative path (e.g., `src/main.py`, `README.md`) matching `prepdir`’s output.
  - `changes`: Array of change objects.
- **Change Object**:
  - `original_lines`: For existing files, ≥10 lines (or as specified in `vibedir`’s `config.yaml`, or all lines for short files) to ensure a unique match. For new files, empty (`[]`).
  - `changed_lines`: New lines, including `original_lines` plus added lines for additions, a subset for deletions, or full content for new files.

### Example Cases
- **Modification (src/main.py)**: Replace 10 lines (e.g., a function) with a modified version (e.g., adding error handling).
- **Addition (src/main.py)**: Replace 10 lines with the same 10 lines plus new lines (e.g., a new function).
- **Deletion (src/main.py)**: Replace 10 lines with a subset, omitting deleted lines.
- **Creation (src/new_menu.py)**: Create a new file with `original_lines: []` and `changed_lines` containing the full content.
- **Addition (README.md)**: Replace 10 lines with 11 lines, adding a feature description.

### Merging Logic
- Changes within 10 lines (or as specified in `vibedir`’s `config.yaml`) of each other are merged into a single change by the LLM, combining `original_lines` and `changed_lines`.

## Workflow
1. **User Input**:
   - User provides a prompt to `vibedir` (e.g., “add a save button to the top menu”) and specifies the project directory or files.
2. **vibedir Orchestrates**:
   - Reads `config.yaml` (e.g., `context_lines: 10`).
   - Calls `prepdir` to supply full file contents with relative paths (e.g., `src/main.py`, `README.md`).
   - Crafts a prompt with user instructions, file contents, and JSON format requirements (specifying ≥10 lines in `original_lines` for existing files, empty for new files).
   - Sends the prompt to the LLM and receives the JSON array response.
   - Parses the JSON and passes it to `applydir` for validation.
3. **applydir Validates**:
   - Validates the JSON:
     - Ensure it’s an array of file objects with valid relative `file` paths and non-empty `changes` arrays.
     - For existing files (`original_lines` is non-empty):
       - Confirm `original_lines` matches the file (exact or fuzzy match via `difflib`).
       - For additions, check `changed_lines` includes `original_lines`.
     - For new files (`original_lines` empty):
       - Verify the `file` path does not yet exist in the project directory.
       - Check `changed_lines` is non-empty.
     - Return errors to `vibedir` (e.g., “Unmatched original_lines in src/main.py”, “File src/new_menu.py already exists”).
4. **vibedir Handles Errors**:
   - Displays errors to the user or sends them to the LLM for correction (e.g., “Fix unmatched lines”).
   - Optionally, iterates with the LLM to refine the response.
5. **vibedir Displays Diff**:
   - If validation succeeds, generates a diff-like view (e.g., unified diff for existing files, full `changed_lines` for new files).
   - Presents the diff to the user for approval (e.g., via CLI or UI).
6. **User Approval**:
   - User reviews the diff and approves or rejects changes.
   - Approved changes are compiled into a new JSON (a subset if some changes are rejected).
7. **applydir Applies Changes**:
   - Receives the approved JSON from `vibedir`.
   - For each file and change:
     - If `original_lines` is non-empty, match it in the file and replace with `changed_lines`.
     - If `original_lines` is empty, create the file at the `file` path with `changed_lines`.
   - Logs changes and errors (e.g., unmatched `original_lines`, file creation failures).

## Component Roles
- **prepdir**:
  - Supplies full file contents with relative paths (e.g., `src/main.py`, `README.md`) relative to the base directory (e.g., `/path/to/project`).
  - Example output format:
    ```
    File listing generated 2025-06-14 23:24:00.123456 by prepdir version 0.14.1
    Base directory is '/path/to/project'
    =-=-=-=-=-=-=-= Begin File: 'src/main.py' =-=-=-=-=-=-=-=
    print("Hello, World!")
    =-=-=-=-=-=-=-= End File: 'src/main.py' =-=-=-=-=-=-=-=
    ```
- **vibedir**:
  - Reads `config.yaml` (e.g., `context_lines: 10`) to set the minimum lines for `original_lines`.
  - Calls `prepdir` for file contents.
  - Crafts and sends the LLM prompt, receives and parses the JSON response.
  - Passes the JSON to `applydir` for validation.
  - Handles errors by displaying them to the user or querying the LLM for fixes.
  - Generates a diff view and manages user approval.
- **applydir**:
  - Validates the JSON structure, `changed_lines` syntax, and `original_lines` matching (or non-existent `file` path for new files).
  - Applies changes by replacing `original_lines` with `changed_lines` or creating new files.
  - Returns errors to `vibedir` and logs changes.

## Config.yaml for vibedir
```yaml
context_lines: 10
```
- Specifies the minimum lines for `original_lines` in existing files.
- Included in the LLM prompt.
- Adjustable (e.g., `context_lines: 15`).

## Prompt Design (Managed by vibedir)
```
You are an expert code editor. For the provided files, apply the requested changes and return a JSON array with the following structure:
[
  {
    "file": "<relative_file_path>",
    "changes": [
      {
        "original_lines": [<at least 10 lines to replace for existing files, or all lines for files shorter than 10, or empty for new files>],
        "changed_lines": [<new lines, includes original_lines plus new lines for additions, subset for deletions, or full content for new files>]
      }
    ]
  }
]
- All changes (modifications, additions, deletions, creations) will be treated as replacements (changed_lines for original_lines).
- For existing files, include at least 10 lines in original_lines (or all lines for files shorter than 10) to ensure a unique match.
- For additions, include 10 lines for context around the insertion point in original_lines, duplicate the context lines in changed_lines, and include new lines.
- For deletions, include the lines to delete in original_lines (with surrounding lines as needed to reach 10 lines) and exclude the lines to be deleted from changed_lines.
- For new files, use empty original_lines ([]) and include the full content in changed_lines.
- Merge changes within 10 lines of each other into a single change for existing files.
- Ensure changed_lines are syntactically correct for the language (e.g., Python for .py files, Markdown for .md files).
- Use relative file paths (e.g., src/main.py) matching the provided file listing.

Files:
- src/main.py:
<insert full file content from prepdir>
- README.md:
<insert full file content from prepdir>

Changes: <user-supplied prompt, e.g., "Add a save button to the top menu">
```

## Validation Rules (applydir)
- **JSON Structure**:
  - Must be an array of file objects with valid relative `file` paths and non-empty `changes` arrays.
- **Existing Files (`original_lines` non-empty)**:
  - Verify `changed_lines` has valid syntax (e.g., `pylint` for Python, `markdownlint` for Markdown).
  - Confirm `original_lines` matches the file (exact or fuzzy match via `difflib`).
  - For additions, check `changed_lines` starts with `original_lines`.
- **New Files (`original_lines` empty)**:
  - Verify the `file` path does not exist in the project directory.
  - Check `changed_lines` has valid syntax and is non-empty.
- **Error Handling**:
  - Return structured errors to `vibedir` (e.g., JSON with messages like “Unmatched original_lines in src/main.py”, “File src/new_menu.py already exists”).
  - Do not enforce minimum line counts for `original_lines`; fail only if matching fails.

## Ensuring >95% Reliability
- **Unique Matching**: The prompt specifies ≥10 lines in `original_lines` for existing files, ensuring unique matches. Fuzzy matching (e.g., `difflib`) handles minor file changes.
- **Creation Safety**: Validating non-existent `file` paths for new files prevents overwrites.
- **Validation**: `applydir` checks syntax and matching, returning errors for `vibedir` to handle.
- **User Approval**: `vibedir`’s diff view and approval process ensure only correct changes are applied.
- **Clear Prompts**: `vibedir`’s precise instructions reduce LLM errors.

## Edge Cases and Mitigations
1. **New File Creation**:
   - **Challenge**: LLM specifies an existing file path for creation.
   - **Mitigation**: `applydir` validates that the `file` path does not exist for empty `original_lines`.
2. **Large Additions**:
   - **Challenge**: Large additions (e.g., 50 lines) increase token usage.
   - **Mitigation**: Include 10 lines in `original_lines`, duplicated in `changed_lines` plus new lines. Full file input ensures context.
3. **File Changes**:
   - **Challenge**: Edits shift content in existing files.
   - **Mitigation**: Fuzzy matching of `original_lines`. `applydir` returns mismatches to `vibedir`.
4. **Short Files**:
   - **Challenge**: File has <10 lines.
   - **Mitigation**: Use all lines in `original_lines`.
5. **LLM Errors**:
   - **Challenge**: Incorrect `original_lines`, invalid syntax, or existing path for new files.
   - **Mitigation**: `applydir` validates syntax, matching, and file existence. `vibedir` handles errors via user or LLM.

## Next Steps
- **Error Format**: Define `applydir`’s structured error format (e.g., JSON with file, change index, and message).
- **Diff Design**: Plan `vibedir`’s diff view (e.g., unified diff, showing new files) and approval process (e.g., CLI prompts).
- **Test Cases**: Create samples with existing file edits (e.g., `src/main.py`, `README.md`), new file creation (e.g., `src/new_menu.py`), and user prompts (e.g., “add a save button”).
- **Prompt Testing**: Test the prompt with LLMs to ensure consistent output with relative paths, ≥10-line `original_lines`, and empty `original_lines` for new files.
- **Config Enhancements**: Consider additional `config.yaml` settings (e.g., LLM model, diff format).