from typing import List, Dict, Union
from pydantic import BaseModel, field_validator, ConfigDict
from .applydir_file_change import ApplydirFileChange
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity


class ApplydirChanges(BaseModel):
    """Parses and validates JSON input for applydir changes."""

    files: List[Dict[str, Union[str, List[ApplydirFileChange]]]]

    model_config = ConfigDict(extra="allow")  # Allow extra fields in JSON

    @field_validator("files")
    @classmethod
    def validate_files(cls, v: List[Dict]) -> List[Dict]:
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
            extra_keys = set(file_entry.keys()) - expected_keys
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

            if not file_entry.get("file"):
                errors.append(
                    ApplydirError(
                        change=None,
                        error_type=ErrorType.FILE_PATH,
                        severity=ErrorSeverity.ERROR,
                        message="File path missing or empty",
                        details={},
                    )
                )
            if not file_entry.get("changes"):
                errors.append(
                    ApplydirError(
                        change=None,
                        error_type=ErrorType.CHANGES_EMPTY,
                        severity=ErrorSeverity.ERROR,
                        message="Changes array is empty",
                        details={"file": file_entry.get("file", "")},
                    )
                )

        if errors:
            raise ValueError(errors)
        return v

    def validate_changes(self, base_dir: str) -> List[ApplydirError]:
        """Validates all file changes."""
        errors = []
        for file_entry in self.files:
            for change in file_entry["changes"]:
                change_obj = ApplydirFileChange(file=file_entry["file"], **change.dict())
                errors.extend(change_obj.validate_change(base_dir=base_dir))
        return errors