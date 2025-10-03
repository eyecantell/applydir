# applydir

## Overview
`applydir` is a Python command-line tool that automates the application of LLM-generated code changes to a codebase. It processes changes specified in a JSON format, supporting actions like line replacements, file creation, and deletion. Changes are applied directly to the codebase—use Git or other version control tools (e.g., via planned `vibedir` integration) for tracking and reverting. Designed to integrate with `prepdir` (for logging and configuration) and eventually `vibedir` (for LLM communication, Git integration, and linting), `applydir` validates and applies changes with robust error handling, fuzzy matching for reliability, and resolvable file paths.

## Features
- **Supported Actions**: 
  - `replace_lines`: Replace blocks of lines in existing files (unified approach for modifications, additions, deletions).
  - `create_file`: Create new files with specified content.
  - `delete_file`: Delete files (configurable via `--no-allow-file-deletion`).
- **Reliability**: Uses fuzzy matching (Levenshtein or sequence matcher, configurable) to locate lines in existing files, with options for whitespace handling and case sensitivity.
- **JSON Input**: Processes a simple JSON structure with `file_entries`, each containing `file`, `action`, and `changes` (with `original_lines` and `changed_lines` for replacements).
- **Resolvable Paths**: Accepts relative or absolute file paths, resolved relative to `--base-dir` (default: current directory).
- **Validation**: Validates JSON structure, file paths, and non-ASCII characters (configurable via `config.yaml` or `--non-ascii-action`).
- **Configuration**: Loads defaults from `.applydir/config.yaml` or bundled `src/applydir/config.yaml` using `prepdir`'s `load_config`. Overrides via CLI or programmatic `config_override`.
- **Error Handling**: Returns structured `ApplydirError` objects with type, severity, message, and details; logged via `prepdir`'s logging system.
- **CLI Utility**: Run `applydir <input_file>` with options to customize behavior.
- **Direct Application**: Changes are applied directly to files for simplicity; track/revert via Git in workflows like `vibedir`.
- **Modular Design**: Separates JSON parsing (`ApplydirChanges`), change validation (`ApplydirFileChange`), matching (`ApplydirMatcher`), and application (`ApplydirApplicator`).

## JSON Format
Changes are provided in a JSON object with a `file_entries` array:

```json
{
  "file_entries": [
    {
      "file": "<relative_or_absolute_file_path>",
      "action": "<replace_lines|create_file|delete_file>",
      "changes": [
        {
          "original_lines": ["<lines to match in existing file (empty for create_file)>"],
          "changed_lines": ["<new lines to insert (full content for create_file)>"]
        }
      ]
    }
  ]
}
```

### Example Cases
- **Modification (replace_lines)**: Replace a block in `src/main.py`:
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
- **Addition**: Match a block and replace with additional lines.
- **Deletion**: Match a block and replace with fewer lines, or use `delete_file` for entire files.
- **Creation (create_file)**: Create `src/new.py` with content:
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
- **Deletion (delete_file)**: Delete `src/old.py`:
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

## Installation
```bash
pip install applydir
```

## Usage
### CLI
Run the `applydir` utility to apply changes from a JSON file:
```bash
applydir changes.json [--base-dir <path>] [--no-allow-file-deletion] [--non-ascii-action {error,warning,ignore}] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
```
- `changes.json`: Path to the JSON file containing changes.
- `--base-dir`: Base directory for file paths (default: `.`).
- `--no-allow-file-deletion`: Disable file deletions (overrides config).
- `--non-ascii-action`: Handle non-ASCII characters (`error`, `warning`, or `ignore`; overrides config).
- `--log-level`: Set logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).

### Example
```bash
applydir changes.json --base-dir /path/to/project --no-allow-file-deletion --non-ascii-action=error --log-level=DEBUG
```

### Programmatic
```python
from applydir import ApplydirApplicator, ApplydirChanges, ApplydirMatcher
from applydir.applydir_error import ApplydirError, ErrorSeverity
import logging
from prepdir import configure_logging

logger = logging.getLogger("applydir")
configure_logging(logger, level="INFO")

changes_json = {
    "file_entries": [
        {
            "file": "src/main.py",
            "action": "replace_lines",
            "changes": [{"original_lines": ["print('Hello')"], "changed_lines": ["print('Hello World')"]}]
        }
    ]
}
changes = ApplydirChanges(file_entries=changes_json["file_entries"])
matcher = ApplydirMatcher(similarity_threshold=0.95)
applicator = ApplydirApplicator(
    base_dir="/path/to/project",
    changes=changes,
    matcher=matcher,
    logger=logger,
    config_override={"allow_file_deletion": False, "validation": {"non_ascii": {"default": "error"}}}
)
errors = applicator.apply_changes()
has_errors = False
for error in errors:
    log_level = (
        logging.INFO if error.severity == ErrorSeverity.INFO
        else logging.WARNING if error.severity == ErrorSeverity.WARNING
        else logging.ERROR
    )
    logger.log(log_level, f"{error.message}: {error.details}")
    if error.severity in [ErrorSeverity.ERROR, ErrorSeverity.WARNING]:
        has_errors = True
if not has_errors:
    logger.info("Changes applied successfully")
```

