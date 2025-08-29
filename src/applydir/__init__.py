from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from .applydir_changes import ApplydirChanges
from .applydir_file_change import ApplydirFileChange, get_non_ascii_severity
from .applydir_matcher import ApplydirMatcher
from .applydir_applicator import ApplydirApplicator
from .applydir_distance import levenshtein_distance, levenshtein_similarity, sequence_matcher_similarity
from .main import main

__all__ = [
    "ApplydirError",
    "ErrorType",
    "ErrorSeverity",
    "ApplydirChanges",
    "ApplydirFileChange",
    "ApplydirMatcher",
    "ApplydirApplicator",
    "get_non_ascii_severity",
    "levenshtein_distance",
    "levenshtein_similarity",
    "sequence_matcher_similarity",
    "main",
]

# Rebuild Pydantic models after all classes are defined
ApplydirError.model_rebuild()
