# applydir - NOT READY FOR USE but "coming soon"!

## Overview
`applydir` is a Python tool that automates the application of LLM-generated code changes to a codebase. It processes changes specified in a JSON format, using a unified "replace" approach to handle modifications, additions, deletions, and new file creation. Designed to work with `prepdir` (supplies full file contents) and `vibedir` (orchestrates prompts, LLM communication, and Git integration), `applydir` validates and applies changes while ensuring consistency with relative file paths and robust error handling.

## Features
- **Unified Replace Approach**: All changes are treated as replacements:
  - Existing files: Replace `original_lines` (typically ≥10 lines, per `vibedir`’s `config.yaml`) with `changed_lines`.
  - New files: Create files with empty `original_lines` (`[]`) and full content in `changed_lines`.
- **Reliability (>95%)**: Uses ≥10 lines for unique matching in existing files, fuzzy matching (e.g., `difflib`) for robustness, and validates non-existent paths for new files.
- **Minimal JSON Format**: Simple structure with `file` and `changes` (`original_lines`, `changed_lines`) to reduce LLM output tokens.
- **Relative Paths**: Matches `prepdir`’s output (e.g., `src/main.py`) relative to the project base directory.
- **Validation**: Checks JSON structure and line matching.
- **Modular Design**: Separates JSON parsing, change validation, line matching, and file operations for clarity and testability.

## JSON Format
Changes are provided in a JSON array of file objects:

```json
[
  {
    "file": "<relative_file_path>",
    "changes": [
      {
        "original_lines": [<≥10 lines for existing files, or all lines if <10, or empty for new files>],
        "changed_lines": [<new lines for replacements or full content for new files>]
      }
    ]
  }
]
```

### Example Cases
- **Modification**: Replace 10 lines in `src/main.py` with a modified version (e.g., add error handling).
- **Addition**: Replace 10 lines in `src/main.py` with 10 lines plus new lines (e.g., new function).
- **Deletion**: Replace 10 lines in `src/main.py` with a subset, omitting deleted lines.
- **Creation**: Create `src/new_menu.py` with `original_lines: []` and full content in `changed_lines`.
- **Addition in Markdown**: Add a feature description to `README.md`.

## Class Structure
`applydir` uses four classes, adhering to Python best practices (PEP 8, PEP 20):

1. **ApplyDirChanges (Pydantic)**:
   - Parses and validates JSON, creating `ApplyDirFileChange` objects with `file` injected.
   - Validates JSON structure and file paths.
   - Attributes: `files: List[Dict[str, Union[str, List[ApplyDirFileChange]]]]`.

2. **ApplyDirFileChange (Pydantic)**:
   - Represents and validates a single change, including the file path.
   - Validates syntax and additions (e.g., `changed_lines` starts with `original_lines`).
   - Attributes: `file: str`, `original_lines: List[str]`, `changed_lines: List[str]`.

3. **ApplyDirMatcher**:
   - Matches `original_lines` in existing files using fuzzy matching (e.g., `difflib`).
   - Attributes: `similarity_threshold: float`, `max_search_lines: Optional[int]`.
   - Methods: `match(file_content: List[str], change: ApplyDirFileChange) -> Dict`.

4. **ApplyDirApplicator**:
   - Applies changes using `ApplyDirFileChange` and `ApplyDirMatcher`.
   - Handles file operations (replace or create).
   - Attributes: `base_dir: str`, `changes: ApplyDirChanges`, `matcher: ApplyDirMatcher`, `logger`.
   - Methods: `apply_changes()`, `apply_single_change(change: ApplyDirFileChange)`.

## Workflow
1. **User Input**: User provides a prompt (e.g., “add a save button”) and project directory to `vibedir`.
2. **vibedir**:
   - Calls `prepdir` for file contents (e.g., `src/main.py`).
   - Sends prompt to LLM, receives JSON.
   - Commits or backs up state (Git or files).
   - Passes JSON to `ApplyDirChanges`.
3. **ApplyDirChanges**: Parses JSON, creates and validates `ApplyDirFileChange` objects.
4. **ApplyDirFileChange**: Validates syntax and additions for each change.
5. **ApplyDirApplicator**: Iterates over changes, uses `ApplyDirMatcher` for existing files, applies replacements or creates new files.
6. **ApplyDirMatcher**: Matches `original_lines` in existing files.
7. **vibedir**:
   - Handles errors (displays or queries LLM).
   - Generates diff, seeks user approval.
   - Commits changes or reverts on errors/rejection.

## Validation
- **ApplyDirChanges**: Validates JSON structure and file paths.
- **ApplyDirFileChange**: Checks syntax, additions for existing files, non-empty `changed_lines` for new files.
- **ApplyDirApplicator**: Verifies path non-existence for new files, relies on `ApplyDirMatcher` for existing files.
- **ApplyDirMatcher**: Ensures `original_lines` matches file content.

## Python Best Practices
- **PEP 8**: Clear, descriptive names (e.g., `ApplyDirFileChange`).
- **PEP 20**: Explicit `file` in `ApplyDirFileChange`, simple class roles.
- **Type Safety**: Designed for type hints (e.g., `List[str]`).
- **Testability**: Small, focused classes.
- **Documentation**: Planned docstrings for all methods.

## Edge Cases
- **New File Creation**: Validate non-existent paths.
- **Unmatched Lines**: Fuzzy matching with error reporting.
- **Invalid Syntax**: Detected by `ApplyDirFileChange`.
- **Short Files**: Handled by `vibedir`’s prompt.
- **File System Issues**: Caught by `ApplyDirApplicator`.

## Dependencies
- **Pydantic**: For JSON parsing and validation.
- **difflib**: For fuzzy matching.
- **Syntax Checkers**: `pylint` (Python), `markdownlint` (Markdown).

## Next Steps
- Define structured error format (e.g., JSON with `file`, `change_index`, `error`).
- Specify `ApplyDirMatcher` settings (e.g., `difflib` threshold).
- Plan logging for `ApplyDirApplicator`.
- Detail `vibedir`’s Git/backup strategy.
- Develop test cases for all scenarios.