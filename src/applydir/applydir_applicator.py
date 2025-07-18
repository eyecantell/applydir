from typing import List, Optional
from pathlib import Path
from .applydir_changes import ApplyDirChanges
from .applydir_file_change import ApplyDirFileChange
from .applydir_matcher import ApplyDirMatcher
from .applydir_error import ApplyDirError, ErrorType

class ApplyDirApplicator:
    """Applies validated changes to files in temporary directory."""
    def __init__(self, base_dir: str, changes: ApplyDirChanges, matcher: ApplyDirMatcher):
        self.base_dir = base_dir
        self.changes = changes
        self.matcher = matcher
        self.logger = None  # Placeholder for logging

    def apply_changes(self) -> List[ApplyDirError]:
        """Applies all changes, writing to temporary files."""
        errors = []
        for file_dict in self.changes.files:
            for change in file_dict["changes"]:
                errors.extend(self.apply_single_change(change))
        return errors

    def apply_single_change(self, change: ApplyDirFileChange) -> List[ApplyDirError]:
        """Applies a single change to a temporary file."""
        temp_path = Path(".applydir_temp") / change.file
        if not change.original_lines:
            if temp_path.exists():
                return [ApplyDirError(
                    change=change,
                    error_type=ErrorType.FILE_SYSTEM,
                    message="File already exists",
                    details={}
                )]
            try:
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path.write_text("\n".join(change.changed_lines))
                return []
            except Exception as e:
                return [ApplyDirError(
                    change=change,
                    error_type=ErrorType.FILE_SYSTEM,
                    message=str(e),
                    details={"exception": type(e).__name__}
                )]

        try:
            file_path = Path(self.base_dir) / change.file
            file_content = file_path.read_text().splitlines()
            match_result = self.matcher.match(file_content, change)
            if isinstance(match_result, list):
                return match_result
            start, end = match_result["start_line"], match_result["end_line"]
            new_content = file_content[:start] + change.changed_lines + file_content[end+1:]
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text("\n".join(new_content))
            return []
        except Exception as e:
            return [ApplyDirError(
                change=change,
                error_type=ErrorType.FILE_SYSTEM,
                message=str(e),
                details={"exception": type(e).__name__}
            )]