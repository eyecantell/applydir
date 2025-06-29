from pathlib import Path
from typing import List, Dict, Optional
import logging
import difflib
from prepdir.prepdir_output_file import PrepdirOutputFile
from prepdir.prepdir_file_entry import PrepdirFileEntry

logger = logging.getLogger(__name__)

class PrepdirApplicator:
    """Handles application of PrepdirOutputFile changes to the filesystem and related operations."""

    def __init__(self, highest_base_directory: Optional[str] = None, verbose: bool = False):
        """Initialize PrepdirApplicator with configuration.

        Args:
            highest_base_directory: Directory above which file paths must not resolve. If None, uses PrepdirOutputFile.metadata["base_directory"].
            verbose: If True, enable detailed logging.
        """
        self.highest_base_directory = highest_base_directory
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        if self.verbose:
            self.logger.setLevel(logging.DEBUG)

    def apply_changes(self, output: PrepdirOutputFile, dry_run: bool = False) -> List[str]:
        """Apply changes from a PrepdirOutputFile to the filesystem using PrepdirFileEntry.apply_changes.

        Args:
            output: PrepdirOutputFile containing files to apply.
            dry_run: If True, log changes without writing to disk.

        Returns:
            List[str]: List of relative paths for files that failed to apply.

        Raises:
            ValueError: If file paths or base_directory escape highest_base_directory.
        """
        highest_base = Path(
            self.highest_base_directory or output.metadata["base_directory"]
        ).resolve()
        failed_files = []

        # Verify base_directory
        base_dir = Path(output.metadata["base_directory"]).resolve()
        try:
            base_dir.relative_to(highest_base)
        except ValueError:
            logger.error(
                f"Base directory '{base_dir}' is outside highest base directory '{highest_base}'"
            )
            raise ValueError(
                f"Base directory '{base_dir}' is outside highest base directory '{highest_base}'"
            )

        for entry in output.files.values():
            abs_path = entry.absolute_path.resolve()
            try:
                abs_path.relative_to(highest_base)
            except ValueError:
                logger.error(
                    f"File path '{abs_path}' is outside highest base directory '{highest_base}'"
                )
                failed_files.append(entry.relative_path)
                continue

            if dry_run:
                content = entry.restore_uuids(uuid_mapping=output.uuid_mapping)
                self.logger.info(f"Dry run: Would write to {abs_path}:\n{content}")
                continue

            abs_path.parent.mkdir(parents=True, exist_ok=True)
            success = entry.apply_changes(uuid_mapping=output.uuid_mapping)
            if not success:
                failed_files.append(entry.relative_path)

        if failed_files:
            self.logger.warning(f"Failed to apply changes to {len(failed_files)} files: {failed_files}")
        return failed_files

    def get_diffs(self, output: PrepdirOutputFile) -> Dict[str, str]:
        """Generate diffs between PrepdirOutputFile content and existing files.

        Args:
            output: PrepdirOutputFile containing files to compare.

        Returns:
            Dict[str, str]: Dictionary mapping relative paths to unified diff strings (empty if no diff).
        """
        diffs = {}
        for entry in output.files.values():
            if entry.is_binary or entry.error:
                self.logger.info(
                    f"Skipping diff for {entry.relative_path}: {'binary' if entry.is_binary else 'error'}"
                )
                continue
            abs_path = entry.absolute_path
            restored_content = entry.restore_uuids(uuid_mapping=output.uuid_mapping).splitlines()
            existing_content = []
            if abs_path.exists():
                try:
                    existing_content = abs_path.read_text(encoding="utf-8").splitlines()
                except Exception as e:
                    self.logger.warning(f"Failed to read {abs_path} for diff: {str(e)}")
                    continue
            diff = list(
                difflib.unified_diff(
                    existing_content,
                    restored_content,
                    fromfile=str(abs_path),
                    tofile=f"prepdir:{entry.relative_path}",
                    lineterm="",
                )
            )
            if diff:
                diffs[entry.relative_path] = "\n".join(diff)
        return diffs

    def list_changed_files(self, output: PrepdirOutputFile) -> List[str]:
        """List files in PrepdirOutputFile that differ from existing files.

        Args:
            output: PrepdirOutputFile containing files to check.

        Returns:
            List[str]: List of relative paths for changed files.
        """
        changed_files = []
        for entry in output.files.values():
            if entry.is_binary or entry.error:
                continue
            abs_path = entry.absolute_path
            restored_content = entry.restore_uuids(uuid_mapping=output.uuid_mapping)
            if abs_path.exists():
                try:
                    existing_content = abs_path.read_text(encoding="utf-8")
                    if existing_content != restored_content:
                        changed_files.append(entry.relative_path)
                except Exception as e:
                    self.logger.warning(f"Failed to read {abs_path} for comparison: {str(e)}")
            else:
                # New files are considered changed
                changed_files.append(entry.relative_path)
        return changed_files

    def list_new_files(self, output: PrepdirOutputFile) -> List[str]:
        """List files in PrepdirOutputFile that do not exist on disk.

        Args:
            output: PrepdirOutputFile containing files to check.

        Returns:
            List[str]: List of relative paths for new files.
        """
        new_files = []
        for entry in output.files.values():
            if entry.is_binary or entry.error:
                continue
            if not entry.absolute_path.exists():
                new_files.append(entry.relative_path)
        return new_files