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

        matches = []
        n = len(file_content)
        m = len(change.original_lines)

        # Check all possible windows of size m
        for i in range(n - m + 1):
            matcher = SequenceMatcher(None, file_content[i : i + m], change.original_lines)
            if matcher.ratio() >= self.similarity_threshold:
                matches.append({"start": i, "end": i + m})

        if not matches:
            return [
                ApplydirError(
                    change=change,
                    error_type=ErrorType.MATCHING,
                    severity=ErrorSeverity.ERROR,
                    message="No matching lines found",
                    details={"file": change.file},
                )
            ]
        if len(matches) > 1:
            return [
                ApplydirError(
                    change=change,
                    error_type=ErrorType.MATCHING,
                    severity=ErrorSeverity.ERROR,
                    message="Multiple matches found for original_lines",
                    details={"file": change.file, "match_count": len(matches)},
                )
            ]
        return matches[0]
