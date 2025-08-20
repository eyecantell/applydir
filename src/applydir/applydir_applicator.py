import logging
from .applydir_changes import ApplydirChanges
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from .applydir_file_change import ApplydirFileChange, ActionType
from .applydir_matcher import ApplydirMatcher
from dynaconf import Dynaconf
from pathlib import Path
from prepdir import load_config
from typing import List, Optional, Dict

logger = logging.getLogger("applydir")

class ApplydirApplicator:
    """Applies validated changes to files."""

    def __init__(
        self,
        base_dir: str = ".",
        changes: Optional[ApplydirChanges] = None,
        matcher: Optional[ApplydirMatcher] = None,
        logger: Optional[logging.Logger] = None,
        config_override: Optional[Dict] = None,
    ):
        self.base_dir = Path(base_dir)
        self.changes = changes
        self.logger = logger or logging.getLogger("applydir")
        default_config = load_config(namespace="applydir") or {
            "validation": {"non_ascii": {"default": "warning", "rules": []}},
            "allow_file_deletion": True,
            "matching": {
                "whitespace": {"default": "collapse"},
                "similarity": {"default": 0.95},
                "similarity_metric": {"default": "sequence_matcher"},
                "use_fuzzy": {"default": True},
            },
        }
        self.config = Dynaconf(settings_files=[default_config], merge_enabled=True)
        if config_override:
            self.config.update(config_override, merge=True)
        self.matcher = matcher or ApplydirMatcher(config=self.config)

    def apply_changes(self) -> List[ApplydirError]:
        """Applies all changes directly to files in base_dir."""
        errors = []
        if not self.changes:
            return errors
        for file_entry in self.changes.file_entries:
            file_path = self.base_dir / file_entry.file
            if file_entry.action == ActionType.DELETE_FILE:
                errors.extend(self.delete_file(file_path, file_entry.file))
            elif file_entry.action in [ActionType.REPLACE_LINES, ActionType.CREATE_FILE]:
                for change in file_entry.changes:
                    # Ensure change is an ApplydirFileChange object
                    if isinstance(change, dict):
                        try:
                            change = ApplydirFileChange(**change, file_path=file_path, action=file_entry.action)
                        except Exception as e:
                            errors.append(
                                ApplydirError(
                                    change=None,
                                    error_type=ErrorType.INVALID_CHANGE,
                                    severity=ErrorSeverity.ERROR,
                                    message=f"Failed to convert change to ApplydirFileChange: {str(e)}",
                                    details={"file": file_entry.file},
                                )
                            )
                            continue
                    errors.extend(self.apply_single_change(file_path, change))
            else:
                errors.append(
                    ApplydirError(
                        change=None,
                        error_type=ErrorType.INVALID_CHANGE,
                        severity=ErrorSeverity.ERROR,
                        message=f"Unsupported action: {file_entry.action}",
                        details={"file": file_entry.file},
                    )
                )
        return errors

    def apply_single_change(self, file_path: Path, change: ApplydirFileChange) -> List[ApplydirError]:
        """Applies a single change to a file for REPLACE_LINES or CREATE_FILE."""
        errors = []
        try:
            # Validate change structure (non-ASCII, action rules)
            validation_errors = change.validate_change(self.config.get("validation", {}))
            errors.extend(validation_errors)
            if validation_errors:
                return errors

            # File system existence checks
            if change.action == ActionType.CREATE_FILE:
                if file_path.exists():
                    errors.append(
                        ApplydirError(
                            change=change,
                            error_type=ErrorType.FILE_ALREADY_EXISTS,
                            severity=ErrorSeverity.ERROR,
                            message="File already exists for new file creation",
                            details={"file": str(change.file_path)},
                        )
                    )
                    return errors
                self.write_changes(file_path, change.changed_lines, None)
                errors.append(
                    ApplydirError(
                        change=change,
                        error_type=ErrorType.FILE_CHANGES_SUCCESSFUL,
                        severity=ErrorSeverity.INFO,
                        message="All changes to file applied successfully",
                        details={"file": str(change.file_path), "action": change.action.value, "change_count": 1},
                    )
                )
            elif change.action == ActionType.REPLACE_LINES:
                if not file_path.exists():
                    errors.append(
                        ApplydirError(
                            change=change,
                            error_type=ErrorType.FILE_NOT_FOUND,
                            severity=ErrorSeverity.ERROR,
                            message="File does not exist for modification",
                            details={"file": str(change.file_path)},
                        )
                    )
                    return errors
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read().splitlines()
                match_result, match_errors = self.matcher.match(file_content, change)
                errors.extend(match_errors)
                if match_result:
                    self.write_changes(file_path, change.changed_lines, match_result)
                    errors.append(
                        ApplydirError(
                            change=change,
                            error_type=ErrorType.FILE_CHANGES_SUCCESSFUL,
                            severity=ErrorSeverity.INFO,
                            message="All changes to file applied successfully",
                            details={"file": str(change.file_path), "action": change.action.value, "change_count": 1},
                        )
                    )
        except Exception as e:
            errors.append(
                ApplydirError(
                    change=change,
                    error_type=ErrorType.FILE_SYSTEM,
                    severity=ErrorSeverity.ERROR,
                    message=f"File operation failed: {str(e)}",
                    details={"file": str(change.file_path)},
                )
            )
        return errors

    def delete_file(self, file_path: Path, relative_path: str) -> List[ApplydirError]:
        """Deletes a file."""
        errors = []
        if not self.config.get("allow_file_deletion", True):
            errors.append(
                ApplydirError(
                    change=None,
                    error_type=ErrorType.PERMISSION_DENIED,
                    severity=ErrorSeverity.ERROR,
                    message="File deletion is disabled in configuration",
                    details={"file": relative_path},
                )
            )
            return errors
        try:
            if not file_path.exists():
                errors.append(
                    ApplydirError(
                        change=None,
                        error_type=ErrorType.FILE_NOT_FOUND,
                        severity=ErrorSeverity.ERROR,
                        message="File does not exist for deletion",
                        details={"file": relative_path},
                    )
                )
                return errors
            file_path.unlink()
            self.logger.info(f"Deleted file: {relative_path}")
            errors.append(
                ApplydirError(
                    change=None,
                    error_type=ErrorType.FILE_CHANGES_SUCCESSFUL,
                    severity=ErrorSeverity.INFO,
                    message="All changes to file applied successfully",
                    details={"file": relative_path, "action": ActionType.DELETE_FILE.value, "change_count": 1},
                )
            )
        except Exception as e:
            errors.append(
                ApplydirError(
                    change=None,
                    error_type=ErrorType.FILE_SYSTEM,
                    severity=ErrorSeverity.ERROR,
                    message=f"File deletion failed: {str(e)}",
                    details={"file": relative_path},
                )
            )
        return errors

    def write_changes(self, file_path: Path, changed_lines: List[str], range: Optional[Dict]):
        """Writes changed lines to the file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if range:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().splitlines()
            content[range["start"]:range["end"]] = changed_lines
        else:
            content = changed_lines
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content) + "\n")