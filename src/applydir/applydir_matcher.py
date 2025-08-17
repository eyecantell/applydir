from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from .applydir_file_change import ApplydirFileChange, ActionType
import logging
import re

logger = logging.getLogger("applydir")

class ApplydirMatcher:
    """Matches original_lines in file content using fuzzy matching."""

    def __init__(self, similarity_threshold: float = 0.95, max_search_lines: Optional[int] = None):
        self.similarity_threshold = similarity_threshold
        self.max_search_lines = max_search_lines

    def match(self, file_content: List[str], change: ApplydirFileChange) -> Tuple[Optional[Dict], List[ApplydirError]]:
        """Matches original_lines in file_content, skips for create_file."""
        errors = []
        logger.debug(f"Matching for file: {change.file}, action: {change.action}")

        if change.action == ActionType.CREATE_FILE:
            logger.debug(f"Skipping match for create_file action: {change.file}")
            return None, []

        if not file_content:
            logger.debug(f"Empty file content for {change.file}")
            errors.append(
                ApplydirError(
                    change=change,
                    error_type=ErrorType.NO_MATCH,
                    severity=ErrorSeverity.ERROR,
                    message="No match: File is empty",
                    details={"file": str(change.file)},
                )
            )
            return None, errors

        if not change.original_lines:
            logger.debug(f"Empty original_lines for {change.file}")
            errors.append(
                ApplydirError(
                    change=change,
                    error_type=ErrorType.NO_MATCH,
                    severity=ErrorSeverity.ERROR,
                    message="No match: original_lines is empty",
                    details={"file": str(change.file)},
                )
            )
            return None, errors

        matches = []
        n = len(file_content)
        m = len(change.original_lines)
        search_limit = min(n - m + 1, self.max_search_lines) if self.max_search_lines else n - m + 1

        # Normalize lines: remove all whitespace for comparison
        def normalize(line: str) -> str:
            return re.sub(r'\s+', '', line.strip())
        
        normalized_original = [normalize(line) for line in change.original_lines]
        normalized_content = [normalize(line) for line in file_content]
        logger.debug(f"Normalized original_lines: {normalized_original}")
        logger.debug(f"Normalized file_content: {normalized_content}")

        # Check all possible windows of size m
        for i in range(search_limit):
            window = normalized_content[i : i + m]
            matcher = SequenceMatcher(None, window, normalized_original)
            ratio = matcher.ratio()
            logger.debug(f"Match attempt at index {i} for {change.file}, ratio: {ratio}, window: {window}")
            if ratio >= self.similarity_threshold:
                matches.append({"start": i, "end": i + m})

        if not matches:
            logger.debug(f"No matches found for {change.file}")
            errors.append(
                ApplydirError(
                    change=change,
                    error_type=ErrorType.NO_MATCH,
                    severity=ErrorSeverity.ERROR,
                    message="No matching lines found",
                    details={"file": str(change.file)},
                )
            )
            return None, errors

        if len(matches) > 1:
            logger.debug(f"Multiple matches found for {change.file}: {len(matches)} matches")
            errors.append(
                ApplydirError(
                    change=change,
                    error_type=ErrorType.MULTIPLE_MATCHES,
                    severity=ErrorSeverity.ERROR,
                    message="Multiple matches found for original_lines",
                    details={"file": str(change.file), "match_count": len(matches), "match_indices": [m["start"] for m in matches]},
                )
            )
            return None, errors

        logger.debug(f"Single match found for {change.file} at start: {matches[0]['start']}")
        return matches[0], []