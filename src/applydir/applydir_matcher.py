from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from .applydir_file_change import ApplydirFileChange, ActionType
from .applydir_distance import levenshtein_similarity, sequence_matcher_similarity
import logging
import re
from pathlib import Path

logger = logging.getLogger("applydir")


def _to_lowercase_keys(obj: Dict) -> Dict:
    """Recursively convert all dictionary keys to lowercase."""
    if not isinstance(obj, dict):
        return obj
    return {k.lower() if isinstance(k, str) else k: _to_lowercase_keys(v) for k, v in obj.items()}


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
        matching = self.config.get("matching", self.config.get("MATCHING", {}))
        default_handling = matching.get("whitespace", {}).get("default", "collapse")
        if not file_path:
            return default_handling
        file_extension = Path(file_path).suffix.lower()
        rules = matching.get("whitespace", {}).get("rules", [])
        for rule in rules:
            if file_extension in rule.get("extensions", []):
                return rule.get("handling", default_handling)
        return default_handling

    def get_similarity_threshold(self, file_path: str) -> float:
        """Determine similarity threshold based on file extension."""

        matching = self.config.get("matching", self.config.get("MATCHING", {}))
        default_threshold = matching.get("similarity", {}).get("default", self.default_similarity_threshold)
        # Validate default_threshold is a number
        if not isinstance(default_threshold, (int, float)):
            logger.warning(
                f"Invalid default similarity threshold '{default_threshold}', using {self.default_similarity_threshold}"
            )
            default_threshold = self.default_similarity_threshold

        if not file_path:
            return default_threshold
        file_extension = Path(file_path).suffix.lower()
        rules = matching.get("similarity", {}).get("rules", [])
        for rule in rules:
            if file_extension in rule.get("extensions", []):
                threshold = rule.get("threshold", default_threshold)
                if not isinstance(threshold, (int, float)):
                    logger.warning(
                        f"Invalid similarity threshold '{threshold}' for extension {file_extension}, using {default_threshold}"
                    )
                    return default_threshold
                logger.debug(f"Got {threshold=} for {file_extension=}")
                return threshold

        logger.debug(f"No rule found for {file_extension=}, using {default_threshold=}")
        return default_threshold

    def get_similarity_metric(self, file_path: str) -> str:
        """Determine similarity metric based on file extension."""

        matching = self.config.get("matching", self.config.get("MATCHING", {}))
        sim_metric = matching.get("similarity_metric", {}).get("default", "levenshtein")
        if not file_path:
            return sim_metric
        file_extension = Path(file_path).suffix.lower()
        rules = matching.get("similarity_metric", {}).get("rules", [])
        for rule in rules:
            if file_extension in rule.get("extensions", []):
                return rule.get("metric", sim_metric)
        return sim_metric.lower()

    def get_use_fuzzy(self, file_path: str) -> bool:
        """Determine if fuzzy matching should be used based on file extension."""
        matching = self.config.get("matching", self.config.get("MATCHING", {}))
        default_use_fuzzy = matching.get("use_fuzzy", {}).get("default", True)
        if not file_path:
            return default_use_fuzzy
        file_extension = Path(file_path).suffix.lower()
        rules = matching.get("use_fuzzy", {}).get("rules", [])
        for rule in rules:
            if file_extension in rule.get("extensions", []):
                return rule.get("use_fuzzy", default_use_fuzzy)
        return default_use_fuzzy

    # Normalize lines based on whitespace and case handling
    def normalize_line(self, line: str, whitespace_handling_type: str = "collapse", case_sensitive: bool = True) -> str:
        """Normalize line by handling whitespace and case according to parameters"""

        if whitespace_handling_type not in ["strict", "remove", "ignore", "collapse"]:
            logger.warning(
                f"Unknown whitespace handling type '{whitespace_handling_type}' (expecting 'strict', 'remove', 'ignore', or 'collapse') - will use collapse"
            )

        if whitespace_handling_type == "strict":
            norm = line
        elif whitespace_handling_type in ["remove", "ignore"]:
            norm = re.sub(r"\s+", "", line)
        else:  # Default to collapse
            norm = re.sub(r"\s+", " ", line.strip())  # Note that collapse also strips leading/trailing whitespace

        # Handle case
        norm = norm if case_sensitive else norm.lower()

        # Return result
        logger.debug(
            f"Normalized line: '{line}' -> '{norm}' ({whitespace_handling_type=}, case_sensitive={self.case_sensitive})"
        )
        return str(norm)

    def match(self, file_content: List[str], change: ApplydirFileChange) -> Tuple[Optional[Dict], List[ApplydirError]]:
        """Matches original_lines in file_content, tries exact first, then fuzzy if configured."""
        errors = []
        logger.debug(f"Matching for file: {change.file_path}, action: {change.action}")
        logger.debug(f"Input file_content: {file_content}")
        logger.debug(f"Input original_lines: {change.original_lines}")

        if change.action == ActionType.CREATE_FILE:
            logger.debug(f"Skipping match for create_file action: {change.file_path}")
            return None, []

        if not file_content:
            logger.debug(f"Empty file content for {change.file_path}")
            errors.append(
                ApplydirError(
                    change=change,
                    error_type=ErrorType.NO_MATCH,
                    severity=ErrorSeverity.ERROR,
                    message="No match: File is empty",
                    details={"file": str(change.file_path)},
                )
            )
            return None, errors

        if not change.original_lines:
            logger.debug(f"Empty original_lines for {change.file_path}")
            errors.append(
                ApplydirError(
                    change=change,
                    error_type=ErrorType.NO_MATCH,
                    severity=ErrorSeverity.ERROR,
                    message="No match: original_lines is empty",
                    details={"file": str(change.file_path)},
                )
            )
            return None, errors

        matches = []
        n = len(file_content)
        m = len(change.original_lines)
        search_limit = max(0, n - m + 1) if self.max_search_lines is None else min(n - m + 1, self.max_search_lines)
        logger.debug(f"Search limit: {search_limit}, file lines: {n}, original lines: {m}")

        whitespace_handling_type = self.get_whitespace_handling(change.file_path)

        logger.debug(f"Whitespace handling for {change.file_path}: {whitespace_handling_type}")

        normalized_original = [
            self.normalize_line(line, whitespace_handling_type, self.case_sensitive) for line in change.original_lines
        ]
        normalized_content = [
            self.normalize_line(line, whitespace_handling_type, self.case_sensitive) for line in file_content
        ]
        logger.debug(f"Normalized original_lines: {normalized_original}")
        logger.debug(f"Normalized file_content: {normalized_content}")

        # Exact matching first
        logger.debug(f"Attempting exact match for {change.file_path}")
        for i in range(search_limit):
            window = normalized_content[i : i + m]
            logger.debug(f"Checking exact window at index {i}: {window} (size: {len(window)})")
            if len(window) == m and window == normalized_original:
                matches.append({"start": i, "end": i + m})
                logger.debug(f"Exact match found at index {i} for {change.file_path}")

        # Fuzzy matching if no exact match and use_fuzzy is True
        use_fuzzy = self.get_use_fuzzy(change.file_path)
        logger.debug(f"Use fuzzy matching for {change.file_path}: {use_fuzzy}")
        if not matches and use_fuzzy:
            similarity_threshold = self.get_similarity_threshold(change.file_path)
            similarity_metric = self.get_similarity_metric(change.file_path)
            logger.debug(
                f"Trying fuzzy match for {change.file_path}, metric: {similarity_metric}, threshold: {similarity_threshold}"
            )
            for i in range(search_limit):
                window = normalized_content[i : i + m]
                logger.debug(f"Checking fuzzy window at index {i}: {window} (size: {len(window)})")
                if len(window) == m:
                    if similarity_metric == "sequence_matcher":
                        ratio = sequence_matcher_similarity(window, normalized_original)

                    else:
                        if similarity_metric is not None and similarity_metric != "levenshtein":
                            logger.warning(f"Unrecognized similarity_metric {similarity_metric} - using levenshtein")
                        ratio = levenshtein_similarity(window, normalized_original)

                    logger.debug(
                        f"Fuzzy match attempt at index {i} for {change.file_path}, metric: {similarity_metric}, ratio: {ratio:.4f}, window: {window}, original: {normalized_original}"
                    )
                    if ratio >= similarity_threshold:
                        matches.append({"start": i, "end": i + m})
                        logger.debug(f"Fuzzy match found at index {i}, metric: {similarity_metric}, ratio: {ratio:.4f}")

        if not matches:
            logger.debug(f"No matches found for {change.file_path}")
            errors.append(
                ApplydirError(
                    change=change,
                    error_type=ErrorType.NO_MATCH,
                    severity=ErrorSeverity.ERROR,
                    message="No matching lines found",
                    details={"file": str(change.file_path)},
                )
            )
            return None, errors

        if len(matches) > 1:
            logger.debug(f"Multiple matches found for {change.file_path}: {len(matches)} matches")
            errors.append(
                ApplydirError(
                    change=change,
                    error_type=ErrorType.MULTIPLE_MATCHES,
                    severity=ErrorSeverity.ERROR,
                    message="Multiple matches found for original_lines",
                    details={
                        "file": str(change.file_path),
                        "match_count": len(matches),
                        "match_indices": [m["start"] for m in matches],
                    },
                )
            )
            return None, errors

        logger.debug(f"Single match found for {change.file_path} at start: {matches[0]['start']}")
        return matches[0], []
