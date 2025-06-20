from pathlib import Path
from typing import Dict, Optional, List
import difflib
import logging

logger = logging.getLogger(__name__)

class FileForApplyDir:
    """Represents a file to be processed by applydir, with original and modified content."""
    def __init__(
        self,
        relative_path: str,
        base_dir: Path,
        modified_content: str,
        original_content: Optional[str] = None,
        uuid_mapping: Optional[Dict[str, str]] = None
    ):
        self.relative_path = relative_path
        self.base_dir = Path(base_dir)
        self.absolute_path = self.base_dir / relative_path
        self.modified_content = modified_content
        self.original_content = original_content  # None if new file
        self.uuid_mapping = uuid_mapping or {}
        self.is_new = original_content is None
        self.is_updated = False
        self.diff: Optional[List[str]] = None

    def compute_diff(self) -> None:
        """Compute unified diff between original and modified content."""
        if not self.is_new:
            self.diff = list(difflib.unified_diff(
                (self.original_content or "").splitlines(keepends=True),
                self.modified_content.splitlines(keepends=True),
                fromfile=f"Original: {self.relative_path}",
                tofile=f"Modified: {self.relative_path}"
            ))

    def has_changes(self) -> bool:
        """Check if the file is new or has modified content."""
        if self.is_new:
            return True
        return self.original_content != self.modified_content

    def restore_uuids(self) -> None:
        """Replace UUID placeholders with original UUIDs in modified content."""
        if not self.uuid_mapping:
            return
        for placeholder, original_uuid in self.uuid_mapping.items():
            self.modified_content = self.modified_content.replace(placeholder, original_uuid)

    def apply_changes(self, dry_run: bool = False, auto_apply: bool = False) -> bool:
        """Apply changes to the file system, with optional confirmation."""
        if not self.has_changes():
            logger.info(f"No changes for {self.relative_path}")
            return False
        if self.diff is None:
            self.compute_diff()
        print(f"\nProposed changes for {self.relative_path}:")
        if self.diff:
            print("".join(self.diff))
        else:
            preview = self.modified_content[:100] + ("..." if len(self.modified_content) > 100 else "")
            print(f"New file content:\n{preview}")
        
        logger.info(f"Proposed changes for {self.relative_path}")
        if dry_run:
            print(f"Dry run: Would {'create' if self.is_new else 'update'} {self.relative_path}")
            logger.info(f"Dry run: Would {'create' if self.is_new else 'update'} {self.relative_path}")
            return False
        if auto_apply:
            self._write_content()
            print(f"Automatically {'created' if self.is_new else 'updated'} {self.relative_path}")
            logger.info(f"Automatically {'created' if self.is_new else 'updated'} {self.relative_path}")
            return True
        confirm = input(f"{'Create' if self.is_new else 'Update'} {self.relative_path}? (y/n): ").lower()
        if confirm == "y":
            self._write_content()
            print(f"{'Created' if self.is_new else 'Updated'} {self.relative_path}")
            logger.info(f"{'Created' if self.is_new else 'Updated'} {self.relative_path}")
            return True
        print(f"Skipped {self.relative_path}")
        logger.info(f"Skipped {self.relative_path}")
        return False

    def _write_content(self) -> None:
        """Write modified content to the file system."""
        self.absolute_path.parent.mkdir(parents=True, exist_ok=True)
        self.absolute_path.write_text(self.modified_content, encoding="utf-8")
        self.is_updated = True