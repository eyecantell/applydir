from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from .applydir_changes import ApplydirChanges
from .applydir_file_change import ApplydirFileChange
from .applydir_matcher import ApplydirMatcher
from .applydir_applicator import ApplydirApplicator
from .applydir_distance import levenshtein_distance, levenshtein_similarity
from .main import main

__all__ = [
    "ApplydirError",
    "ErrorType",
    "ErrorSeverity",
    "ApplydirChanges",
    "ApplydirFileChange",
    "ApplydirMatcher",
    "ApplydirApplicator",
    "levenshtein_distance",
    "levenshtein_similarity",
    "main",
]

# Rebuild Pydantic models after all classes are defined
ApplydirError.model_rebuild()
