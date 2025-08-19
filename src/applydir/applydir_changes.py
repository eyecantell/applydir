from typing import List, Optional, Dict
from pydantic import BaseModel, field_validator, ValidationInfo, ConfigDict
from .applydir_file_change import ApplydirFileChange, ActionType
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from pathlib import Path
import logging
from pydantic_core import PydanticCustomError

logger = logging.getLogger("applydir")

class FileEntry(BaseModel):
    """Represents a single file entry with a file path, action, and list of changes."""
    file: str  # Require non-empty file
    action: Optional[ActionType] = ActionType.REPLACE_LINES  # Default to replace_lines
    changes: Optional[List[Dict]] = None
    model_config = ConfigDict(extra="ignore")  # Silently ignore extra fields

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
        else:
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
                if file_entry.action in [ActionType.REPLACE_LINES, ActionType.CREATE_FILE] and not file_entry.changes:
                    errors.append(
                        ApplydirError(
                            change=None,
                            error_type=ErrorType.CHANGES_EMPTY,
                            severity=ErrorSeverity.ERROR,
                            message="Empty changes array for replace_lines or create_file",
                            details={"file": file_entry.file or ""},
                        )
                    )
                elif file_entry.action == ActionType.DELETE_FILE and file_entry.changes:
                    logger.warning(f"Ignoring changes for delete_file action in {file_entry.file}")
                if file_entry.changes:
                    for j, change in enumerate(file_entry.changes):
                        if not isinstance(change, dict):
                            errors.append(
                                ApplydirError(
                                    change=None,
                                    error_type=ErrorType.JSON_STRUCTURE,
                                    severity=ErrorSeverity.ERROR,
                                    message="Change must be a dictionary",
                                    details={"file": file_entry.file or "", "change_index": j},
                                )
                            )
                        if "original_lines" not in change or not isinstance(change["original_lines"], list):
                            errors.append(
                                ApplydirError(
                                    change=None,
                                    error_type=ErrorType.JSON_STRUCTURE,
                                    severity=ErrorSeverity.ERROR,
                                    message="Missing or invalid original_lines (must be list)",
                                    details={"file": file_entry.file or "", "change_index": j},
                                )
                            )
                        if "changed_lines" not in change or not isinstance(change["changed_lines"], list):
                            errors.append(
                                ApplydirError(
                                    change=None,
                                    error_type=ErrorType.JSON_STRUCTURE,
                                    severity=ErrorSeverity.ERROR,
                                    message="Missing or invalid changed_lines (must be list)",
                                    details={"file": file_entry.file or "", "change_index": j},
                                )
                            )
        if errors:
            raise PydanticCustomError(
                "value_error",
                str([e.model_dump() for e in errors]),
                {"errors": [e.model_dump() for e in errors]}
            )
        return v

    def validate_changes(self, base_dir: str, config_override: Optional[Dict] = None) -> List[ApplydirError]:
        """Validates all file changes for structure and path containment (no file system existence checks)."""
        errors = []
        config = config_override or {}
        logger.debug(f"Config used for validation: {config}")
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

            # Create change object for DELETE_FILE (structural validation only)
            change_obj = ApplydirFileChange(
                file_path=file_path,
                original_lines=[],
                changed_lines=[],
                action=file_entry.action,
            )

            if file_entry.action in [ActionType.REPLACE_LINES, ActionType.CREATE_FILE]:
                if not file_entry.changes:
                    errors.append(
                        ApplydirError(
                            change=change_obj,
                            error_type=ErrorType.CHANGES_EMPTY,
                            severity=ErrorSeverity.ERROR,
                            message="Empty changes array for replace_lines or create_file",
                            details={"file": file_entry.file},
                        )
                    )
                else:
                    for change in file_entry.changes:
                        try:
                            change_obj = ApplydirFileChange(
                                file_path=file_path,
                                original_lines=change.get("original_lines", []),
                                changed_lines=change.get("changed_lines", []),
                                action=file_entry.action,
                            )
                            errors.extend(change_obj.validate_change(config=config))
                        except Exception as e:
                            errors.append(
                                ApplydirError(
                                    change=change_obj,
                                    error_type=ErrorType.JSON_STRUCTURE,
                                    severity=ErrorSeverity.ERROR,
                                    message=f"Invalid change structure: {str(e)}",
                                    details={"file": file_entry.file},
                                )
                            )
        return errors