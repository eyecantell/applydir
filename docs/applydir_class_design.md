# applydir Class Design Document (October 2, 2025)

## Overview
The `applydir` project automates applying LLM-generated code changes to a codebase with high reliability. It processes JSON-specified changes, supporting `replace_lines` (line-level modifications), `create_file` (new files), and `delete_file` (file deletions). Changes are applied directly to the codebase, with tracking/reversion handled by Git or other tools (planned via `vibedir`). It integrates with `prepdir` for logging and configuration. File paths are resolved relative to a base directory, matching `prepdir`’s output.

## Core Design Principles
- **Supported Actions**: `replace_lines` for line replacements, `create_file` for new files, `delete_file` for deletions (controlled by `allow_file_deletion`).
- **Direct Application**: Changes are applied directly to files for simplicity; Git (via planned `vibedir`) handles tracking/reversion.
- **Reliability**: Hybrid matching (exact first, optional fuzzy fallback with Levenshtein or sequence matcher) ensures accurate line replacements.
- **JSON Input**: Minimal structure with `file_entries` containing `file`, `action`, and `changes`.
- **Resolvable Paths**: Relative or absolute paths resolved within `--base-dir`.
- **Validation**: Checks JSON structure, actions, file paths, and non-ASCII characters.
- **Configuration**: Uses `prepdir`’s `load_config` for `config.yaml`, with CLI or programmatic overrides.
- **Modularity**: Separates parsing (`ApplydirChanges`), validation (`ApplydirFileChange`), matching (`ApplydirMatcher`), and application (`ApplydirApplicator`).

## JSON Format
```json
{
  "message": "Optional Git commit message (may include \n for multi-line)",
  "file_entries": [
    {
      "file": "<relative_or_absolute_file_path>",
      "action": "<replace_lines|create_file|delete_file>",
      "changes": [
        {
          "original_lines": ["<lines to match in existing file (empty for create_file)>"],
          "changed_lines": ["<new lines or full content for create_file>"]
        }
      ]
    }
  ]
}
```

### Fields
- **File Entry**:
  - `file`: Path (e.g., `src/main.py`).
  - `action`: Required; one of `replace_lines`, `create_file`, `delete_file`.
  - `changes`: Required for `replace_lines` and `create_file`, optional for `delete_file`.
- **Change Object** (within `changes`):
  - `original_lines`: Non-empty for `replace_lines`, empty for `create_file`, ignored for `delete_file`.
  - `changed_lines`: Non-empty for `replace_lines` or `create_file`, ignored for `delete_file`.

### Example Cases
- **Replace Lines**:
  ```json
  {
    "file_entries": [
      {
        "file": "src/main.py",
        "action": "replace_lines",
        "changes": [
          {"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}
        ]
      }
    ]
  }
  ```
- **Create File**:
  ```json
  {
    "file_entries": [
      {
        "file": "src/new.py",
        "action": "create_file",
        "changes": [
          {"original_lines": [], "changed_lines": ["def new_func():", "    pass"]}
        ]
      }
    ]
  }
  ```
- **Delete File**:
  ```json
  {
    "file_entries": [
      {
        "file": "src/old.py",
        "action": "delete_file",
        "changes": []
      }
    ]
  }
  ```

## Configuration
Uses `.applydir/config.yaml` or bundled `src/applydir/config.yaml`, loaded via `prepdir`’s `load_config`. CLI options (`--no-allow-file-deletion`, `--non-ascii-action`) or programmatic `config_override` override settings.

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
  similarity:
    default: 0.95
  similarity_metric:
    default: levenshtein
  use_fuzzy:
    default: true
