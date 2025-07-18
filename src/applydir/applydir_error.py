from typing import Optional, Dict
from pydantic import BaseModel, validator
from enum import Enum

class ErrorType(str, Enum):
    JSON_STRUCTURE = "json_structure"
    FILE_PATH = "file_path"
    CHANGES_EMPTY = "changes_empty"
    SYNTAX = "syntax"
    ADDITION_MISMATCH = "addition_mismatch"
    EMPTY_CHANGED_LINES = "empty_changed_lines"
    MATCHING = "matching"
    FILE_SYSTEM = "file_system"
    LINTING = "linting"

class ApplyDirError(BaseModel):
    """Represents a single error in the applydir process."""
    change: Optional["ApplyDirFileChange"] = None  # Forward reference
    error_type: ErrorType
    message: str
    details: Optional[Dict] = None

    @validator("message")
    def message_non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("Message cannot be empty")
        return v

    @validator("details", pre=True)
    def ensure_details_dict(cls, v: Optional[Dict]) -> Optional[Dict]:
        return v or {}

# Avoid circular import issues
ApplyDirError.update_forward_refs()