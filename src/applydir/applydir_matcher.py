from difflib import SequenceMatcher
from typing import List, Dict, Union, Optional
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from .applydir_file_change import ApplydirFileChange


class ApplydirMatcher:
    """Matches original_lines in file content using fuzzy matching."""

    def __init__(self, similarity_threshold: float = 0.95, max_search_lines: Optional[int] = None):
        self.similarity_threshold = similarity_threshold
        self.max_search_lines = max_search_lines

    def match(self, file_content: List[str], change: ApplydirFileChange) -> Union[Dict, List[ApplydirError]]:
        """Matches original_lines in file_content."""
        matcher = SequenceMatcher(None, file_content, change.original_lines)
        match = matcher.find_longest_match(0, len(file_content), 0, len(change.original_lines))
        if match.size >= len(change.original_lines) * self.similarity_threshold:
            return {"start": match.a, "end": match.a + match.size}
        return [
            ApplydirError(
                change=change,
                error_type=ErrorType.MATCHING,
                severity=ErrorSeverity.ERROR,
                message="No matching lines found",
                details={"file": change.file},
            )
        ]
