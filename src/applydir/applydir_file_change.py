from typing import List, Optional
from pydantic import BaseModel, validator
import pylint.lint
import io
from .applydir_error import ApplyDirError, ErrorType

class ApplyDirFileChange(BaseModel):
    """Represents a single change to a file, including path and line changes."""
    file: str
    original_lines: List[str]
    changed_lines: List[str]

    @validator("file")
    def validate_file_path(cls, v: str) -> str:
        if not v or v.startswith("/"):
            raise ValueError("File path must be non-empty and relative")
        return v

    def validate_change(self) -> List[ApplyDirError]:
        """Validates syntax and additions for the change."""
        errors = []
        if not self.original_lines:
            if not self.changed_lines:
                errors.append(ApplyDirError(
                    change=self,
                    error_type=ErrorType.EMPTY_CHANGED_LINES,
                    message="changed_lines cannot be empty for new files",
                    details={}
                ))
            return errors

        # Syntax check for Python files (simplified)
        if self.file.endswith(".py"):
            try:
                pylint_output = io.StringIO()
                pylint.lint.Run(["--disable=all", "--enable=syntax-error", "-"], reporter=pylint.lint.Reporter(pylint_output))
                if pylint_output.getvalue():
                    errors.append(ApplyDirError(
                        change=self,
                        error_type=ErrorType.SYNTAX,
                        message="Invalid Python syntax in changed_lines",
                        details={"pylint_output": pylint_output.getvalue()}
                    ))
            except Exception as e:
                errors.append(ApplyDirError(
                    change=self,
                    error_type=ErrorType.SYNTAX,
                    message="Failed to validate Python syntax",
                    details={"exception": str(e)}
                ))

        # Addition check: changed_lines must start with original_lines
        if len(self.changed_lines) >= len(self.original_lines):
            if self.changed_lines[:len(self.original_lines)] != self.original_lines:
                errors.append(ApplyDirError(
                    change=self,
                    error_type=ErrorType.ADDITION_MISMATCH,
                    message="changed_lines does not start with original_lines",
                    details={"expected_prefix": self.original_lines}
                ))

        return errors