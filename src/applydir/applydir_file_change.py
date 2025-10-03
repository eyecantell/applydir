from typing import List, Optional, Dict
from pathlib import Path
from pydantic import BaseModel, field_validator, ValidationInfo, ConfigDict, field_serializer
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from enum import Enum
import logging
import json

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
            raise ValueError("File path must be a valid Path object and non-empty (and not '.')")
        return v

    def validate_change(self, config: Dict = None) -> List[ApplydirError]:
        """Validates the change content.  Returns list of AppldirErrors found"""
        errors = []

        if config is None:
            config = {}

        logger.debug(f"{self} got config: " + json.dumps(config, indent=4))

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
                        error_type=ErrorType.CHANGED_LINES_EMPTY,
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
                        error_type=ErrorType.CHANGED_LINES_EMPTY,
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
                        severity=ErrorSeverity.WARNING,  # We allow this per design, but log a warning
                        message="The original_lines and changed_lines should be empty for delete_file",
                        details={"file": str(self.file_path)},
                    )
                )

        errors += self.check_for_non_ascii_chars(config)

        return errors

    def non_ascii_errors_from_lines(
        self, property_name: str, lines_to_check: List[str], severity: ErrorSeverity
    ) -> List[ApplydirError]:
        errors = []
        for i, line in enumerate(lines_to_check, 1):
            if any(ord(char) > 127 for char in str(line)):
                errors.append(
                    ApplydirError(
                        change=self,
                        error_type=ErrorType.NON_ASCII_CHARS,
                        severity=severity,
                        message=f"Non-ASCII characters found in {property_name}",
                        details={"line": str(line), "line_number": i},
                    )
                )
        return errors

    def check_for_non_ascii_chars(self, config: Dict) -> List[ApplydirError]:
        """Check for non-ascii characters per config. Returns list of ApplydirErrors when config actions are warning, errror"""
        # Determine non-ASCII action based on file extension

        if config is None:
            config = {}

        errors = []

        non_ascii_severity_for_path = get_non_ascii_severity(config, "path")
        if non_ascii_severity_for_path in [
            "error",
            "warning",
        ]:  # Apply non-ASCII validation if action is error or warning
            # Check path for non-ascii characters
            errors += self.non_ascii_errors_from_lines("file_path", [self.file_path], non_ascii_severity_for_path)

        non_ascii_severity_for_ext = get_non_ascii_severity(
            config, "extensions", file_extension=self.file_path.suffix.lower()
        )
        if non_ascii_severity_for_ext in [
            "error",
            "warning",
        ]:  # Apply non-ASCII validation if action is error or warning
            # Check lines for non-ascii characters
            errors += self.non_ascii_errors_from_lines("changed_lines", self.changed_lines, non_ascii_severity_for_ext)
            errors += self.non_ascii_errors_from_lines(
                "original_lines", self.original_lines, non_ascii_severity_for_ext
            )

        return errors

    @classmethod
    def from_file_entry(
        cls, file_path: Path, action: ActionType, change_dict: Optional[Dict] = None
    ) -> "ApplydirFileChange":
        """Creates an ApplydirFileChange instance from a FileEntry's change_dict."""
        try:
            if change_dict and isinstance(change_dict, Dict):
                original_lines = change_dict.get("original_lines", [])
                changed_lines = change_dict.get("changed_lines", [])
            else:
                original_lines = []
                changed_lines = []

            return cls(file_path=file_path, original_lines=original_lines, changed_lines=changed_lines, action=action)
        except Exception as e:
            logger.error(f"Failed to create ApplydirFileChange: {str(e)}")
            raise


def get_non_ascii_severity(config: Dict, rule_name: str, file_extension: str = None) -> str:
    if config is None:
        config = {}

    # Get default
    non_ascii_severity = (
        config.get("validation", config.get("VALIDATION", {})).get("non_ascii", {}).get("default", "ignore").lower()
    )
    non_ascii_rules = config.get("validation", config.get("VALIDATION", {})).get("non_ascii", {}).get("rules", [])

    if rule_name not in ["extensions", "path"]:
        raise ValueError(f"Unknown rule_name: {rule_name}, expected 'extensions' or 'path'")

    if rule_name == "extensions" and not file_extension:
        raise ValueError("Must have an extension when rule name is extension")

    # Check rules
    for rule in non_ascii_rules:
        if rule_name == "extensions" and file_extension in rule.get("extensions", []):
            non_ascii_severity = rule.get("action", non_ascii_severity).lower()
            break
        elif rule_name == "path" and rule.get("path"):
            non_ascii_severity = rule.get("action", non_ascii_severity).lower()

    rule_name_str = str(rule_name) + " " + str(file_extension) if file_extension else rule_name
    logger.debug(f"Non-ASCII action for {rule_name_str}: {non_ascii_severity}")
    return non_ascii_severity
