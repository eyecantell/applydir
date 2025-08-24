import pytest
import logging
from pathlib import Path
from prepdir import configure_logging
from applydir.applydir_matcher import ApplydirMatcher
from applydir.applydir_file_change import ApplydirFileChange, ActionType
from applydir.applydir_error import ApplydirError, ErrorType, ErrorSeverity

# Set up logging for tests
logger = logging.getLogger("applydir_test")
configure_logging(logger, level=logging.DEBUG)
logging.getLogger('applydir').setLevel(logging.DEBUG)


def test_normalize_line_strict_whitespace():
    """Test normalize_line with strict whitespace handling."""
    matcher = ApplydirMatcher(case_sensitive=True)
    line = "  print('Hello')  "
    result = matcher.normalize_line(line, whitespace_handling_type="strict")
    assert result == "  print('Hello')  "
    logger.debug(f"Strict whitespace normalization: '{line}' -> '{result}'")


def test_normalize_line_remove_whitespace():
    """Test normalize_line with remove whitespace handling."""
    matcher = ApplydirMatcher(case_sensitive=True)
    line = "  print('Hello')  "
    result = matcher.normalize_line(line, whitespace_handling_type="remove")
    assert result == "print('Hello')"
    logger.debug(f"Remove whitespace normalization: '{line}' -> '{result}'")


def test_normalize_line_ignore_whitespace():
    """Test normalize_line with ignore whitespace handling (same as remove)."""
    matcher = ApplydirMatcher(case_sensitive=True)
    line = "  print('Hello')  "
    result = matcher.normalize_line(line, whitespace_handling_type="ignore")
    assert result == "print('Hello')"
    logger.debug(f"Ignore whitespace normalization: '{line}' -> '{result}'")


def test_normalize_line_collapse_whitespace():
    """Test normalize_line with collapse whitespace handling."""
    matcher = ApplydirMatcher(case_sensitive=True)
    line = "  print(  'Hello'  )  "
    result = matcher.normalize_line(line, whitespace_handling_type="collapse")
    assert result == " print( 'Hello' ) "
    logger.debug(f"Collapse whitespace normalization: '{line}' -> '{result}'")


def test_normalize_line_unknown_whitespace_handling():
    """Test normalize_line with unknown whitespace handling (falls back to collapse)."""
    matcher = ApplydirMatcher(case_sensitive=True)
    line = "  print(  'Hello'  )  "
    result = matcher.normalize_line(line, whitespace_handling_type="invalid")
    assert result == " print( 'Hello' ) "
    logger.debug(f"Unknown whitespace normalization (fallback to collapse): '{line}' -> '{result}'")


def test_normalize_line_case_sensitive():
    """Test normalize_line with case-sensitive handling."""
    matcher = ApplydirMatcher(case_sensitive=True)
    line = "  Print('Hello')  "
    result = matcher.normalize_line(line, whitespace_handling_type="collapse", case_sensitive=True)
    assert result == " Print('Hello') "
    logger.debug(f"Case-sensitive normalization: '{line}' -> '{result}'")


def test_normalize_line_case_insensitive():
    """Test normalize_line with case-insensitive handling."""
    matcher = ApplydirMatcher(case_sensitive=False)
    line = "  Print('Hello')  "
    result = matcher.normalize_line(line, whitespace_handling_type="collapse", case_sensitive=False)
    assert result == " print('hello') "
    logger.debug(f"Case-insensitive normalization: '{line}' -> '{result}'")


def test_normalize_line_empty_input():
    """Test normalize_line with empty input."""
    matcher = ApplydirMatcher(case_sensitive=True)
    line = ""
    result = matcher.normalize_line(line, whitespace_handling_type="collapse")
    assert result == ""
    logger.debug(f"Empty input normalization: '{line}' -> '{result}'")


