# applydir Class Design Document

## Overview
The `applydir` project automates code changes by applying LLM-generated modifications, achieving >95% reliability. It works with `prepdir` (supplies full file contents) and `vibedir` (crafts prompts, communicates with the LLM, manages Git integration). Changes are specified in a JSON array of file objects, using a unified "replace" approach where `original_lines` are replaced with `changed_lines`. The design supports modifications, additions, deletions, and new file creation, with relative paths matching `prepdir`’s output.

## Core Design Principles
- **Unified Replace Approach**: All changes (modifications, additions, deletions, creations) are replacements:
  - Existing files: Replace `original_lines` (typically ≥10 lines, per `vibedir`) with `changed_lines`.
  - New files: `original_lines` is empty (`[]`), `changed_lines` contains the full content.
- **Reliability (>95%)**: ≥10 lines in `original_lines` ensure unique matching for existing files; fuzzy matching handles minor changes. New file creation validates non-existent paths.
- **Minimal JSON**: Only `file` and `changes` (`original_lines`, `changed_lines`), reducing token usage.
- **Relative Paths**: Match `prepdir`’s output (e.g., `src/main.py`).
- **Validation Simplicity**: Validate JSON structure, syntax, and `original_lines` matching; fail if no match or new file path exists.
- **Git in vibedir**: `vibedir` handles Git integration and rollbacks, keeping `applydir` focused on validation and application.

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
1. **ApplyDirChanges (Pydantic)**:
   - Parse and validate JSON, create `ApplyDirFileChange` objects with `file` injected.
   - Attributes: `files: List[Dict[str, Union[str, List[ApplyDirFileChange]]]` (file path, changes).
   - Validate: JSON structure, `file` paths, delegate content validation to `ApplyDirFileChange`.

2. **ApplyDirFileChange (Pydantic)**:
   - Represent and validate a single change, including the file path.
   - Attributes: `file: str`, `original_lines: List[str]`, `changed_lines: List[str]`.
   - Validate: Syntax, additions (if `original_lines` non-empty); non-empty `changed_lines` (if `original_lines` empty).

3. **ApplyDirMatcher**:
   - Match `original_lines` in existing files using fuzzy matching (e.g., `difflib`).
   - Attributes: `similarity_threshold: float`, `max_search_lines: Optional[int]`.
   - Methods: `match(file_content: List[str], change: ApplyDirFileChange) -> Dict`.

4. **ApplyDirApplicator**:
   - Apply changes using `ApplyDirFileChange` and `ApplyDirMatcher`.
   - Attributes: `base_dir: str`, `changes: ApplyDirChanges`, `matcher: ApplyDirMatcher`, `logger`.
   - Methods: `apply_changes()`, `apply_single_change(change: ApplyDirFileChange)`, `write_changes()`.

## Workflow
1. **User Input**:
   - User provides prompt (e.g., “add a save button”) and project directory to `vibedir`.
2. **vibedir Orchestrates**:
   - Reads `config.yaml` (e.g., `context_lines: 10`).
   - Calls `prepdir` for file contents (e.g., `src/main.py`).
   - Sends prompt to LLM, receives JSON.
   - Commits or backs up current state (Git or files).
   - Passes JSON to `ApplyDirChanges`.
3. **ApplyDirChanges**:
   - Parse JSON, create `ApplyDirFileChange` objects with `file`.
   - Validate structure, delegate to `ApplyDirFileChange`.
4. **ApplyDirFileChange**:
   - Validate `original_lines`, `changed_lines` (syntax, additions).
   - Return errors (e.g., `{"file": "src/main.py", "change_index": 0, "error": "Invalid syntax"}`).
5. **ApplyDirApplicator**:
   - Iterate over `ApplyDirChanges.files` and `changes`.
   - For each `ApplyDirFileChange`:
     - Resolve path using `change.file`.
     - If `original_lines` non-empty:
       - Read file, call `ApplyDirMatcher.match(change)`.
       - Replace with `changed_lines`.
     - If `original_lines` empty:
       - Check path non-existence.
       - Create file.
6. **ApplyDirMatcher**:
   - Match `change.original_lines` in file content.
   - Return range or error using `change.file`.
7. **vibedir**:
   - On errors: Display to user or query LLM.
   - On success: Generate diff, seek approval.
   - Post-approval: Apply changes, commit (e.g., `git commit -m "Applied changes"`).
   - On rejection/errors: Revert (e.g., `git reset --hard`) or restore backups.

## Git Integration (vibedir)
- **Before Validation**: Commit (e.g., `git commit -m "Pre-applydir changes"`) or backup files.
- **After Validation**: Generate diff, seek approval.
- **After Application**: Commit changes or revert on errors/rejection.
- **Non-Git Projects**: Use file backups.

## Validation Rules
- **ApplyDirChanges**:
  - JSON is an array, `file` paths valid, `changes` non-empty.
- **ApplyDirFileChange**:
  - Existing files: `changed_lines` valid syntax, additions start with `original_lines`.
  - New files: `changed_lines` non-empty, valid syntax.
- **ApplyDirApplicator**:
  - Existing files: `original_lines` matches file.
  - New files: `file` path does not exist.
- **ApplyDirMatcher**:
  - Match `original_lines` with fuzzy matching.

## Python Best Practices
- **PEP 8**: Clear names (e.g., `ApplyDirFileChange`), consistent structure.
- **PEP 20**: Explicit `file` in `ApplyDirFileChange`, simple class roles.
- **Type Safety**: Design for type hints (e.g., `List[str]`).
- **Testability**: Small classes for unit testing.
- **Documentation**: Plan docstrings.

## Edge Cases and Mitigations
1. **New File Creation**: Validate non-existent path in `ApplyDirApplicator`.
2. **Unmatched original_lines**: `ApplyDirMatcher` uses fuzzy matching, returns errors.
3. **Invalid Syntax**: `ApplyDirFileChange` validates syntax.
4. **Short Files**: `vibedir`’s prompt allows all lines.
5. **File System Issues**: `ApplyDirApplicator` catches errors.
6. **Rollback**: `vibedir` reverts via Git or backups.

## Next Steps
- Define error format for all classes.
- Specify `ApplyDirMatcher` settings (e.g., `difflib` threshold).
- Plan logging format for `ApplyDirApplicator`.
- Detail `vibedir`’s Git/backup strategy.
- Design test cases for all scenarios.