```

- `validation.non_ascii`: Controls non-ASCII handling (default and per-extension rules).
- `allow_file_deletion`: Enables/disables file deletions.
- `matching`: Configures `ApplydirMatcher` (whitespace handling, similarity threshold/metric, fuzzy matching).

## Class Structure
1. **ApplydirError (Pydantic)**:
   - **Purpose**: JSON-serializable error, warning, or success confirmation.
   - **Attributes**:
     - `change: Optional[Any]`: Associated change, if applicable (null for structural errors).
     - `error_type: ErrorType`: Enum (`json_structure`, `invalid_change`, `file_not_found`, `file_already_exists`, `no_match`, `multiple_matches`, `file_system`, `file_changes_successful`, `non_ascii_chars`).
     - `severity: ErrorSeverity`: Enum (`error`, `warning`, `info`).
     - `message: str`: Descriptive message.
     - `details: Dict`: Context (e.g., `file`, `match_count`, `actions`, `change_count`).
   - **Validation**: Ensures valid enums, non-empty `message`, `details` defaults to `{}`.
   - **Usage**: Errors (`error`, `warning`) for validation/application failures, `info` for successful file changes.

2. **ApplydirChanges (Pydantic)**:
   - **Purpose**: Parses and validates JSON `file_entries`, creates `ApplydirFileChange` objects.
   - **Attributes**:
     - `file_entries: List[Dict]`: Each with `file: str`, `action: str`, `changes: Optional[List[Dict]]`.
   - **Validation**:
     - Non-empty `file_entries` array.
     - Valid `file` paths (resolvable within `base_dir`).
     - Valid `action` (`replace_lines`, `create_file`, `delete_file`).
     - Creates `ApplydirFileChange` objects via `from_file_entry`.
   - **Methods**:
     - `validate_changes(base_dir: str, config: Dict) -> List[ApplydirError]`: Validates paths and non-ASCII characters.
   - **Error Handling**: Returns `List[ApplydirError]` for structural issues (e.g., missing `file_entries`).

3. **ApplydirFileChange (Pydantic)**:
   - **Purpose**: Represents a single change, validates action-specific rules.
   - **Attributes**:
     - `file_path: Path`: Resolved path.
     - `action: ActionType`: Enum (`replace_lines`, `create_file`, `delete_file`).
     - `original_lines: List[str]`: Lines to match (empty for `create_file`).
     - `changed_lines: List[str]`: New content (empty for `delete_file`).
   - **Methods**:
     - `from_file_entry(file_path: Path, action: str, change_dict: Optional[Dict]) -> ApplydirFileChange`: Creates instance from JSON.
     - `validate_change(config: Dict) -> List[ApplydirError]`: Validates paths, non-ASCII, and action rules.
   - **Validation**:
     - Non-empty `file_path`.
     - Non-ASCII per `config.validation.non_ascii`.
     - `replace_lines`: Non-empty `original_lines` and `changed_lines`.
     - `create_file`: Empty `original_lines`, non-empty `changed_lines`.
     - `delete_file`: Empty `original_lines` and `changed_lines`.
   - **Error Handling**: Returns `List[ApplydirError]` (e.g., `invalid_change`, `non_ascii_chars`).

4. **ApplydirMatcher**:
   - **Purpose**: Matches `original_lines` using exact or fuzzy matching (Levenshtein or sequence matcher).
   - **Attributes**:
     - `similarity_threshold: float`: Default 0.95 (from config).
     - `max_search_lines: Optional[int]`: Limits search scope.
     - `case_sensitive: bool`: From config or default.
     - `config: Dynaconf`: For `whitespace`, `similarity_metric`, `use_fuzzy`.
   - **Methods**:
     - `match(file_content: List[str], change: ApplydirFileChange) -> Tuple[Optional[Dict], List[ApplydirError]]`: Returns match range or errors (`no_match`, `multiple_matches`).
     - `normalize_line(line: str, whitespace_handling: str, case_sensitive: bool) -> str`: Normalizes lines for matching.
   - **Error Handling**: Returns `ApplydirError` for `no_match` or `multiple_matches` with `match_count` in `details`.

5. **ApplydirApplicator**:
   - **Purpose**: Applies changes using `ApplydirFileChange` and `ApplydirMatcher`, performs file system operations.
   - **Attributes**:
     - `base_dir: str`: Root directory for paths.
     - `changes: ApplydirChanges`: Parsed changes.
     - `matcher: ApplydirMatcher`: For line matching.
     - `logger: logging.Logger`: For logging.
     - `config: Dynaconf`: Merged configuration.
   - **Methods**:
     - `apply_changes() -> List[ApplydirError]`: Iterates over `file_entries`, applies changes.
     - `create_file(file_path: Path, change: ApplydirFileChange) -> List[ApplydirError]`: Creates new files.
     - `replace_lines(file_path: Path, change: ApplydirFileChange) -> List[ApplydirError]`: Replaces lines using matcher.
     - `delete_file(file_path: Path, change: ApplydirFileChange) -> List[ApplydirError]`: Deletes files if allowed.
     - `write_changes(file_path: Path, changed_lines: List[str], range: Optional[Dict])`: Writes file content.
   - **Validation**: Checks file existence (`file_not_found`, `file_already_exists`), permissions via `allow_file_deletion`.
   - **Error Handling**: Returns `List[ApplydirError]` for failures, `file_changes_successful` for successes.

## CLI Utility
```bash
applydir changes.json [--base-dir <path>] [--no-allow-file-deletion] [--non-ascii-action {error,warning,ignore}] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
```
- `changes.json`: JSON file with changes.
- `--base-dir`: Base directory (default: `.`).
- `--no-allow-file-deletion`: Disables deletions.
- `--non-ascii-action`: Non-ASCII handling (`error`, `warning`, `ignore`).
- `--log-level`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).

## Error Types
- `json_structure`: Invalid JSON (e.g., missing `file_entries`).
- `invalid_change`: Invalid change format or validation failure.
- `file_not_found`: File missing for `replace_lines` or `delete_file`.
- `file_already_exists`: File exists for `create_file`.
- `no_match`: No matching lines for `replace_lines`.
- `multiple_matches`: Multiple matches for `original_lines`.
- `file_system`: File operation failure (e.g., write error).
- `file_changes_successful`: Successful file changes (info severity).
- `non_ascii_chars`: Non-ASCII characters detected (severity per config).

## Error Format
```json
[
  {
    "change": {
      "file_path": "src/main.py",
      "action": "replace_lines",
      "original_lines": ["print('Hello')"],
      "changed_lines": ["print('Hello World')"]
    },
    "error_type": "no_match",
    "severity": "error",
    "message": "No matching lines found",
    "details": {"file": "src/main.py"}
  },
  {
    "change": null,
    "error_type": "file_changes_successful",
    "severity": "info",
    "message": "All changes to file applied successfully",
    "details": {"file": "src/main.py", "actions": ["replace_lines"], "change_count": 1}
  }
]
```

## Workflow
1. **Input**: Run `applydir changes.json` with JSON file.
2. **Parsing**: `ApplydirChanges` parses `file_entries`, validates structure.
3. **Validation**: `ApplydirChanges.validate_changes` checks paths and non-ASCII, creating `ApplydirFileChange` objects.
4. **Application**: `ApplydirApplicator.apply_changes` iterates over changes, uses `ApplydirMatcher` to locate lines, and applies `create_file`, `replace_lines`, or `delete_file`.
5. **Output**: Logs errors/successes via `prepdir`’s `configure_logging`, returns exit code (0 for success, 1 for errors).

## Dependencies
- **prepdir**: Provides `load_config` for configuration and `configure_logging` for logging.
- **Pydantic**: JSON parsing and validation for `ApplydirError`, `ApplydirChanges`, `ApplydirFileChange`.
- **dynaconf**: Configuration merging in `ApplydirApplicator`.
- **difflib**: Fuzzy matching in `ApplydirMatcher` (via `sequence_matcher_similarity`).

## Next Steps
- Integrate with `vibedir` for LLM prompting, Git integration, and linting.
- Expand test coverage for `ApplydirFileChange`, `ApplydirMatcher`, and edge cases.
- Add support for additional error types if needed.
- Refine matching configuration (e.g., per-extension rules).