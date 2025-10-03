# applydir Design Overview (October 2, 2025)

## Overview
`applydir` is a Python command-line tool that automates applying LLM-generated code changes to a codebase with high reliability. It processes changes in a JSON format, supporting `replace_lines` (line-level modifications), `create_file` (new files), and `delete_file` (file deletions). Changes are applied directly to the codebase, with tracking/reversion handled by Git or other tools (planned via `vibedir`). It integrates with `prepdir` for logging and configuration. File paths are resolved relative to a base directory, matching `prepdir`’s output.

## Core Design Principles
- **Supported Actions**: `replace_lines` for line replacements, `create_file` for new files, `delete_file` for deletions (controlled by `allow_file_deletion`).
- **Direct Application**: Changes are applied directly to files; Git (via planned `vibedir`) handles tracking/reversion.
- **Reliability**: Hybrid matching (exact first, optional fuzzy fallback with Levenshtein or sequence matcher) ensures accurate line replacements.
- **JSON Input**: Minimal structure with `file_entries` containing `file`, `action`, and `changes`.
- **Relative Paths**: Paths (e.g., `src/main.py`) are relative to `--base-dir`.
- **Validation Simplicity**: Validates JSON structure, actions, paths, and non-ASCII characters.
- **Configuration**: Uses `prepdir`’s `load_config` for `config.yaml`, with CLI or programmatic overrides.

## JSON Format
The input is a JSON object with a `file_entries` array:

```json
{
  "file_entries": [
    {
      "file": "<relative_file_path>",
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
- **Top-Level**: Object with `file_entries` array.
- **File Entry**:
  - `file`: Relative path (e.g., `src/main.py`).
  - `action`: Required; `replace_lines`, `create_file`, or `delete_file`.
  - `changes`: Required for `replace_lines` and `create_file`, optional for `delete_file`.
- **Change Object**:
  - `original_lines`: Non-empty for `replace_lines`, empty for `create_file`, ignored for `delete_file`.
  - `changed_lines`: Non-empty for `replace_lines` or `create_file`, ignored for `delete_file`.

### Example Cases
- **Modification (replace_lines)**:
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
- **Addition**: `replace_lines` with `changed_lines` including additional lines.
- **Deletion**: `replace_lines` with fewer `changed_lines`, or `delete_file` for entire files.
- **Creation (create_file)**:
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
- **File Deletion (delete_file)**:
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

## Workflow
1. **User Input**: Run `applydir changes.json` with a JSON file specifying changes.
2. **Parsing**: `ApplydirChanges` parses `file_entries`, validates JSON structure.
3. **Validation**: `ApplydirChanges.validate_changes` checks paths and non-ASCII, creating `ApplydirFileChange` objects.
4. **Application**: `ApplydirApplicator` uses `ApplydirMatcher` to locate lines and applies changes (`create_file`, `replace_lines`, `delete_file`) directly to files.
5. **Output**: Logs errors or successes via `prepdir`’s `configure_logging`, returns exit code (0 for success, 1 for errors).

## Component Roles
- **prepdir**: Supplies file contents, `load_config` for configuration, `configure_logging` for logging.
- **applydir**: Validates JSON, applies changes, returns errors or success confirmations.
- **vibedir** (Planned): Will manage LLM prompts, Git integration, and linting.

## Configuration
Uses `.applydir/config.yaml` or bundled `src/applydir/config.yaml`, loaded via `prepdir`’s `load_config`. CLI options or `config_override` override settings.

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

- `validation.non_ascii`: Controls non-ASCII handling.
- `allow_file_deletion`: Enables/disables deletions.
- `matching`: Configures `ApplydirMatcher` (whitespace, similarity, metric, fuzzy).

## Validation Rules
- **JSON Structure (ApplydirChanges)**:
  - Non-empty `file_entries` array.
  - Valid `file` paths (resolvable within `base_dir`).
  - Valid `action` (`replace_lines`, `create_file`, `delete_file`).
  - Errors: `json_structure` (invalid structure), `invalid_change` (invalid action or changes).
- **Content Validation (ApplydirFileChange)**:
  - `replace_lines`: Non-empty `original_lines` and `changed_lines`.
  - `create_file`: Empty `original_lines`, non-empty `changed_lines`.
  - `delete_file`: Empty or absent `changes`.
  - Errors: `invalid_change`, `non_ascii_chars`.
- **File System Existence (ApplydirApplicator)**:
  - `delete_file`: File must exist (`file_not_found`).
  - `replace_lines`: File must exist (`file_not_found`).
  - `create_file`: File must not exist (`file_already_exists`).
  - Errors: `file_system` (operation failures).
- **Success Reporting**: `file_changes_successful` with `info` severity, including `file`, `actions`, and `change_count`.

## Ensuring Reliability
- **Unique Matching**: Hybrid matching (exact first, fuzzy fallback with Levenshtein or sequence matcher) ensures accurate replacements.
- **Deletion Safety**: Validates file existence and `allow_file_deletion`.
- **Creation Safety**: Validates non-existent paths for `create_file`.
- **Validation**: Checks JSON, paths, non-ASCII, and matching, with specific error types.
- **Success Confirmation**: `file_changes_successful` confirms successful changes per file.

## Edge Cases and Mitigations
- **New File Creation**: Validates non-existent path (`file_already_exists`, `file_system`).
- **File Deletion**: Validates existence (`file_not_found`) and permissions (`allow_file_deletion`).
- **Multiple/No Matches**: Returns `multiple_matches` or `no_match` errors.
- **Non-ASCII Characters**: Handled per `config.validation.non_ascii` (`non_ascii_chars`).
- **Invalid JSON**: Returns `json_structure` errors.

## Dependencies
- **prepdir**: Provides `load_config` and `configure_logging`.
- **Pydantic**: JSON parsing and validation.
- **dynaconf**: Configuration merging.
- **difflib**: Fuzzy matching in `ApplydirMatcher`.

## Planned Features
- **vibedir Integration**: LLM prompting, Git commits/rollbacks, linting, and diff view.
- **User Approval**: Workflow for reviewing and approving changes.
- **Extended Validation**: Syntax or linting checks.

## Next Steps
- Implement `vibedir` for LLM integration, Git, and linting.
- Add tests for edge cases (multiple matches, short files).
- Refine matching configuration if needed.