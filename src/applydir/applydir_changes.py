from typing import List, Optional
from pydantic import BaseModel, field_validator, ValidationInfo
from .applydir_file_change import ApplydirFileChange, ActionType
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from pathlib import Path
import logging

logger = logging.getLogger("applydir")


class FileEntry(BaseModel):
    """Represents a single file entry with a file path, action, and list of changes."""

    file: str
    action: Optional[str] = "replace_lines"  # Default to replace_lines
    changes: Optional[List[Dict]] = None
    model_config = ConfigDict(extra="ignore")  # Silently ignore extra fields

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: Optional[str]) -> Optional[str]:
        """Ensures action is valid."""
        if v not in ["delete_file", "replace_lines", "create_file", None]:
            raise ValueError(f"Invalid action: {v}. Must be 'delete_file', 'replace_lines', or 'create_file'.")
        return v


class ApplydirChanges(BaseModel):
    """Parses and validates JSON input for applydir changes."""

    files: List[FileEntry]
    model_config = ConfigDict(extra="allow")  # Allow extra fields at top level

    def __init__(self, **data):
        logger.debug(f"Raw input JSON for files: {data.get('files', [])}")
        super().__init__(**data)

    @field_validator("files")
    @classmethod
    def validate_files(cls, v: List[FileEntry], info: ValidationInfo) -> List[FileEntry]:
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
                # Validate based on action
                if file_entry.action == "delete_file":
                    if file_entry.changes:
                        logger.warning(f"Ignoring changes for delete_file action in {file_entry.file}")
                    file_path = Path(info.data.get("base_dir", Path.cwd())) / file_entry.file
                    if not file_path.exists():
                        errors.append(
                            ApplydirError(
                                change=None,
                                error_type=ErrorType.FILE_SYSTEM,
                                severity=ErrorSeverity.ERROR,
                                message="File does not exist for deletion",
                                details={"file": file_entry.file},
                            )
                        )
                elif file_entry.action in ["replace_lines", "create_file"]:
                    if not file_entry.changes:
                        errors.append(
                            ApplydirError(
                                change=None,
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
                                    file=file_entry.file,
                                    original_lines=change.get("original_lines", []),
                                    changed_lines=change.get("changed_lines", []),
                                    base_dir=Path(info.data.get("base_dir", Path.cwd())),
                                    action=ActionType(file_entry.action if file_entry.action else "replace_lines"),
                                )
                                if file_entry.action == "replace_lines" and not change.get("original_lines", []):
                                    errors.append(
                                        ApplydirError(
                                            change=change_obj,
                                            error_type=ErrorType.ORIG_LINES_EMPTY,
                                            severity=ErrorSeverity.ERROR,
                                            message="Empty original_lines not allowed for replace_lines",
                                            details={"file": file_entry.file},
                                        )
                                    )
                                errors.extend(change_obj.validate_change(config=info.data.get("config_override", {})))
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
        if errors:
            raise ValueError(errors)
        return v

    def validate_changes(self, base_dir: str, config_override: Optional[Dict] = None) -> List[ApplydirError]:
        """Validates all file changes."""
        errors = []
        config = config_override or {}
        logger.debug(f"Config used for validation: {config}")
        for file_entry in self.files:
            if file_entry.action in ["replace_lines", "create_file"]:
                if not file_entry.changes:
                    errors.append(
                        ApplydirError(
                            change=None,
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
                                file=file_entry.file,
                                original_lines=change.get("original_lines", []),
                                changed_lines=change.get("changed_lines", []),
                                base_dir=Path(base_dir),
                                action=ActionType(file_entry.action if file_entry.action else "replace_lines"),
                            )
                            if file_entry.action == "replace_lines" and not change.get("original_lines", []):
                                errors.append(
                                    ApplydirError(
                                        change=change_obj,
                                        error_type=ErrorType.ORIG_LINES_EMPTY,
                                        severity=ErrorSeverity.ERROR,
                                        message="Empty original_lines not allowed for replace_lines",
                                        details={"file": file_entry.file},
                                    )
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
