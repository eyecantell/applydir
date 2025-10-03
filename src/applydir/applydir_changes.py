from typing import List, Optional, Dict
from pydantic import BaseModel, field_validator, ValidationInfo, ConfigDict
from .applydir_file_change import ApplydirFileChange, ActionType
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from pathlib import Path
import logging
import json
from pydantic_core import PydanticCustomError

logger = logging.getLogger("applydir")


class FileEntry(BaseModel):
    """Represents a single file entry with a file path, action, and list of changes."""

    file: str  # Require non-empty file
    action: Optional[ActionType] = ActionType.REPLACE_LINES  # Default to replace_lines
    changes: Optional[List[Dict]] = None
    model_config = ConfigDict(extra="ignore")  # Silently ignore extra fields

    @field_validator("file")
    @classmethod
    def validate_file(cls, v: str) -> str:
        """Ensures the file path is a non-empty string."""
        if not v or not v.strip():
            raise ValueError("File path must be non-empty")
        return v

    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, v: Optional[str]) -> Optional[ActionType]:
        """Ensures action is valid."""
        if v is None:
            return ActionType.REPLACE_LINES
        try:
            return ActionType(v)
        except ValueError:
            raise ValueError(f"Invalid action: {v}. Must be 'delete_file', 'replace_lines', or 'create_file'.")


class ApplydirChanges(BaseModel):
    """Parses and validates JSON input for applydir changes as a container class."""

    file_entries: List[FileEntry]
    model_config = ConfigDict(extra="allow")  # Allow extra fields at top level

    def __init__(self, **data):
        logger.debug(f"Raw input JSON for file_entries: {data.get('file_entries', [])}")
        super().__init__(**data)

    @field_validator("file_entries")
    @classmethod
    def validate_file_entries(cls, v: List[FileEntry], info: ValidationInfo) -> List[FileEntry]:
        """Validates basic JSON structure and file entries (types only; deep validation in validate_changes)."""
        errors = []
        if not v:
            errors.append(
                ApplydirError(
                    change=None,
                    error_type=ErrorType.JSON_STRUCTURE,
                    severity=ErrorSeverity.ERROR,
                    message="JSON must contain a non-empty array of file entries",
                    details={},
                )
            )
            raise ValueError(errors)
        for i, file_entry in enumerate(v):
            if not file_entry.file:
                errors.append(
                    ApplydirError(
                        change=None,
                        error_type=ErrorType.FILE_PATH,
                        severity=ErrorSeverity.ERROR,
                        message="File path missing or empty",
                        details={},
                    )
                )
        if errors:
            raise ValueError(errors)
        return v

    def validate_changes(self, base_dir: str, config: Optional[Dict] = None) -> List[ApplydirError]:
        """Validates all file changes for structure (via ApplydirFileChange) and path containment. No file system checks."""
        errors = []
        if config is None:
            config = {}

        logger.debug(f"Config used for validate_changes:" + json.dumps(config, indent=4))
        base_path = Path(base_dir).resolve()

        for file_entry in self.file_entries:
            # Validate file path containment (safety check)
            try:
                file_path = (base_path / file_entry.file).resolve()
                if not str(file_path).startswith(str(base_path)):
                    errors.append(
                        ApplydirError(
                            change=None,
                            error_type=ErrorType.FILE_PATH,
                            severity=ErrorSeverity.ERROR,
                            message="File path is outside project directory",
                            details={"file": file_entry.file},
                        )
                    )
                    continue
            except Exception as e:
                errors.append(
                    ApplydirError(
                        change=None,
                        error_type=ErrorType.FILE_PATH,
                        severity=ErrorSeverity.ERROR,
                        message=f"Invalid file path: {str(e)}",
                        details={"file": file_entry.file},
                    )
                )
                continue

            # Process changes (or lack thereof if no changes)
            change_dicts = file_entry.changes or [None]  # Treat empty changes as a single None entry
            for change in change_dicts:
                try:
                    change_obj = ApplydirFileChange.from_file_entry(
                        file_path=file_path, action=file_entry.action, change_dict=change
                    )
                    errors.extend(change_obj.validate_change(config=config))
                except Exception as e:
                    errors.append(
                        ApplydirError(
                            change=None,
                            error_type=ErrorType.JSON_STRUCTURE,
                            severity=ErrorSeverity.ERROR,
                            message=f"Invalid change structure: {str(e)}",
                            details={"file": file_entry.file},
                        )
                    )

        return errors