def test_normalize_line_only_whitespace():
    """Test normalize_line with input containing only whitespace."""
    matcher = ApplydirMatcher(case_sensitive=True)
    line = "   \t  "
    result = matcher.normalize_line(line, whitespace_handling_type="collapse")
    assert result == " "
    logger.debug(f"Only whitespace normalization: '{line}' -> '{result}'")


def test_match_replace_lines_single_match():
    """Test single fuzzy match for replace_lines action."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = ["print('Hello')", "x = 1"]
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    result, errors = matcher.match(file_lines, change)
    assert result == {"start": 0, "end": 1}
    assert len(errors) == 0
    logger.debug(f"Match found: {result}")


def test_match_replace_lines_whitespace_match():
    """Test whitespace match within similarity threshold."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["    print('Hello')"],  # four spaces leading
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = [" print('Hello')", "x = 1"]  # tab leading
    matcher = ApplydirMatcher(similarity_threshold=0.8)
    result, errors = matcher.match(file_lines, change)
    assert result == {"start": 0, "end": 1}
    assert len(errors) == 0
    logger.debug(f"Fuzzy match found: {result}")


def test_match_replace_lines_no_match():
    """Test no match for replace_lines action."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = ["print('World')", "x = 1"]
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    result, errors = matcher.match(file_lines, change)
    assert result is None
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.NO_MATCH
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "No matching lines found"
    assert errors[0].details == {"file": "src/main.py"}
    logger.debug(f"No match error: {errors[0]}")


def test_match_replace_lines_multiple_matches():
    """Test multiple matches for replace_lines action."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = ["print('Hello')", "x = 1", "print('Hello')"]
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    result, errors = matcher.match(file_lines, change)
    assert result is None
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.MULTIPLE_MATCHES
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "Multiple matches found for original_lines"
    assert errors[0].details["file"] == "src/main.py"
    assert errors[0].details["match_count"] == 2
    assert errors[0].details["match_indices"] == [0, 2]
    logger.debug(f"Multiple matches error: {errors[0]}")


def test_match_create_file_skips():
    """Test create_file action skips matching."""
    change = ApplydirFileChange(
        file_path="src/new.py",
        original_lines=[],
        changed_lines=["print('Hello World')"],
        action=ActionType.CREATE_FILE,
    )
    file_lines = ["print('Hello')", "x = 1"]
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    result, errors = matcher.match(file_lines, change)
    assert result is None
    assert len(errors) == 0
    logger.debug("Create file action skipped matching")


def test_match_empty_file():
    """Test matching against empty file for replace_lines."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = []
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    result, errors = matcher.match(file_lines, change)
    assert result is None
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.NO_MATCH
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "No match: File is empty"
    assert errors[0].details == {"file": "src/main.py"}
    logger.debug(f"Empty file error: {errors[0]}")


def test_match_empty_original_lines():
    """Test empty original_lines for replace_lines."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=[],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = ["print('Hello')", "x = 1"]
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    result, errors = matcher.match(file_lines, change)
    assert result is None
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.NO_MATCH
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "No match: original_lines is empty"
    assert errors[0].details == {"file": "src/main.py"}
    logger.debug(f"Empty original_lines error: {errors[0]}")


def test_match_partial_match():
    """Test partial match below similarity threshold."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Hello')", "x = 1"],
        changed_lines=["print('Hello World')", "x = 2"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = ["print('Hello')", "y = 1"]
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    result, errors = matcher.match(file_lines, change)
    assert result is None
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.NO_MATCH
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "No matching lines found"
    assert errors[0].details["file"] == "src/main.py"
    logger.debug(f"Partial match error: {errors[0]}")


def test_match_max_search_lines():
    """Test max_search_lines limits matching range."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = ["x = 1", "y = 2", "print('Hello')"]
    matcher = ApplydirMatcher(similarity_threshold=0.95, max_search_lines=2)
    result, errors = matcher.match(file_lines, change)
    assert result is None
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.NO_MATCH
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "No matching lines found"
    assert errors[0].details["file"] == "src/main.py"
    logger.debug(f"Max search lines error: {errors[0]}")


