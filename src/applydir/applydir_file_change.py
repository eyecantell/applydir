from typing import List, Optional
from pydantic import BaseModel, field_validator
import re
from pathlib import Path
from prepdir import load_config
from .applydir_error import ApplydirError, ErrorType, ErrorSeverity

class ApplydirFileChange(BaseModel):
    """Represents a single change to a file, including path and line changes."""
    file: str
    original_lines: List[str]
    changed_lines: List[str]

    @field_validator("file")
    @classmethod
    def validate_file_path(cls, v: str, values: dict) -> str:
        """Validates that the file path is resolvable within the project base_dir."""
        if not v:
            raise ValueError("File path must be non-empty")
        # base_dir may be provided via Pydantic's values (e.g., from ApplydirApplicator)
        base_dir = values.get("base_dir", Path.cwd())
        try:
            resolved_path = (base_dir / Path(v)).resolve()
            if not str(resolved_path).startswith(str(base_dir.resolve())):
                raise ValueError("File path is outside project directory")
        except Exception as e:
            raise ValueError(f"Invalid file path: {str(e)}")
        return v

    def validate_change(self) -> List[ApplydirError]:
        """Validates syntax for the change."""
        errors = []
        if not self.original_lines:
            if not self.changed_lines:
                errors.append(ApplydirError(
                    change=self,
                    error_type=ErrorType.EMPTY_CHANGED_LINES,
                    message="changed_lines cannot be empty for new files",
                    details={},
                    severity=ErrorSeverity.ERROR
                ))
            return errors

        # Load non-ASCII validation rules from applydir_config.yaml
        config = load_config(namespace="applydir") or {"validation": {"non_ascii": {"default": "warning", "rules": []}}}
        non_ascii_action = config["validation"]["non_ascii"]["default"]
        for rule in config["validation"]["non_ascii"]["rules"]:
            if any(self.file.endswith(ext) for ext in rule.get("extensions", [])):
                non_ascii_action = rule["action"]
                break

        # Syntax check: Detect non-ASCII characters in changed_lines
        non_ascii_pattern = re.compile(r'[^\x00-\x7F]')
        for line in self.changed_lines:
            if non_ascii_pattern.search(line):
                severity = (
                    ErrorSeverity.ERROR if non_ascii_action == "error"
                    else ErrorSeverity.WARNING if non_ascii_action == "warning"
                    else None
                )
                if severity:
                    errors.append(ApplydirError(
                        change=self,
                        error_type=ErrorType.SYNTAX,
                        message="Non-ASCII characters found in changed_lines",
                        details={"line": line, "line_number": self.changed_lines.index(line) + 1},
                        severity=severity
                    ))

        return errors