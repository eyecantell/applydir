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
                "similarity_metric": {"default": "levenshtein"},  # Updated default to levenshtein
                "use_fuzzy": {"default": True},
            },
        }
        self.config = Dynaconf(settings_files=[default_config], merge_enabled=True)
        if config_override:
            self.config.update(config_override, merge=True)
        self.matcher = matcher or ApplydirMatcher(config=self.config)

    def apply_changes(self) -> List[ApplydirError]:
        """Applies all changes directly to files in base_dir, reporting one success per file."""
        errors = []
        if not self.changes:
            return errors
        for file_entry in self.changes.file_entries:
            file_path = self.base_dir / file_entry.file
            change_count = 0
            actions = set()
            file_errors = []

            # Create ApplydirFileChange instances
            changes = []
            try:
                # To make sure we process entries without changes, set change_dict to a single None entry
                change_dicts = [None] if not file_entry.changes else file_entry.changes
                for change_dict in change_dicts:
                    try:
                        change = ApplydirFileChange.from_file_entry(file_path, file_entry.action, change_dict)
                        changes.append(change)
                    except ValueError as e:
                        file_errors.append(
                            ApplydirError(
                                change=None,
                                error_type=ErrorType.INVALID_CHANGE,
                                severity=ErrorSeverity.ERROR,
                                message=str(e),
                                details={"file": file_entry.file},
                            )
                        )
                    except Exception as e:
                        file_errors.append(
                            ApplydirError(
                                change=None,
                                error_type=ErrorType.INVALID_CHANGE,
                                severity=ErrorSeverity.ERROR,
                                message=f"Failed to create ApplydirFileChange: {str(e)}",
                                details={"file": file_entry.file},
                            )
                        )
            except Exception as e:
                file_errors.append(
                    ApplydirError(
                        change=None,
                        error_type=ErrorType.INVALID_CHANGE,
                        severity=ErrorSeverity.ERROR,
                        message=f"Unexpected error processing changes: {str(e)}",
                        details={"file": file_entry.file},
                    )
                )

            # Validate and process changes
            for change in changes:
                validation_errors = change.validate_change(self.config.as_dict())
                file_errors.extend(validation_errors)
                if any(e.severity == ErrorSeverity.ERROR for e in validation_errors):
                    continue
                try:
                    if change.action == ActionType.CREATE_FILE:
                        file_errors.extend(self.create_file(file_path, change))
                    elif change.action == ActionType.REPLACE_LINES:
                        file_errors.extend(self.replace_lines(file_path, change))
                    elif change.action == ActionType.DELETE_FILE:
                        file_errors.extend(self.delete_file(file_path, change))
                    if not any(e.severity == ErrorSeverity.ERROR for e in file_errors[-len(file_errors) :]):
                        change_count += 1
                        actions.add(change.action.value)
                except Exception as e:
                    file_errors.append(
                        ApplydirError(
                            change=change,
                            error_type=ErrorType.FILE_SYSTEM,
                            severity=ErrorSeverity.ERROR,
                            message=f"Failed to apply change: {str(e)}",
                            details={"file": str(file_path)},
                        )
                    )

            # Append file-level success if any changes were applied successfully
            errors.extend(file_errors)
            if change_count > 0:
                errors.append(
                    ApplydirError(
                        change=None,
                        error_type=ErrorType.FILE_CHANGES_SUCCESSFUL,
                        severity=ErrorSeverity.INFO,
                        message="All changes to file applied successfully",
                        details={"file": str(file_path), "actions": list(actions), "change_count": change_count},
                    )
                )
        return errors

    def create_file(self, file_path: Path, change: ApplydirFileChange) -> List[ApplydirError]:
        """Creates a new file with the specified changes."""
        errors = []
        try:
            # File system existence check
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

    def replace_lines(self, file_path: Path, change: ApplydirFileChange) -> List[ApplydirError]:
        """Replaces lines in an existing file."""
        errors = []
        try:
            # File system existence check
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

    def delete_file(self, file_path: Path, change: ApplydirFileChange) -> List[ApplydirError]:
        """Deletes a file."""
        errors = []
        if not self.config.get("allow_file_deletion", True):
            errors.append(
                ApplydirError(
                    change=change,
                    error_type=ErrorType.PERMISSION_DENIED,
                    severity=ErrorSeverity.ERROR,
                    message="File deletion is disabled in configuration",
                    details={"file": str(change.file_path)},
                )
            )
            return errors
        try:
            if not file_path.exists():
                errors.append(
                    ApplydirError(
                        change=change,
                        error_type=ErrorType.FILE_NOT_FOUND,
                        severity=ErrorSeverity.ERROR,
                        message="File does not exist for deletion",
                        details={"file": str(change.file_path)},
                    )
                )
                return errors
            file_path.unlink()
            self.logger.info(f"Deleted file: {change.file_path}")
        except Exception as e:
            errors.append(
                ApplydirError(
                    change=change,
                    error_type=ErrorType.FILE_SYSTEM,
                    severity=ErrorSeverity.ERROR,
                    message=f"File deletion failed: {str(e)}",
                    details={"file": str(change.file_path)},
                )
            )
        return errors

    def write_changes(self, file_path: Path, changed_lines: List[str], range: Optional[Dict]):
        """Writes changed lines to the file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if range:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().splitlines()
            content[range["start"] : range["end"]] = changed_lines
        else:
            content = changed_lines
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content) + "\n")
