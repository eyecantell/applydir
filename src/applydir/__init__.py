from .applydir_applicator import ApplydirApplicator
from .applydir_changes import ApplydirChanges
from .applydir_distance import levenshtein_distance, levenshtein_similarity, sequence_matcher_similarity
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from .applydir_file_change import ApplydirFileChange, get_non_ascii_severity
from .applydir_format_description import applydir_format_description
from .applydir_matcher import ApplydirMatcher
from .main import main

__all__ = [
    "applydir_format_description",
    "ApplydirApplicator",
    "ApplydirChanges",
    "ApplydirError",
    "ApplydirFileChange",
    "ApplydirMatcher",
    "ErrorSeverity",
    "ErrorType",
    "get_non_ascii_severity",
    "levenshtein_distance",
    "levenshtein_similarity",
    "main",
    "sequence_matcher_similarity",
]

# Rebuild Pydantic models after all classes are defined
ApplydirError.model_rebuild()
