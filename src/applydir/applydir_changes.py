from typing import List, Optional, Dict
import logging
from pydantic import BaseModel, field_validator, ConfigDict
from .applydir_file_change import ApplydirFileChange
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from pathlib import Path
from dynaconf import Dynaconf

# Set up logger
logger = logging.getLogger("applydir")


class FileEntry(BaseModel):
    """Represents a single file entry with a file path and list of changes."""
    file: str
    changes: List[ApplydirFileChange]
    model_config = ConfigDict(extra="ignore")  # Silently ignore extra fields


class ApplydirChanges(BaseModel):
    """Parses and validates JSON input for applydir changes."""

    files: List[FileEntry]
    model_config = ConfigDict(extra="allow")  # Allow extra fields at top level

    def __init__(self, **data):
        logger.debug(f"Raw input JSON for files: {data.get('files', [])}")
        super().__init__(**data)

    @field_validator("files")
    @classmethod
    def validate_files(cls, v: List[FileEntry]) -> List[FileEntry]:
        """Validates JSON structure and file entries."""
        errors = []
        if not v:
            errors.append(
                ApplydirError(
                    change=None,
                    error_type=ErrorType.JSON_STRUCTURE,
                    severity=ErrorSeverity.ERROR,
                    message="JSON must contain a non-empty array of files",
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
            if not file_entry.changes:
                errors.append(
                    ApplydirError(
                        change=None,
                        error_type=ErrorType.CHANGES_EMPTY,
                        severity=ErrorSeverity.ERROR,
                        message="Changes array is empty",
                        details={"file": file_entry.file},
                    )
                )
                
            # Set the file value in each change
            for change in file_entry.changes:
                change.file = file_entry.file

        if errors:
            raise ValueError(errors)
        return v

    def validate_changes(self, base_dir: str, config_override: Optional[Dict] = None) -> List[ApplydirError]:
        """Validates all file changes."""
        errors = []
        config = Dynaconf(settings_files=[{"validation": {"non_ascii": {"default": "warning"}}}] if not config_override else [config_override], merge_enabled=True)
        for file_entry in self.files:
            for change in file_entry.changes:
                change_obj = ApplydirFileChange(
                    file=file_entry.file,
                    original_lines=change.original_lines,
                    changed_lines=change.changed_lines,
                    base_dir=Path(base_dir),
                )
                errors.extend(change_obj.validate_change(config=config))
        return errors