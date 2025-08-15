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

class ApplydirFileChange(BaseModel):
    """Represents a single file change with original and changed lines."""

    file: Optional[str] = None
    original_lines: List[str]
    changed_lines: List[str]
    base_dir: Optional[Path] = None
    action: ActionType

    model_config = ConfigDict(
        extra="forbid",  # Disallow extra fields
        arbitrary_types_allowed=True,  # Allow Path objects
    )

    @field_serializer("base_dir")
    def serialize_base_dir(self, base_dir: Optional[Path], _info) -> Optional[str]:
        """Serialize Path as string or None."""
        return str(base_dir) if base_dir is not None else None

    @field_serializer("action")
    def serialize_action(self, action: ActionType, _info) -> str:
        """Serialize ActionType as its string value."""
        return action.value

    @field_validator("file")
    @classmethod
    def validate_file_field(cls, v: Optional[str], info: ValidationInfo) -> str:
        """Ensures the file field is a non-empty string."""
        if not v:
            raise ValueError("File path must be non-empty")
        return v

    @field_validator("file")
    @classmethod
    def validate_file_path(cls, v: str, info: ValidationInfo) -> str:
        """Validates that the file path is resolvable within the project base_dir."""
        if not v:
            raise ValueError("File path must be non-empty")
        base_dir = info.data.get("base_dir") or Path.cwd()
        try:
            resolved_path = (base_dir / Path(v)).resolve()
            if not str(resolved_path).startswith(str(base_dir.resolve())):
                raise ValueError("File path is outside project directory")
        except Exception as e:
            raise ValueError(f"Invalid file path: {str(e)}")
        return v

    def validate_change(self, config: Dict = None) -> List[ApplydirError]:
        """Validates the change content."""
        errors = []

        if config is None:
            config = {}

        # Validate file path
        if not self.file:
            errors.append(
                ApplydirError(
                    change=self,
                    error_type=ErrorType.FILE_PATH,
                    severity=ErrorSeverity.ERROR,
                    message="No file path specified",
                )
            )

        # Validate action-specific rules
        if self.action == ActionType.REPLACE_LINES:
            if not self.original_lines:
                errors.append(
                    ApplydirError(
                        change=self,
                        error_type=ErrorType.CHANGES_EMPTY,
                        severity=ErrorSeverity.ERROR,
                        message="Empty original_lines not allowed for replace_lines",
                    )
                )
        elif self.action == ActionType.CREATE_FILE:
            if self.original_lines:
                errors.append(
                    ApplydirError(
                        change=self,
                        error_type=ErrorType.ORIG_LINES_NOT_EMPTY,
                        severity=ErrorSeverity.ERROR,
                        message="Non-empty original_lines not allowed for create_file",
                    )
                )

        # Determine non-ASCII action based on file extension
        non_ascii_action = config.get("validation", {}).get("non_ascii", {}).get("default", "ignore").lower()
        if self.file:
            file_extension = Path(self.file).suffix.lower()
            non_ascii_rules = config.get("validation", {}).get("non_ascii", {}).get("rules", [])
            for rule in non_ascii_rules:
                if file_extension in rule.get("extensions", []):
                    non_ascii_action = rule.get("action", non_ascii_action).lower()
                    break
        logger.debug(f"Non-ASCII action for {self.file}: {non_ascii_action}")

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