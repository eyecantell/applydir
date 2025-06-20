import argparse
import logging
import os
import sys
import subprocess
from typing import List, Tuple, Dict, Optional
from pathlib import Path
import fnmatch
from prepdir.core import validate_output_file
from applydir.config import load_config
from .file_for_applydir import FileForApplyDir

logger = logging.getLogger(__name__)

def setup_logging(config, handler: logging.Handler = None) -> None:
    """Configure logging based on config settings."""
    log_level = getattr(logging, config.LOGGING.LEVEL.upper(), logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(log_level)
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def parse_prepped_dir(file_path: str, base_dir: Path, uuid_mapping: Dict[str, str]) -> Tuple[List[FileForApplyDir], List[str]]:
    """Parse prepped_dir.txt using prepdir's validate_output_file."""
    validation_result = validate_output_file(file_path)
    if not validation_result["is_valid"]:
        logger.error(f"Invalid prepped_dir.txt: {validation_result['errors']}")
        raise ValueError(f"Invalid prepped_dir.txt: {validation_result['errors']}")

    files = []
    for rel_path, modified_content in validation_result["files"].items():
        absolute_path = base_dir / rel_path
        original_content = None
        if absolute_path.exists():
            try:
                original_content = absolute_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                logger.warning(f"Skipping binary file {rel_path}")
                continue
            except Exception as e:
                logger.error(f"Failed to read {rel_path}: {e}")
                continue
        file_obj = FileForApplyDir(rel_path, base_dir, modified_content, original_content, uuid_mapping)
        file_obj.restore_uuids()  # Restore UUIDs immediately after initialization
        files.append(file_obj)

    # Commands are not directly parsed by validate_output_file; assume they follow files
    commands = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        in_commands = False
        for line in lines:
            line = line.rstrip("\n")
            if line.startswith("=-=-=-= Begin Additional Commands"):
                in_commands = True
                continue
            if line.startswith("=-=-=-= End Additional Commands"):
                in_commands = False
                continue
            if in_commands and line.strip():
                commands.append(line.strip())
    except Exception as e:
        logger.error(f"Failed to parse commands from {file_path}: {e}")

    return files, commands

def execute_commands(commands: List[str], shell_type: str, dry_run: bool = False) -> None:
    """Execute additional commands using the specified shell type."""
    if not commands:
        return
    logger.info(f"Executing commands ({shell_type}): {', '.join(commands)}")
    print(f"\nExecuting commands ({shell_type}):")
    for cmd in commands:
        print(f"  {cmd}")
        if dry_run:
            print(f"Dry run: Would execute: {cmd}")
            logger.info(f"Dry run: Would execute: {cmd}")
        else:
            try:
                shell = shell_type == "powershell" and "powershell" or shell_type == "cmd" and "cmd.exe /c" or "bash -c"
                subprocess.run(f"{shell} {cmd}", shell=True, check=True, text=True)
                print(f"Executed: {cmd}")
                logger.info(f"Executed: {cmd}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to execute command '{cmd}': {e}")
                print(f"Failed to execute command '{cmd}': {e}")

def apply_changes(
    files: List[FileForApplyDir],
    commands: List[str],
    config,
    dry_run: bool = False,
    selected_files: Optional[List[str]] = None,
    execute_commands_flag: bool = False
) -> None:
    """Apply changes to selected files and execute commands if requested."""
    auto_apply = config.APPLY_CHANGES.AUTO_APPLY
    shell_type = config.COMMANDS.SHELL_TYPE

    # Filter files based on selected_files (if provided)
    if selected_files and "-all" not in selected_files:
        files = [
            f for f in files
            if f.relative_path in selected_files or any(fnmatch.fnmatch(f.relative_path, p) for p in selected_files)
        ]

    # Apply changes to files
    for file_obj in files:
        if file_obj.has_changes():
            file_obj.apply_changes(dry_run, auto_apply)

    # Handle commands
    if commands and execute_commands_flag:
        execute_commands(commands, shell_type, dry_run)

def main():
    parser = argparse.ArgumentParser(description="Apply changes from a modified prepped_dir.txt to the codebase.")
    parser.add_argument("prepped_dir", help="Path to the modified prepped_dir.txt file")
    parser.add_argument("--base-dir", default=".", help="Base directory of the codebase")
    parser.add_argument("--config", default=None, help="Path to configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying them")
    parser.add_argument("--files", default="-all", help="Comma-separated list of files/patterns to apply (default: -all)")
    parser.add_argument("--uuid-mapping", default="{}", help="JSON string with UUID mappings from prepdir")
    parser.add_argument("--execute-commands", action="store_true", help="Execute additional commands")
    args = parser.parse_args()

    # Load configuration
    config = load_config("applydir", args.config)
    setup_logging(config)

    # Validate base directory
    base_dir = Path(os.path.abspath(args.base_dir))
    if not base_dir.is_dir():
        logger.error(f"'{base_dir}' is not a directory")
        sys.exit(1)

    # Parse UUID mapping
    import json
    try:
        uuid_mapping = json.loads(args.uuid_mapping)
    except json.JSONDecodeError:
        logger.error(f"Invalid UUID mapping: {args.uuid_mapping}")
        sys.exit(1)

    # Parse prepped_dir.txt
    try:
        files, commands = parse_prepped_dir(args.prepped_dir, base_dir, uuid_mapping)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    # Apply changes
    selected_files = args.files.split(",") if args.files else ["-all"]
    apply_changes(files, commands, config, args.dry_run, selected_files, args.execute_commands)

if __name__ == "__main__":
    main()