def test_match_similarity_threshold():
    """Test similarity threshold prevents low-similarity matches."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = ["print('Helo')"]  # Close but below threshold
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    result, errors = matcher.match(file_lines, change)
    assert result is None
    assert len(errors) == 1
    assert errors[0].error_type == ErrorType.NO_MATCH
    assert errors[0].severity == ErrorSeverity.ERROR
    assert errors[0].message == "No matching lines found"
    assert errors[0].details["file"] == "src/main.py"
    logger.debug(f"Similarity threshold error: {errors[0]}")


def test_match_multi_line_single_match():
    """Test single fuzzy match for multi-line original_lines."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Hello')", "x = 1", "y = 2"],
        changed_lines=["print('Hello World')", "x = 2", "y = 3"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = ["z = 0", "print('Hello')", "x = 1", "y = 2", "end"]
    matcher = ApplydirMatcher(similarity_threshold=0.95)
    result, errors = matcher.match(file_lines, change)
    assert result == {"start": 1, "end": 4}
    assert len(errors) == 0
    logger.debug(f"Multi-line match found: {result}")


def test_match_replace_lines_whitespace_difference():
    """Test whitespace difference match within similarity threshold."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = ["print('Hello ') ", "x = 1"]  # Extra whitespace
    matcher = ApplydirMatcher(
        case_sensitive=False,
        config={
            "matching": {
                "whitespace": {"default": "collapse", "rules": [{"extensions": [".py"], "handling": "remove"}]},
                "similarity": {"default": 0.95, "rules": [{"extensions": [".py"], "threshold": 0.8}]},
                "similarity_metric": {
                    "default": "sequence_matcher",
                    "rules": [{"extensions": [".py"], "metric": "levenshtein"}],
                },
                "use_fuzzy": {"default": True, "rules": [{"extensions": [".py"], "use_fuzzy": True}]},
            }
        },
    )
    result, errors = matcher.match(file_lines, change)
    assert result == {"start": 0, "end": 1}
    assert len(errors) == 0
    logger.debug(f"Fuzzy match with whitespace: {result}")


def test_match_fuzzy_typos_and_case():
    """Test fuzzy match with typos and case differences."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = ["Print('Helo')", "x = 1"]  # Case difference and typo
    matcher = ApplydirMatcher(
        case_sensitive=False,
        config={
            "matching": {
                "whitespace": {"default": "collapse", "rules": [{"extensions": [".py"], "handling": "remove"}]},
                "similarity": {"default": 0.95, "rules": [{"extensions": [".py"], "threshold": 0.5}]},
                "similarity_metric": {
                    "default": "sequence_matcher",
                    "rules": [{"extensions": [".py"], "metric": "levenshtein"}],
                },
                "use_fuzzy": {"default": True, "rules": [{"extensions": [".py"], "use_fuzzy": True}]},
            }
        },
    )
    result, errors = matcher.match(file_lines, change)
    assert result == {"start": 0, "end": 1}
    assert len(errors) == 0
    logger.debug(f"Fuzzy match with typos and case: {result}")


def test_match_exact_only():
    """Test exact match without fuzzy fallback."""
    change = ApplydirFileChange(
        file_path="src/main.py",
        original_lines=["print('Hello')"],
        changed_lines=["print('Hello World')"],
        action=ActionType.REPLACE_LINES,
    )
    file_lines = ["print('Hello')", "x = 1"]  # Exact match
    matcher = ApplydirMatcher(
        case_sensitive=False,
        config={
            "matching": {
                "whitespace": {"default": "collapse", "rules": [{"extensions": [".py"], "handling": "remove"}]},
                "use_fuzzy": {"default": True, "rules": [{"extensions": [".py"], "use_fuzzy": False}]},
            }
        },
    )
    result, errors = matcher.match(file_lines, change)
    assert result == {"start": 0, "end": 1}
    assert len(errors) == 0
    logger.debug(f"Exact match only: {result}")