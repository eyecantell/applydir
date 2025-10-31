from typing import List, Optional
from .applydir_error import ApplydirError
from dataclasses import dataclass

@dataclass
class ApplydirResult:
    errors: List[ApplydirError]
    commit_message: Optional[str]
    success: bool