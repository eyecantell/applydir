from typing import Optional, Dict
from pydantic import BaseModel, field_validator, ConfigDict, field_serializer
from enum import Enum


class ErrorSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ErrorType(str, Enum):
    CHANGES_EMPTY = "changes_empty"
    FILE_CHANGES_SUCCESSFUL = "file_changes_successful"
    CONFIGURATION = "configuration"
    CHANGED_LINES_EMPTY = "empty_changed_lines"
    FILE_PATH = "file_path"
    FILE_NOT_FOUND = "file_not_found"
    FILE_ALREADY_EXISTS = "file_already_exists"
    FILE_SYSTEM = "file_system"
    JSON_STRUCTURE = "json_structure"
    LINTING = "linting"
    MULTIPLE_MATCHES = "multiple_matches"
    NO_MATCH = "no_match"
    NON_ASCII_CHARS = "non_ascii_chars"
    ORIG_LINES_EMPTY = "orig_lines_empty"
    ORIG_LINES_NOT_EMPTY = "orig_lines_not_empty"
    PERMISSION_DENIED = "permission_denied"
    SYNTAX = "syntax"
    INVALID_CHANGE = "invalid_change"

    def __str__(self):
        return {
            ErrorType.CHANGED_LINES_EMPTY: "Empty changed_lines for replace_lines or create_file",
            ErrorType.CHANGES_EMPTY: "Empty changes array for replace_lines or create_file",
            ErrorType.CONFIGURATION: "Invalid configuration",
            ErrorType.FILE_ALREADY_EXISTS: "File already exists",
            ErrorType.FILE_CHANGES_SUCCESSFUL: "All changes to file applied successfully",
            ErrorType.FILE_NOT_FOUND: "File does not exist",
            ErrorType.FILE_PATH: "Invalid file path",
            ErrorType.FILE_SYSTEM: "File system operation failed",
            ErrorType.INVALID_CHANGE: "Invalid change content for the specified action",
            ErrorType.JSON_STRUCTURE: "Invalid JSON structure or action",
            ErrorType.LINTING: "Linting failed on file (handled by vibedir)",
            ErrorType.MULTIPLE_MATCHES: "Multiple matches found for original_lines",
            ErrorType.NO_MATCH: "No matching lines found in file",
            ErrorType.NON_ASCII_CHARS: "Non-ASCII characters detected",
            ErrorType.ORIG_LINES_EMPTY: "Empty original_lines not allowed for replace_lines",
            ErrorType.ORIG_LINES_NOT_EMPTY: "Non-empty original_lines not allowed for create_file",
            ErrorType.PERMISSION_DENIED: "Permission denied",
            ErrorType.SYNTAX: "Invalid syntax in changed_lines",
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
