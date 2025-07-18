# applydir

## Overview
`applydir` is a Python tool that automates the application of LLM-generated code changes to a codebase, achieving >95% reliability. It processes changes specified in a JSON format, using a unified "replace" approach to handle modifications, additions, deletions, and new file creation. Designed to work with `prepdir` (supplies full file contents) and `vibedir` (orchestrates prompts, LLM communication, Git integration, and linting), `applydir` validates and applies changes while ensuring consistency with relative file paths and robust error handling.

## Features
- **Unified Replace Approach**: All changes are treated as replacements:
  - Existing files: Replace `original_lines` (typically ≥10 lines, per `vibedir`’s `config.yaml`) with `changed_lines`.
  - New files: Create files with empty `original_lines` (`[]`) and full content in `changed_lines`.
- **Reliability (>95%)**: Uses ≥10 lines for unique matching in existing files, fuzzy matching (e.g., `difflib`) for robustness, and validates non-existent paths for new files.
- **Minimal JSON Format**: Simple structure with `file` and `changes` (`original_lines`, `changed_lines`) to reduce LLM output tokens.
- **Relative Paths**: Matches `prepdir`’s output (e.g., `src/main.py`) relative to the project base directory.
- **Validation**: Checks JSON structure, syntax, and line matching.
- **Modular Design**: Separates JSON parsing, change validation, line matching, and file operations for clarity and testability.
- **Git and Linting in vibedir**: `vibedir` handles Git commits, rollbacks, and linting of temporary files.

## JSON Format
The LLM provides changes in a JSON array of file objects:

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
`applydir` uses five classes, adhering to Python best practices (PEP 8, PEP 20):

1. **ApplyDirError (Pydantic)**:
   - Represents a single error, JSON-serializable.
   - Attributes: `change: Optional[ApplyDirFileChange]`, `error_type: str`, `message: str`, `details: Optional[Dict]`.
   - Validates `error_type` (e.g., `json_structure`, `syntax`) and `message`.

2. **ApplyDirChanges (Pydantic)**:
   - Parses and validates JSON, creating `ApplyDirFileChange` objects with `file` injected.
   - Validates JSON structure and file paths.
   - Attributes: `files: List[Dict[str, Union[str, List[ApplyDirFileChange]]]]`.

3. **ApplyDirFileChange (Pydantic)**:
   - Represents and validates a single change, including the file path.
   - Validates syntax and additions (e.g., `changed_lines` starts with `original_lines`).
   - Attributes: `file: str`, `original_lines: List[str]`, `changed_lines: List[str]`.

4. **ApplyDirMatcher**:
   - Matches `original_lines` in existing files using fuzzy matching (e.g., `difflib`).
   - Attributes: `similarity_threshold: float`, `max_search_lines: Optional[int]`.
   - Methods: `match(file_content: List[str], change: ApplyDirFileChange) -> Union[Dict, List[ApplyDirError]]`.

5. **ApplyDirApplicator**:
   - Applies changes using `ApplyDirFileChange` and `ApplyDirMatcher`.
   - Handles file operations (replace or create) in temporary files.
   - Attributes: `base_dir: str`, `changes: ApplyDirChanges`, `matcher: ApplyDirMatcher`, `logger`.
   - Methods: `apply_changes()`, `apply_single_change(change: ApplyDirFileChange)`.

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
- `json_structure`: Invalid JSON.
- `file_path`: Invalid `file` path.
- `changes_empty`: Empty `changes` array.
- `syntax`: Invalid `changed_lines` syntax.
- `addition_mismatch`: `changed_lines` doesn’t start with `original_lines`.
- `empty_changed_lines`: `changed_lines` empty for new files.
- `matching`: No match for `original_lines`.
- `file_system`: File exists, permissions, disk errors.
- `linting`: Linting failures in `vibedir`.

## Workflow
1. **User Input**: User provides a prompt (e.g., “add a save button”) and project directory to `vibedir`.
2. **vibedir**:
   - Calls `prepdir` for file contents (e.g., `src/main.py`).
   - Sends prompt to LLM, receives JSON.
   - Commits or backs up state (Git or files).
   - Passes JSON to `ApplyDirChanges`.
3. **ApplyDirChanges**: Parses JSON, creates and validates `ApplyDirFileChange` objects, returns `List[ApplyDirError]`.
4. **ApplyDirFileChange**: Validates syntax and additions, returns `List[ApplyDirError]`.
5. **ApplyDirApplicator**: Iterates over changes, uses `ApplyDirMatcher`, writes to temporary files, returns `List[ApplyDirError]`.
6. **ApplyDirMatcher**: Matches `original_lines`, returns range or `List[ApplyDirError]`.
7. **vibedir**:
   - Runs linters (e.g., `pylint`, `markdownlint`) on temporary files, returns `List[ApplyDirError]`.
   - On success: Moves files to codebase, commits.
   - On errors: Displays errors or queries LLM, discards temporary files.
   - On rejection: Reverts via Git or backups.

## Git and Linting
- **Git Integration (vibedir)**:
  - Before validation: Commit (e.g., `git commit -m "Pre-applydir changes"`) or backup files.
  - After application: Commit changes or revert on errors/rejection.
  - Non-Git projects: Use file backups.
- **Linting (vibedir)**:
  - Runs linters on temporary files (e.g., `.applydir_temp`).
  - Returns `List[ApplyDirError]` with `error_type: "linting"`.

## Validation
- **ApplyDirChanges**: Validates JSON structure and file paths.
- **ApplyDirFileChange**: Checks syntax, additions, non-empty `changed_lines` for new files.
- **ApplyDirApplicator**: Verifies path non-existence, relies on `ApplyDirMatcher`.
- **ApplyDirMatcher**: Ensures `original_lines` matches file content.

## Python Best Practices
- **PEP 8**: Clear, descriptive names (e.g., `ApplyDirError`).
- **PEP 20**: Explicit `change` in `ApplyDirError`, simple class roles.
- **Type Safety**: Pydantic for type-safe errors and changes.
- **Testability**: Small classes and structured errors.
- **Documentation**: Planned docstrings for all methods.

## Edge Cases
- **New File Creation**: Validate non-existent paths.
- **Unmatched Lines**: Fuzzy matching with `ApplyDirError`.
- **Invalid Syntax**: Detected by `ApplyDirFileChange`.
- **Short Files**: Handled by `vibedir`’s prompt.
- **File System Issues**: Caught by `ApplyDirApplicator`.
- **Linting Failures**: Caught by `vibedir`.

## Dependencies
- **Pydantic**: For JSON parsing, validation, and error handling.
- **difflib**: For fuzzy matching.
- **Syntax Checkers**: `pylint` (Python), `markdownlint` (Markdown).

## Next Steps
- Finalize `ApplyDirError`:
  - Define `error_type` enum.
  - Specify truncation for large `original_lines`/`changed_lines`.
- Specify `ApplyDirMatcher` settings (e.g., `difflib` threshold).
- Plan logging for `ApplyDirApplicator`.
- Detail `vibedir`’s Git/backup and linting strategy.
- Develop test cases for all scenarios.