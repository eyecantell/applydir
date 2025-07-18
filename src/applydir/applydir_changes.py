from typing import List, Dict, Union
from pydantic import BaseModel, validator
from .applydir_file_change import ApplyDirFileChange
from .applydir_error import ApplyDirError, ErrorType

class ApplyDirChanges(BaseModel):
    """Parses and validates JSON changes for multiple files."""
    files: List[Dict[str, Union[str, List[ApplyDirFileChange]]]]

    @validator("files")
    def validate_files(cls, v: List[Dict]) -> List[Dict]:
        errors = []
        for file_dict in v:
            if "file" not in file_dict or "changes" not in file_dict:
                errors.append(ApplyDirError(
                    change=None,
                    error_type=ErrorType.JSON_STRUCTURE,
                    message="File object missing 'file' or 'changes' key",
                    details={"file_dict": file_dict}
                ))
            else:
                if not file_dict["changes"]:
                    errors.append(ApplyDirError(
                        change=None,
                        error_type=ErrorType.CHANGES_EMPTY,
                        message=f"Empty changes for file {file_dict['file']}",
                        details={"file": file_dict["file"]}
                    ))
                for change in file_dict["changes"]:
                    if not isinstance(change, ApplyDirFileChange):
                        change = ApplyDirFileChange(file=file_dict["file"], **change)
                        file_dict["changes"][file_dict["changes"].index(change)] = change
                    errors.extend(change.validate_change())
        if errors:
            raise ValueError(errors)
        return v

    @classmethod
    def from_json(cls, json_data: List[Dict]) -> "ApplyDirChanges":
        """Creates ApplyDirChanges from JSON, injecting file into changes."""
        if not isinstance(json_data, list):
            raise ValueError([ApplyDirError(
                change=None,
                error_type=ErrorType.JSON_STRUCTURE,
                message="JSON must be an array",
                details={}
            )])
        return cls(files=[
            {
                "file": f["file"],
                "changes": [ApplyDirFileChange(file=f["file"], **c) for c in f["changes"]]
            } for f in json_data
        ])