## Configuration
`applydir` loads defaults from `.applydir/config.yaml` or bundled `src/applydir/config.yaml` using `prepdir`'s `load_config`. CLI options or programmatic `config_override` can override settings.

Example `config.yaml`:
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

- `validation.non_ascii`: Controls non-ASCII handling (default, rules by extension).
- `allow_file_deletion`: Enables/disables deletions (default: true).
- `matching`: Settings for `ApplydirMatcher` (whitespace, similarity threshold/metric, fuzzy matching).

Logging level is set via CLI `--log-level` or programmatically.

## Error Format
Errors and warnings are returned as a list of `ApplydirError` objects and logged:

```json
[
  {
    "change": null,
    "error_type": "json_structure",
    "severity": "error",
    "message": "Invalid JSON structure",
    "details": {}
  },
  {
    "change": null,
    "error_type": "file_not_found",
    "severity": "error",
    "message": "File does not exist for deletion",
    "details": {"file": "/path/to/missing.py"}
  },
  {
    "change": null,
    "error_type": "file_changes_successful",
    "severity": "info",
    "message": "All changes to file applied successfully",
    "details": {"file": "/path/to/main.py", "actions": ["replace_lines"], "change_count": 1}
  }
]
```

## Error Types
- `json_structure`: Invalid JSON (e.g., missing `file_entries`).
- `invalid_change`: Invalid change format or validation failure.
- `file_not_found`: File missing for modification/deletion.
- `file_already_exists`: File exists for creation.
- `no_match`: No matching lines found.
- `multiple_matches`: Multiple matches for lines.
- `permission_denied`: Deletion disabled.
- `file_system`: File operation failure.
- `file_changes_successful`: Successful application (info level).

## Class Structure
1. **ApplydirError**:
   - Represents errors/warnings.
   - Attributes: `change: Optional[Any]`, `error_type: ErrorType`, `severity: ErrorSeverity`, `message: str`, `details: Dict`.

2. **ApplydirChanges**:
   - Parses/validates JSON `file_entries`.
   - Methods: `validate_changes(base_dir: str, config: Dict) -> List[ApplydirError]`.

3. **ApplydirFileChange**:
   - Represents a single change.
   - Methods: `from_file_entry(file_path: Path, action: str, change_dict: Optional[Dict]) -> ApplydirFileChange`, `validate_change(config: Dict) -> List[ApplydirError]`.

4. **ApplydirMatcher**:
   - Matches lines with fuzzy options.
   - Methods: `match(file_content: List[str], change: ApplydirFileChange) -> Tuple[Optional[Dict], List[ApplydirError]]`.

5. **ApplydirApplicator**:
   - Applies changes.
   - Methods: `apply_changes() -> List[ApplydirError]`, supports create/replace/delete.

## Workflow
1. **Input**: Run `applydir <input_file>` with JSON changes.
2. **Parsing**: Load JSON, check `file_entries`, create `ApplydirChanges`.
3. **Validation**: Validate structure, paths, non-ASCII via `validate_changes`.
4. **Application**: Use `ApplydirApplicator` to match lines (`ApplydirMatcher`) and apply changes directly.
5. **Output**: Log errors/successes, return exit code (0 success, 1 failure).

## Planned Features
- **vibedir Integration**: LLM prompting, Git commits/rollbacks, linting.
- **Extended Actions**: More action types if needed.
- **Additional Validation**: Syntax/linting checks.

## Dependencies
- **prepdir**: For `load_config` (configuration) and `configure_logging` (logging).
- **Pydantic**: For model validation (e.g., `ApplydirError`, `ApplydirChanges`).
- **dynaconf**: For configuration merging.
- **difflib** (standard library): For sequence matcher in fuzzy matching.

## Python Best Practices
- PEP 8 compliant naming and structure.
- Type hints and Pydantic for safety.
- Modular classes for testability.
- Logging via `prepdir`.

## Edge Cases
- Invalid JSON/missing `file_entries`: Logged and exit 1.
- Non-existent files for replace/delete: `file_not_found` error.
- Existing files for create: `file_already_exists` error.
- Non-ASCII: Handled per config/CLI.
- Multiple/no matches: `multiple_matches` or `no_match` errors.

## Testing
- Tests in `tests/test_main.py` cover CLI execution, validation, errors, and options.
- Run: `pdm run pytest tests/test_main.py`

## Next Steps
- Implement `vibedir` for full workflow.