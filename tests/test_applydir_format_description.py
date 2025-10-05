import json
import pytest
from applydir import applydir_format_description

def test_applydir_format_description_output():
    """Test that applydir_format_description produces a valid prompt with expected content."""
    # Test with default filename
    prompt = applydir_format_description()
    assert "generate JSON content conforming to the applydir format described below and return it in a file named 'applydir_changes.json'" in prompt
    assert "**Top-Level Structure**:" in prompt
    assert "**Example JSON**:" in prompt
    assert "**Additional Notes**:" in prompt
    assert "For `replace_lines` with multiple changes" in prompt
    
    # Extract and validate example JSON
    json_start = prompt.index('```json\n') + len('```json\n')
    json_end = prompt.index('\n```', json_start)
    example_json_str = prompt[json_start:json_end]
    example_json = json.loads(example_json_str)
    assert "file_entries" in example_json
    assert len(example_json["file_entries"]) == 3  # Expect replace_lines, create_file, delete_file
    assert example_json["file_entries"][0]["action"] == "replace_lines"
    assert len(example_json["file_entries"][0]["changes"]) == 2  # Two changes for replace_lines
    assert example_json["file_entries"][1]["action"] == "create_file"
    assert example_json["file_entries"][2]["action"] == "delete_file"
    
    # Test with custom filename
    custom_prompt = applydir_format_description(filename="custom_changes.json")
    assert "generate JSON content conforming to the applydir format described below and return it in a file named 'custom_changes.json'" in custom_prompt