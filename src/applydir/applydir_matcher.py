from typing import List, Dict, Union, Optional
import difflib
import re
from .applydir_file_change import ApplyDirFileChange
from .applydir_error import ApplyDirError, ErrorType

class ApplyDirMatcher:
    """Matches original_lines in file content using fuzzy matching."""
    def __init__(self, similarity_threshold: float = 0.9, max_search_lines: Optional[int] = None):
        self.similarity_threshold = similarity_threshold
        self.max_search_lines = max_search_lines

    def match(self, file_content: List[str], change: ApplyDirFileChange) -> Union[Dict, List[ApplyDirError]]:
        """Finds original_lines in file_content, returns range or errors."""
        if not change.original_lines:
            return {"start_line": 0, "end_line": -1, "details": {"similarity_score": 1.0, "regex": ""}}

        # Generate regex for debugging
        regex = r"\n".join(re.escape(line) for line in change.original_lines)
        matcher = difflib.SequenceMatcher(None, change.original_lines, file_content)
        if matcher.ratio() >= self.similarity_threshold:
            # Simplified: Assume first matching block
            match = matcher.get_matching_blocks()[0]
            return {
                "start_line": match.b,
                "end_line": match.b + match.size - 1,
                "details": {"similarity_score": matcher.ratio(), "regex": regex}
            }
        return [ApplyDirError(
            change=change,
            error_type=ErrorType.MATCHING,
            message="No match found for original_lines",
            details={"similarity_score": matcher.ratio(), "regex": regex}
        )]