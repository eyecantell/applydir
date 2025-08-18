from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from .applydir_file_change import ApplydirFileChange, ActionType
from .applydir_distance import levenshtein_similarity
import logging
import re
from pathlib import Path

logger = logging.getLogger("applydir")

class ApplydirMatcher:
    """Matches original_lines in file content using exact and optional fuzzy matching."""

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

    def get_use_fuzzy(self, file_path: str) -> bool:
        """Determine if fuzzy matching should be used based on file extension."""
        default_use_fuzzy = self.config.get("matching", {}).get("use_fuzzy", {}).get("default", True)
        if not file_path:
            return default_use_fuzzy
        file_extension = Path(file_path).suffix.lower()
        rules = self.config.get("matching", {}).get("use_fuzzy", {}).get("rules", [])
        for rule in rules:
            if file_extension in rule.get("extensions", []):
                return rule.get("use_fuzzy", default_use_fuzzy)
        return default_use_fuzzy

    def match(self, file_content: List[str], change: ApplydirFileChange) -> Tuple[Optional[Dict], List[ApplydirError]]:
        """Matches original_lines in file_content, tries exact first, then fuzzy if configured."""
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
        use_fuzzy = self.get_use_fuzzy(change.file)
        logger.debug(f"Whitespace handling for {change.file}: {whitespace_handling}")
        logger.debug(f"Use fuzzy matching for {change.file}: {use_fuzzy}")

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

        # Exact matching first
        logger.debug(f"Attempting exact match for {change.file}")
        for i in range(search_limit):
            window = normalized_content[i : i + m]
            logger.debug(f"Checking exact window at index {i}: {window} (size: {len(window)})")
            if len(window) == m and window == normalized_original:
                matches.append({"start": i, "end": i + m})
                logger.debug(f"Exact match found at index {i} for {change.file}")

        # Fuzzy matching if no exact match and use_fuzzy is True
        if not matches and use_fuzzy:
            similarity_threshold = self.get_similarity_threshold(change.file)
            similarity_metric = self.get_similarity_metric(change.file)
            logger.debug(f"Fuzzy matching for {change.file}, metric: {similarity_metric}, threshold: {similarity_threshold}")
            for i in range(search_limit):
                window = normalized_content[i : i + m]
                logger.debug(f"Checking fuzzy window at index {i}: {window} (size: {len(window)})")
                if len(window) == m:
                    if similarity_metric == "levenshtein":
                        ratio = levenshtein_similarity(window, normalized_original)
                        matching_blocks = []
                    else:
                        matcher = SequenceMatcher(None, window, normalized_original, autojunk=False)
                        ratio = matcher.ratio()
                        matching_blocks = matcher.get_matching_blocks()
                    logger.debug(f"Fuzzy match attempt at index {i} for {change.file}, metric: {similarity_metric}, ratio: {ratio:.4f}, window: {window}, original: {normalized_original}, matching_blocks: {matching_blocks}")
                    if ratio >= similarity_threshold:
                        matches.append({"start": i, "end": i + m})
                        logger.debug(f"Fuzzy match found at index {i}, metric: {similarity_metric}, ratio: {ratio:.4f}")

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