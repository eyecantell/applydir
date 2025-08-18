from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from .applydir_file_change import ApplydirFileChange, ActionType
import logging
import re
from pathlib import Path

logger = logging.getLogger("applydir")

def levenshtein_similarity(a: List[str], b: List[str]) -> float:
    """Calculate Levenshtein-based similarity for two lists of strings."""
    def levenshtein(s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return levenshtein(s2, s1)
        if not s2:
            return len(s1)
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]
    
    total_distance = sum(levenshtein(a[i], b[i]) for i in range(min(len(a), len(b))))
    max_length = max(sum(len(s) for s in a), sum(len(s) for s in b))
    return 1.0 - total_distance / max_length if max_length > 0 else 1.0

class ApplydirMatcher:
    """Matches original_lines in file content using fuzzy matching."""

    def __init__(
        self,
        similarity_threshold: float = 0.95,
        max_search_lines: Optional[int] = None,
        case_sensitive: bool = True,
        config: Optional[Dict] = None,
    ):
        self.default_similarity_threshold = similarity_threshold
        self.max_search_lines = max_search_lines
        self.case_sensitive = case_sensitive
        self.config = config or {}

    def get_whitespace_handling(self, file_path: str) -> str:
        """Determine whitespace handling based on file extension."""
        default_handling = self.config.get("matching", {}).get("whitespace", {}).get("default", "collapse")
        if not file_path:
            return default_handling
        file_extension = Path(file_path).suffix.lower()
        rules = self.config.get("matching", {}).get("whitespace", {}).get("rules", [])
        for rule in rules:
            if file_extension in rule.get("extensions", []):
                return rule.get("handling", default_handling)
        return default_handling

    def get_similarity_threshold(self, file_path: str) -> float:
        """Determine similarity threshold based on file extension."""
        default_threshold = self.config.get("matching", {}).get("similarity", {}).get("default", self.default_similarity_threshold)
        if not file_path:
            return default_threshold
        file_extension = Path(file_path).suffix.lower()
        rules = self.config.get("matching", {}).get("similarity", {}).get("rules", [])
        for rule in rules:
            if file_extension in rule.get("extensions", []):
                return rule.get("threshold", default_threshold)
        return default_threshold

    def get_similarity_metric(self, file_path: str) -> str:
        """Determine similarity metric based on file extension."""
        default_metric = self.config.get("matching", {}).get("similarity_metric", {}).get("default", "sequence_matcher")
        if not file_path:
            return default_metric
        file_extension = Path(file_path).suffix.lower()
        rules = self.config.get("matching", {}).get("similarity_metric", {}).get("rules", [])
        for rule in rules:
            if file_extension in rule.get("extensions", []):
                return rule.get("metric", default_metric)
        return default_metric

    def match(self, file_content: List[str], change: ApplydirFileChange) -> Tuple[Optional[Dict], List[ApplydirError]]:
        """Matches original_lines in file_content, skips for create_file."""
        errors = []
        logger.debug(f"Matching for file: {change.file}, action: {change.action}")
        logger.debug(f"Input file_content: {file_content}")
        logger.debug(f"Input original_lines: {change.original_lines}")

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
        search_limit = max(0, n - m + 1) if self.max_search_lines is None else min(n - m + 1, self.max_search_lines)
        logger.debug(f"Search limit: {search_limit}, file lines: {n}, original lines: {m}")

        # Normalize lines based on whitespace handling
        whitespace_handling = self.get_whitespace_handling(change.file)
        similarity_threshold = self.get_similarity_threshold(change.file)
        similarity_metric = self.get_similarity_metric(change.file)
        logger.debug(f"Whitespace handling for {change.file}: {whitespace_handling}")
        logger.debug(f"Similarity threshold for {change.file}: {similarity_threshold}")
        logger.debug(f"Similarity metric for {change.file}: {similarity_metric}")

        def normalize(line: str) -> str:
            if whitespace_handling == "strict":
                norm = line
            elif whitespace_handling == "collapse":
                norm = re.sub(r'\s+', ' ', line.strip())
            elif whitespace_handling in ["remove", "ignore"]:
                norm = re.sub(r'\s+', '', line.strip())
            else:
                norm = re.sub(r'\s+', ' ', line.strip())  # Default to collapse
            norm = norm if self.case_sensitive else norm.lower()
            logger.debug(f"Normalized line: '{line}' -> '{norm}' (chars: {[ord(c) for c in norm]})")
            return norm
        
        normalized_original = [normalize(line) for line in change.original_lines]
        normalized_content = [normalize(line) for line in file_content]
        logger.debug(f"Normalized original_lines: {normalized_original}")
        logger.debug(f"Normalized file_content: {normalized_content}")

        # Check all possible windows of size m
        for i in range(search_limit):
            window = normalized_content[i : i + m]
            logger.debug(f"Checking window at index {i}: {window} (size: {len(window)})")
            if len(window) == m:
                if similarity_metric == "levenshtein":
                    ratio = levenshtein_similarity(window, normalized_original)
                    matching_blocks = []
                else:
                    matcher = SequenceMatcher(None, window, normalized_original, autojunk=False)
                    ratio = matcher.ratio()
                    matching_blocks = matcher.get_matching_blocks()
                logger.debug(f"Match attempt at index {i} for {change.file}, metric: {similarity_metric}, ratio: {ratio:.4f}, window: {window}, original: {normalized_original}, matching_blocks: {matching_blocks}")
                if ratio >= similarity_threshold or window == normalized_original:
                    matches.append({"start": i, "end": i + m})
                    logger.debug(f"Match found at index {i}, metric: {similarity_metric}, ratio: {ratio:.4f}, exact: {window == normalized_original}")

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