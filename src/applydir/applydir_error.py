from typing import Optional, Dict, ClassVar
from pydantic import BaseModel, field_validator
from enum import Enum


class ErrorSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class ErrorType(str, Enum):
    JSON_STRUCTURE = "json_structure"
    FILE_PATH = "file_path"
    CHANGES_EMPTY = "changes_empty"
    SYNTAX = "syntax"
    EMPTY_CHANGED_LINES = "empty_changed_lines"
    MATCHING = "matching"
    FILE_SYSTEM = "file_system"
    LINTING = "linting"


class ApplydirError(BaseModel):
    """Represents an error or warning in the applydir process, used for LLM-related validation and vibedir linting.

    Error type descriptions:
    - json_structure: Bad JSON structure received (e.g., not an array or extra fields).
    - file_path: Invalid file path provided (e.g., outside project directory).
    - changes_empty: Empty changes array for file.
    - syntax: Invalid syntax in changed lines (e.g., non-ASCII characters, configurable via applydir_config.yaml).
    - empty_changed_lines: Empty changed lines for new file.
    - matching: No matching lines found in file.
    - file_system: File system operation failed (e.g., file exists, permissions).
    - linting: Linting failed on file (handled by vibedir).
    """

    ERROR_DESCRIPTIONS: ClassVar[Dict[ErrorType, str]] = {
        ErrorType.JSON_STRUCTURE: "Bad JSON structure received",
        ErrorType.FILE_PATH: "Invalid file path provided",
        ErrorType.CHANGES_EMPTY: "Empty changes array for file",
        ErrorType.SYNTAX: "Invalid syntax in changed lines",
        ErrorType.EMPTY_CHANGED_LINES: "Empty changed lines for new file",
        ErrorType.MATCHING: "No matching lines found",
        ErrorType.FILE_SYSTEM: "File system operation failed",
        ErrorType.LINTING: "Linting failed on file (handled by vibedir)",
    }

    change: Optional["ApplydirFileChange"] = None  # Forward reference
    error_type: ErrorType
    severity: ErrorSeverity = ErrorSeverity.ERROR
    message: str
    details: Optional[Dict] = None

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
