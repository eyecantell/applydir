from typing import List, Optional
from pathlib import Path
from pydantic import BaseModel, field_validator, ValidationInfo, ConfigDict
from dynaconf import Dynaconf
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity


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

    def validate_change(self, config: Dynaconf = Dynaconf()) -> List[ApplydirError]:
        """Validates the change content."""
        errors = []
        non_ascii_config = config.get("validation", {}).get("non_ascii", {}).get("default", "ignore")
        if non_ascii_config == "error":
            for i, line in enumerate(self.changed_lines, 1):
                if any(ord(char) > 127 for char in line):
                    errors.append(
                        ApplydirError(
                            change=self,
                            error_type=ErrorType.SYNTAX,
                            severity=ErrorSeverity.ERROR,
                            message="Non-ASCII characters found in changed_lines",
                            details={"line": line, "line_number": i},
                        )
                    )
        return errors