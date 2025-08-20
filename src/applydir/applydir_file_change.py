from typing import List, Optional, Dict
from pathlib import Path
from pydantic import BaseModel, field_validator, ValidationInfo, ConfigDict, field_serializer
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ActionType(str, Enum):
    REPLACE_LINES = "replace_lines"
    CREATE_FILE = "create_file"
    DELETE_FILE = "delete_file"

class ApplydirFileChange(BaseModel):
    """Represents a single file change with original and changed lines."""

    file_path: Path
    original_lines: List[str]
    changed_lines: List[str]
    action: ActionType

    model_config = ConfigDict(
        extra="forbid",  # Disallow extra fields
        arbitrary_types_allowed=True,  # Allow Path objects
    )

    @field_serializer("file_path")
    def serialize_file_path(self, file_path: Path, _info) -> str:
        """Serialize Path as string."""
        return str(file_path)

    @field_serializer("action")
    def serialize_action(self, action: ActionType, _info) -> str:
        """Serialize ActionType as its string value."""
        return action.value

    @field_validator("file_path")
    @classmethod
    def validate_file_path_field(cls, v: Path, info: ValidationInfo) -> Path:
        """Ensures the file_path is a valid Path object."""
        if not isinstance(v, Path) or not str(v).strip() or str(v) == ".":
            raise ValueError("File path must be a valid Path object and non-empty")
        return v

    def validate_change(self, config: Dict = None) -> List[ApplydirError]:
        """Validates the change content."""
        errors = []

        if config is None:
            config = {}

        # Action-specific validation
        if self.action == ActionType.CREATE_FILE:
            if self.original_lines:
                errors.append(
                    ApplydirError(
                        change=self,
                        error_type=ErrorType.ORIG_LINES_NOT_EMPTY,
                        severity=ErrorSeverity.ERROR,
                        message="Non-empty original_lines not allowed for create_file",
                        details={"file": str(self.file_path)},
                    )
                )
            if not self.changed_lines:
                errors.append(
                    ApplydirError(
                        change=self,
                        error_type=ErrorType.EMPTY_CHANGED_LINES,
                        severity=ErrorSeverity.ERROR,
                        message="Empty changed_lines not allowed for create_file",
                        details={"file": str(self.file_path)},
                    )
                )
        elif self.action == ActionType.REPLACE_LINES:
            if not self.original_lines:
                errors.append(
                    ApplydirError(
                        change=self,
                        error_type=ErrorType.ORIG_LINES_EMPTY,
                        severity=ErrorSeverity.ERROR,
                        message="Empty original_lines not allowed for replace_lines",
                        details={"file": str(self.file_path)},
                    )
                )
            if not self.changed_lines:
                errors.append(
                    ApplydirError(
                        change=self,
                        error_type=ErrorType.EMPTY_CHANGED_LINES,
                        severity=ErrorSeverity.ERROR,
                        message="Empty changed_lines not allowed for replace_lines",
                        details={"file": str(self.file_path)},
                    )
                )
        elif self.action == ActionType.DELETE_FILE:
            if self.original_lines or self.changed_lines:
                errors.append(
                    ApplydirError(
                        change=self,
                        error_type=ErrorType.INVALID_CHANGE,
                        severity=ErrorSeverity.ERROR,
                        message="original_lines and changed_lines must be empty for delete_file",
                        details={"file": str(self.file_path)},
                    )
                )

        # Determine non-ASCII action based on file extension
        non_ascii_action = config.get("validation", {}).get("non_ascii", {}).get("default", "ignore").lower()
        file_extension = self.file_path.suffix.lower()
        non_ascii_rules = config.get("validation", {}).get("non_ascii", {}).get("rules", [])
        for rule in non_ascii_rules:
            if file_extension in rule.get("extensions", []):
                non_ascii_action = rule.get("action", non_ascii_action).lower()
                break
        logger.debug(f"Non-ASCII action for {self.file_path}: {non_ascii_action}")

        # Apply non-ASCII validation if action is error or warning
        if non_ascii_action in ["error", "warning"]:
            for i, line in enumerate(self.changed_lines, 1):
                if any(ord(char) > 127 for char in line):
                    errors.append(
                        ApplydirError(
                            change=self,
                            error_type=ErrorType.SYNTAX,
                            severity=ErrorSeverity.ERROR if non_ascii_action == "error" else ErrorSeverity.WARNING,
                            message="Non-ASCII characters found in changed_lines",
                            details={"line": line, "line_number": i},
                        )
                    )

        return errors

    @classmethod
    def from_file_entry(cls, file_path: Path, action: ActionType, change_dict: Optional[Dict] = None) -> "ApplydirFileChange":
        """Creates an ApplydirFileChange instance from a FileEntry's change_dict."""
        try:
            if not change_dict or not isinstance(change_dict, Dict):
                original_lines = []
                changed_lines = []
            else:
                original_lines = change_dict.get("original_lines", []) 
                changed_lines = change_dict.get("changed_lines", [])
            return cls(
                file_path=file_path,
                original_lines=original_lines,
                changed_lines=changed_lines,
                action=action
            )
        except Exception as e:
            logger.error(f"Failed to create ApplydirFileChange: {str(e)}")
            raise