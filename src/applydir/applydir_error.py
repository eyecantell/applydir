from typing import Optional, Dict, ClassVar
from pydantic import BaseModel, field_validator, ConfigDict, field_serializer
from enum import Enum

class ErrorSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"

class ErrorType(str, Enum):
    JSON_STRUCTURE = "json_structure"
    FILE_PATH = "file_path"
    CHANGES_EMPTY = "changes_empty"
    ORIG_LINES_NOT_EMPTY = "orig_lines_not_empty"
    ORIG_LINES_EMPTY = "orig_lines_empty"
    SYNTAX = "syntax"
    EMPTY_CHANGED_LINES = "empty_changed_lines"
    NO_MATCH = "no_match"
    MULTIPLE_MATCHES = "multiple_matches"
    FILE_SYSTEM = "file_system"
    LINTING = "linting"
    CONFIGURATION = "configuration"

    def __str__(self):
        return {
            ErrorType.JSON_STRUCTURE: "Invalid JSON structure or action",
            ErrorType.FILE_PATH: "Invalid file path",
            ErrorType.CHANGES_EMPTY: "Empty changes array for replace_lines or create_file",
            ErrorType.ORIG_LINES_NOT_EMPTY: "Non-empty original_lines not allowed for create_file",
            ErrorType.ORIG_LINES_EMPTY: "Empty original_lines not allowed for replace_lines",
            ErrorType.SYNTAX: "Invalid syntax in changed_lines",
            ErrorType.EMPTY_CHANGED_LINES: "Empty changed_lines for replace_lines or create_file",
            ErrorType.NO_MATCH: "No matching lines found in file",
            ErrorType.MULTIPLE_MATCHES: "Multiple matches found for original_lines",
            ErrorType.FILE_SYSTEM: "File system operation failed",
            ErrorType.LINTING: "Linting failed on file (handled by vibedir)",
            ErrorType.CONFIGURATION: "Invalid configuration",
        }[self]

class ApplydirError(BaseModel):
    change: Optional["ApplydirFileChange"] = None  # Forward reference
    error_type: ErrorType
    severity: ErrorSeverity = ErrorSeverity.ERROR
    message: str
    details: Optional[Dict] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # Allow Path objects in nested models
    )

    @field_serializer("change")
    def serialize_change(self, change: Optional["ApplydirFileChange"], _info) -> Optional[Dict]:
        """Serialize nested ApplydirFileChange using its model_dump."""
        return change.model_dump(mode="json") if change is not None else None

    @field_validator("message")
    @classmethod
    def message_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty or whitespace-only")
        return v

    @field_validator("details", mode="before")
    @classmethod
    def ensure_details_dict(cls, v: Optional[Dict]) -> Optional[Dict]:
        return v or {}