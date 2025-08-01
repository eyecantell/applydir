from typing import List, Optional, Dict
from pathlib import Path
from pydantic import BaseModel, field_validator, ValidationInfo, ConfigDict
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
import logging

logger = logging.getLogger(__name__)

class ApplydirFileChange(BaseModel):
    """Represents a single file change with original and changed lines."""

    file: Optional[str] = None
    original_lines: List[str]
    changed_lines: List[str]
    base_dir: Optional[Path] = None

    model_config = ConfigDict(extra="forbid")  # Disallow extra fields

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

        if not self.file:
            errors.append(
                ApplydirError(
                    change=self,
                    error_type=ErrorType.FILE_PATH,
                    severity=ErrorSeverity.ERROR,
                    message="No file path specified",
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