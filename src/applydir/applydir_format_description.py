def applydir_format_description() -> str:
    """Returns a description of the applydir JSON format for use in an LLM prompt.

    The description outlines the structure and requirements for the JSON input
    that `applydir` processes to apply changes to a codebase. This is intended for
    integration with `vibedir` to guide an LLM in generating compatible changes.

    Returns:
        str: A detailed description of the applydir JSON format.
    """
    return """
The applydir tool processes code changes specified in a JSON format to apply modifications, creations, or deletions to files in a codebase. The JSON must adhere to the following structure and requirements to ensure compatibility with applydir's processing logic:

1. **Top-Level Structure**:
   - The JSON object must contain a single key, `file_entries`, which is a non-empty array of objects.
   - Each object in `file_entries` represents changes to a single file.

2. **File Entry Structure**:
   - Each file entry is an object with the following fields:
     - `file`: A string specifying the file path (relative to a base directory or absolute). Must be non-empty and not just '.'.
     - `action`: A string specifying the action to perform. Must be one of:
       - `replace_lines`: Replace specific lines in an existing file. Multiple changes are allowed.
       - `create_file`: Create a new file with specified content.
       - `delete_file`: Delete an existing file. The `changes` array must be empty (`[]`), and the file must exist to avoid `file_not_found` errors.
     - `changes`: An array of change objects for `replace_lines` or `create_file` actions. For `delete_file`, this must be an empty array (`[]`).

3. **Change Object Structure** (for `replace_lines` and `create_file` actions):
   - Each change object within the `changes` array has:
     - `original_lines`: For `replace_lines`, an array of strings representing the lines to match in the existing file, which must be non-empty and contain enough lines to be uniquely identifiable within the file. For `create_file`, it must be empty (`[]`).
     - `changed_lines`: An array of strings representing the new lines to insert. Must be non-empty for both `replace_lines` and `create_file`.
   - For `replace_lines`, `original_lines` is used to locate the block to replace using exact or fuzzy matching (based on configuration).
   - For `create_file`, `changed_lines` provides the full content of the new file, and `original_lines` must be empty.

4. **Constraints and Validation**:
   - File paths must be valid, resolvable (relative to a base directory or absolute), and not point outside the project directory.
   - Non-ASCII characters in file paths or content may trigger errors or warnings based on configuration (e.g., error for `.py` files, ignore for `.md` files).
   - The JSON structure must be valid, with no missing required fields or invalid action types.

5. **Example JSON**:
```json
{
  "file_entries": [
    {
      "file": "src/main.py",
      "action": "replace_lines",
      "changes": [
        {
          "original_lines": ["print('Hello')"],
          "changed_lines": ["print('Hello World')"]
        },
        {
          "original_lines": ["def old_func():", "    pass"],
          "changed_lines": ["def updated_func():", "    return True"]
        }
      ]
    },
    {
      "file": "src/new.py",
      "action": "create_file",
      "changes": [
        {
          "original_lines": [],
          "changed_lines": ["def new_func():", "    pass"]
        }
      ]
    },
    {
      "file": "src/old.py",
      "action": "delete_file",
      "changes": []
    }
  ]
}
```

6. **Additional Notes**:
   - Use clear, valid file paths (e.g., `src/main.py` instead of vague or invalid paths like `./` or empty strings).
   - Ensure `original_lines` accurately reflects the content to match for `replace_lines` to avoid `no_match` or `multiple_matches` errors.
   - Avoid non-ASCII characters in critical files (e.g., `.py`, `.js`) unless explicitly allowed in configuration.

This format ensures applydir can parse and apply changes reliably while supporting validation and error handling.
"""