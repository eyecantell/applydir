import logging
from .applydir_changes import ApplydirChanges
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity
from .applydir_file_change import ApplydirFileChange
from .applydir_matcher import ApplydirMatcher
from dynaconf import Dynaconf
from pathlib import Path
from prepdir import load_config
from typing import List, Optional, Dict


class ApplydirApplicator:
    """Applies validated changes to files."""

    def __init__(
        self,
        base_dir: str,
        changes: ApplydirChanges,
        matcher: ApplydirMatcher,
        logger: logging.Logger,
        config_override: Optional[Dict] = None,
    ):
        self.base_dir = Path(base_dir)
        self.changes = changes
        self.matcher = matcher
        self.logger = logger
        # Load default config and apply overrides
        default_config = load_config(namespace="applydir") or {
            "use_temp_files": True,
            "validation": {"non_ascii": {"default": "warning", "rules": []}},
            "allow_file_deletion": True,
        }
        self.config = Dynaconf(settings_files=[default_config], merge_enabled=True)
        if config_override:
            self.config.update(config_override, merge=True)
        self.temp_dir = self.base_dir / ".applydir_temp" if self.config.get("use_temp_files", True) else self.base_dir

    def apply_changes(self) -> List[ApplydirError]:
        """Applies all changes, writing to temporary or actual files."""
        errors = []
        if self.config.get("use_temp_files", True) and not self.temp_dir.exists():
            self.temp_dir.mkdir(parents=True)
        for file_entry in self.changes.files:
            if file_entry.action == "delete_file":
                if not self.config.get("allow_file_deletion", True):
                    errors.append(
                        ApplydirError(
                            change=None,
                            error_type=ErrorType.CONFIGURATION,
                            severity=ErrorSeverity.ERROR,
                            message="File deletion is disabled in configuration",
                            details={"file": file_entry.file},
                        )
                    )
                    continue
                errors.extend(self.delete_file(file_entry.file))
            elif file_entry.action in ["replace_lines", "create_file"]:
                for change in file_entry.changes:
                    errors.extend(self.apply_single_change(change))
        return errors

    def apply_single_change(self, change: ApplydirFileChange) -> List[ApplydirError]:
        """Applies a single change to a file."""
        errors = []
        file_path = (
            self.temp_dir / change.file if self.config.get("use_temp_files", True) else self.base_dir / change.file
        )
        try:
            if change.original_lines:  # replace_lines
                # Existing file: Match and replace
                if not (self.base_dir / change.file).exists():
                    errors.append(
                        ApplydirError(
                            change=change,
                            error_type=ErrorType.FILE_SYSTEM,
                            severity=ErrorSeverity.ERROR,
                            message="File does not exist for modification",
                            details={"file": change.file},
                        )
                    )
                    return errors
                with open(self.base_dir / change.file, "r") as f:
                    file_content = f.readlines()
                match_result = self.matcher.match(file_content, change)
                if isinstance(match_result, list):
                    errors.extend(match_result)
                    return errors
                self.write_changes(file_path, change.changed_lines, match_result)
            else:  # create_file
                # New file: Ensure path doesn’t exist
                if (self.base_dir / change.file).exists():
                    errors.append(
                        ApplydirError(
                            change=change,
                            error_type=ErrorType.FILE_SYSTEM,
                            severity=ErrorSeverity.ERROR,
                            message="File already exists for new file creation",
                            details={"file": change.file},
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
                    details={"file": change.file},
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
                        error_type=ErrorType.FILE_SYSTEM,
                        severity=ErrorSeverity.ERROR,
                        message="File does not exist for deletion",
                        details={"file": file_path},
                    )
                )
                return errors
            temp_path = self.temp_dir / file_path if self.config.get("use_temp_files", True) else actual_path
            if temp_path.exists():
                temp_path.unlink()
            else:
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
            with open(self.base_dir / file_path.relative_to(self.temp_dir), "r") as f:
                content = f.readlines()
            content[range["start"] : range["end"]] = changed_lines
            with open(file_path, "w") as f:
                f.writelines(content)
        else:
            with open(file_path, "w") as f:
                f.writelines(changed_lines)
