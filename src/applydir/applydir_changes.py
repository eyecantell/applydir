from typing import List
from pydantic import BaseModel, field_validator, ConfigDict
from .applydir_file_change import ApplydirFileChange
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from pathlib import Path


class FileEntry(BaseModel):
    """Represents a single file entry with a file path and list of changes."""

    file: str
    changes: List[ApplydirFileChange]


class ApplydirChanges(BaseModel):
    """Parses and validates JSON input for applydir changes."""

    files: List[FileEntry]

    model_config = ConfigDict(extra="allow")  # Allow extra fields in JSON

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

        for file_entry in v:
            # Check for extra fields and add warning
            expected_keys = {"file", "changes"}
            extra_keys = set(file_entry.model_dump().keys()) - expected_keys
            if extra_keys:
                errors.append(
                    ApplydirError(
                        change=None,
                        error_type=ErrorType.JSON_STRUCTURE,
                        severity=ErrorSeverity.WARNING,
                        message="Extra fields found in JSON",
                        details={"extra_keys": list(extra_keys)},
                    )
                )

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

        if errors:
            raise ValueError(errors)
        return v

    def validate_changes(self, base_dir: str) -> List[ApplydirError]:
        """Validates all file changes."""
        errors = []
        for file_entry in self.files:
            for change in file_entry.changes:
                change_obj = ApplydirFileChange(
                    file=file_entry.file,
                    original_lines=change.original_lines,
                    changed_lines=change.changed_lines,
                    base_dir=Path(base_dir),
                )
                errors.extend(change_obj.validate_change())
        return errors
