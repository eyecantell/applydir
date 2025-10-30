def applydir_format_description(filename: str = "applydir_changes.json", include_commit_message: bool = False,) -> str:
    """Returns a description of the applydir JSON format for use in an LLM prompt.

    The description outlines the structure and requirements for the JSON input
    that `applydir` processes to apply changes to a codebase. It includes
    instructions for the LLM to return the JSON content in a file with the
    specified filename. This is intended for integration with `vibedir` to guide
    an LLM in generating compatible changes.

    Args:
        filename (str, optional): The name of the file in which the LLM should
            return the JSON content. Defaults to "applydir_changes.json".

    Returns:
        str: A detailed description of the applydir JSON format with instructions
            for file output.
    """
    description = f"When recommending code changes, you must generate JSON content conforming to the applydir format described below and return it in a file named '{filename}', containing only the JSON data, separate from any explanatory text or metadata."

    description += "\n".join([
       "The applydir tool processes code changes specified in a JSON format to apply modifications, creations, or deletions to files in a codebase. The JSON must adhere to the following structure and requirements to ensure compatibility with applydir's processing logic:",
       "1. **Top-Level Structure**:"
       ])

    if include_commit_message:
      description += "\n   - The JSON object must contain two top-level keys: `file_entries`, which is a non-empty array of objects, and 'message', which is a git commit message describing the changes in file_entries as a whole."
    else:
      description += "\n   - The JSON object must contain a single key, `file_entries`, which is a non-empty array of objects."

    description +="""

   - Each object in `file_entries` represents changes to a single file.

2. **File Entry Structure**:
   - Each file entry is an object with the following fields:
     - `file`: A string specifying a resolvable file path (relative to `--base-dir`or absolute). Must be non-empty and not just '.'.
     - `action`: A string specifying the action to perform. Must be one of:
       - `replace_lines`: Replace specific lines in an existing file. Multiple changes are allowed.
       - `create_file`: Create a new file with specified content.
       - `delete_file`: Delete an existing file. The `changes` array must be empty (`[]`), and the file must exist to avoid `file_not_found` errors.
     - `changes`: An array of change objects for `replace_lines` or `create_file` actions. For `delete_file`, this must be an empty array (`[]`).

3. **Change Object Structure** (for `replace_lines` and `create_file` actions):
   - Each change object within the `changes` array has:
     - `original_lines`: For `replace_lines`, an array of strings representing the lines to match in the existing file, which must be non-empty and contain enough lines to be uniquely identifiable within the file. For `create_file`, `original_lines` must be empty (`[]`).
     - `changed_lines`: An array of strings representing the new lines to insert. Must be non-empty for both `replace_lines` and `create_file`.
   - For `replace_lines`, `original_lines` is used to locate the block (set of lines) to replace.
   - For `create_file`, `changed_lines` provides the full content of the new file, and `original_lines` must be empty.

4. **Constraints and Validation**:
   - Non-ASCII characters in file paths or content may trigger errors or warnings based on configuration (e.g., error for `.py` files, ignore for `.md` files).
   - The JSON structure must be valid, with no missing required fields or invalid action types.

5. **Example JSON**:
```json
{
"""
    if include_commit_message:
       description += """  "message": "Added 'World' to print. Defined updated_func.", """
    description += """
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
   - Ensure `original_lines` accurately reflects the file content to match for `replace_lines` to avoid `no_match` or `multiple_matches` errors.
   - For `replace_lines`, you may include multiple change objects in the `changes` array to apply multiple replacements in a single file.
   - For `replace_lines` with multiple changes in a single file, ensure original_lines do not target overlapping sections of the file. If overlaps occur, combine the changes into a single change object to avoid conflicts during application.
"""
    if include_commit_message:
       description += """
7. **Commit Message**:
   - Include a top-level field `message` with a concise Git commit message describing the changes provided.
   - It may contain line breaks (`\\n`) for a title + body.
   - Example: `{"message": "feat: add JWT auth\\n\\n- implement token generation\\n- add tests"}
"""
    return description