from typing import List
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)


# If this needs to get more complex, or we need it to be faster, consider using rapidfuzz (pdm install rapidfuzz)
def levenshtein_distance(s1: str, s2: str) -> int:
    """Computes the Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
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


def levenshtein_similarity(a: List[str], b: List[str]) -> float:
    """Calculate Levenshtein-based similarity for two lists of strings, joining with newlines."""
    if len(a) != len(b):
        return 0.0  # Early exit if line counts differ
    a_str = "\n".join(a)
    b_str = "\n".join(b)
    total_distance = levenshtein_distance(a_str, b_str)
    max_length = max(len(a_str), len(b_str))
    return 1.0 - total_distance / max_length if max_length > 0 else 1.0


def sequence_matcher_similarity(a: List[str], b: List[str]) -> float:
    """Calculate SequenceMatcher-based similarity for two lists of strings, joining with newlines."""
    if len(a) != len(b):
        return 0.0  # Early exit if line counts differ
    a_str = "\n".join(a)
    b_str = "\n".join(b)
    sm = SequenceMatcher(None, a_str, b_str)
    blocks = list(sm.get_matching_blocks())

    logger.debug(f"Matching blocks are {blocks}")
    return sm.ratio()
