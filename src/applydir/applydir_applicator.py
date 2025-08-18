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
        for file_entry in self.changes.files:
            file_path = self.base_dir / file_entry.file
            if file_entry.action == ActionType.DELETE_FILE:
                if not self.config.get("allow_file_deletion", True):
                    errors.append(
                        ApplydirError(
                            change=None,
                            error_type=ErrorType.PERMISSION_DENIED,
                            severity=ErrorSeverity.ERROR,
                            message="File deletion is disabled in configuration",
                            details={"file": file_entry.file},
                        )
                    )
                    continue
                errors.extend(self.delete_file(file_entry.file))
            elif file_entry.action in [ActionType.REPLACE_LINES, ActionType.CREATE_FILE]:
                for change in file_entry.changes:
                    # Ensure change is an ApplydirFileChange object
                    if isinstance(change, dict):
                        try:
                            change = ApplydirFileChange(**change, file=file_entry.file, base_dir=self.base_dir, action=file_entry.action)
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
                    errors.extend(self.apply_single_change(file_path, change, self.config))
        return errors

    def apply_single_change(self, file_path: Path, change: ApplydirFileChange, config: Dict) -> List[ApplydirError]:
        """Applies a single change to a file."""
        errors = []
        try:
            # Validate change first
            validation_errors = change.validate_change(config.get("validation", {}))
            errors.extend(validation_errors)
            if validation_errors:
                return errors

            # Use a new matcher with the provided config
            matcher = ApplydirMatcher(config=config)
            if change.action == ActionType.REPLACE_LINES:
                if not file_path.exists():
                    errors.append(
                        ApplydirError(
                            change=change,
                            error_type=ErrorType.FILE_PATH,
                            severity=ErrorSeverity.ERROR,
                            message="File does not exist for modification",
                            details={"file": str(change.file)},
                        )
                    )
                    return errors
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read().splitlines()
                match_result, match_errors = matcher.match(file_content, change)
                errors.extend(match_errors)
                if match_result:
                    self.write_changes(file_path, change.changed_lines, match_result)
            elif change.action == ActionType.CREATE_FILE:
                if file_path.exists():
                    errors.append(
                        ApplydirError(
                            change=change,
                            error_type=ErrorType.FILE_ALREADY_EXISTS,
                            severity=ErrorSeverity.ERROR,
                            message="File already exists for new file creation",
                            details={"file": str(change.file)},
                        )
                    )
                    return errors
                self.write_changes(file_path, change.changed_lines, None)
            elif change.action == ActionType.DELETE_FILE:
                if not config.get("allow_file_deletion", True):
                    errors.append(
                        ApplydirError(
                            change=change,
                            error_type=ErrorType.PERMISSION_DENIED,
                            severity=ErrorSeverity.ERROR,
                            message="File deletion is disabled in configuration",
                            details={"file": str(change.file)},
                        )
                    )
                    return errors
                errors.extend(self.delete_file(change.file))
        except Exception as e:
            errors.append(
                ApplydirError(
                    change=change,
                    error_type=ErrorType.FILE_SYSTEM,
                    severity=ErrorSeverity.ERROR,
                    message=f"File operation failed: {str(e)}",
                    details={"file": str(change.file)},
                )
            )
        return errors

    def delete_file(self, file_path: str) -> List[ApplydirError]:
        """Deletes a file."""
        errors = []
        actual_path = self.base_dir / file_path
        try:
            if not actual_path.exists():
                errors.append(
                    ApplydirError(
                        change=None,
                        error_type=ErrorType.FILE_PATH,
                        severity=ErrorSeverity.ERROR,
                        message="File does not exist for deletion",
                        details={"file": file_path},
                    )
                )
                return errors
            actual_path.unlink()
            self.logger.info(f"Deleted file: {file_path}")
        except Exception as e:
            errors.append(
                ApplydirError(
                    change=None,
                    error_type=ErrorType.FILE_SYSTEM,
                    severity=ErrorSeverity.ERROR,
                    message=f"File deletion failed: {str(e)}",
                    details={"file": file_path},
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