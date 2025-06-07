import argparse
import difflib
import logging
import os
import re
import sys
from typing import Dict, List, Tuple

from applydir.config import load_config


def setup_logging(config, handler: logging.Handler = None) -> None:
    """Configure logging based on config settings."""
    log_level = getattr(logging, config.LOGGING.LEVEL.upper(), logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(log_level)
    # Remove existing handlers to avoid duplicates
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    # Add provided handler or default to StreamHandler
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


def parse_prepped_dir(file_path: str) -> Tuple[Dict[str, str], List[str]]:
    """Parse a prepped_dir.txt file into a dictionary of file paths and contents, plus additional commands."""
    files: Dict[str, str] = {}
    commands: List[str] = []
    current_file = None
    current_content = []
    in_content = False
    in_commands = False

    # Regular expression for delimiter (minimum of one or more equals signs) followed by marker text
    file_delim_str = r"\s*=*\-*=+\s*"
    begin_file_pattern = re.compile(rf'^{file_delim_str}Begin File:\s*[\'"](.+?)[\'"]{file_delim_str}')
    end_file_pattern = re.compile(rf'^{file_delim_str}End File:\s*[\'"](.+?)[\'"]{file_delim_str}')
    begin_commands_pattern = re.compile(rf"^{file_delim_str}Begin Additional Commands{file_delim_str}")
    end_commands_pattern = re.compile(rf"^{file_delim_str}End Additional Commands{file_delim_str}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                # Match Begin File marker
                begin_file_match = begin_file_pattern.match(line)
                if begin_file_match:
                    # Save previous file's content if any
                    if current_file and current_content and in_content:
                        files[current_file] = "\n".join(current_content).strip()
                    # Start new file
                    current_file = begin_file_match.group(1)
                    current_content = []
                    in_content = True
                    in_commands = False
                    continue
                # Match End File marker
                end_file_match = end_file_pattern.match(line)
                if end_file_match:
                    end_file_name = end_file_match.group(1)
                    if current_file and current_content and in_content:
                        if end_file_name != current_file:
                            raise ValueError(
                                f"Mismatched End File marker: expected '{current_file}', got '{end_file_name}'. Please fix prepped_dir.txt and regenerate with Grok 3."
                            )
                        files[current_file] = "\n".join(current_content).strip()
                    current_file = None
                    current_content = []
                    in_content = False
                    continue
                # Match Begin Additional Commands marker
                if begin_commands_pattern.match(line):
                    if current_file and current_content and in_content:
                        files[current_file] = "\n".join(current_content).strip()
                    current_file = None
                    current_content = []
                    in_content = False
                    in_commands = True
                    continue
                # Match End Additional Commands marker
                if end_commands_pattern.match(line):
                    in_commands = False
                    continue
                # Skip header lines
                if line.startswith("File listing generated") or line.startswith("Base directory is"):
                    continue
                # Collect content or commands
                if in_content and not (
                    begin_file_pattern.match(line)
                    or end_file_pattern.match(line)
                    or begin_commands_pattern.match(line)
                    or end_commands_pattern.match(line)
                ):
                    current_content.append(line)
                elif in_commands:
                    commands.append(line.strip())
    except Exception as e:
        logging.error(f"Failed to parse {file_path}: {e}")
        raise

    # Handle the last file
    if current_file and current_content and in_content:
        files[current_file] = "\n".join(current_content).strip()

    return files, commands


def compare_files(original: Dict[str, str], modified: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Compare original and modified file contents, returning updates and new files."""
    updates: Dict[str, str] = {}
    new_files: Dict[str, str] = {}

    for file_path, content in modified.items():
        if file_path in original:
            if original[file_path] != content:
                updates[file_path] = content
        else:
            new_files[file_path] = content

    return updates, new_files


def show_diff(original: str, modified: str, file_path: str) -> None:
    """Display a unified diff between original and modified file contents."""
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile=f"Original: {file_path}",
        tofile=f"Modified: {file_path}",
    )
    print("".join(diff))


def apply_changes(
    updates: Dict[str, str],
    new_files: Dict[str, str],
    commands: List[str],
    base_dir: str,
    config,
    dry_run: bool = False,
) -> None:
    """Apply updates and new files to the codebase, and handle additional commands."""
    auto_apply = config.APPLY_CHANGES.AUTO_APPLY
    shell_type = config.COMMANDS.SHELL_TYPE

    # Handle updates
    for file_path, content in updates.items():
        full_path = os.path.join(base_dir, file_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                if original_content != content:
                    print(f"\nProposed changes for {file_path}:")
                    show_diff(original_content, content, file_path)
                    logging.info(f"Proposed changes for {file_path}")
                    if dry_run:
                        print(f"Dry run: Would update {file_path}")
                        logging.info(f"Dry run: Would update {file_path}")
                    elif auto_apply:
                        with open(full_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        print(f"Automatically updated {file_path}")
                        logging.info(f"Automatically updated {file_path}")
                    else:
                        confirm = input(f"Apply changes to {file_path}? (y/n): ").lower()
                        if confirm == "y":
                            with open(full_path, "w", encoding="utf-8") as f:
                                f.write(content)
                            print(f"Updated {file_path}")
                            logging.info(f"Updated {file_path}")
                        else:
                            print(f"Skipped {file_path}")
                            logging.info(f"Skipped {file_path}")
            except Exception as e:
                logging.error(f"Failed to process {file_path}: {e}")
        else:
            logging.warning(f"{file_path} does not exist in codebase; treating as new file")
            new_files[file_path] = content

    # Handle new files
    for file_path, content in new_files.items():
        full_path = os.path.join(base_dir, file_path)
        print(f"\nNew file proposed: {file_path}")
        print(f"Content (first 100 chars):\n{content[:100]}..." if len(content) > 100 else content)
        logging.info(f"New file proposed: {file_path}")
        if dry_run:
            print(f"Dry run: Would create {file_path}")
            logging.info(f"Dry run: Would create {file_path}")
        elif auto_apply:
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"Automatically created {file_path}")
                logging.info(f"Automatically created {file_path}")
            except Exception as e:
                logging.error(f"Failed to create {file_path}: {e}")
        else:
            confirm = input(f"Create {file_path}? (y/n): ").lower()
            if confirm == "y":
                try:
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"Created {file_path}")
                    logging.info(f"Created {file_path}")
                except Exception as e:
                    logging.error(f"Failed to create {file_path}: {e}")
            else:
                print(f"Skipped {file_path}")
                logging.info(f"Skipped {file_path}")

    # Handle additional commands
    if commands:
        print(f"\nProposed additional commands ({shell_type}):")
        for cmd in commands:
            print(f"  {cmd}")
        logging.info(f"Proposed additional commands ({shell_type}): {', '.join(commands)}")
        if dry_run:
            print("Dry run: Commands not executed")
            logging.info("Dry run: Commands not executed")
        elif auto_apply:
            print("Commands not executed automatically in auto_apply mode. Please run them manually.")
            logging.info("Commands not executed automatically in auto_apply mode")
        else:
            confirm = input(
                f"Review commands above (intended for {shell_type}). Run them manually or press Enter to skip: "
            )
            if confirm:
                print("Commands not executed automatically. Please run them manually.")
                logging.info("Commands not executed automatically")
            else:
                print("Skipped command execution")
                logging.info("Skipped command execution")


def main():
    parser = argparse.ArgumentParser(description="Apply changes from a modified prepped_dir.txt to the codebase.")
    parser.add_argument("prepped_dir", help="Path to the modified prepped_dir.txt file")
    parser.add_argument("--base-dir", default=".", help="Base directory of the codebase")
    parser.add_argument("--config", default=None, help="Path to configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Show changes and commands without applying them")
    args = parser.parse_args()

    # Load configuration
    config = load_config("applydir", args.config)
    setup_logging(config)

    # Validate base directory
    base_dir = os.path.abspath(args.base_dir)
    if not os.path.isdir(base_dir):
        logging.error(f"'{base_dir}' is not a directory")
        sys.exit(1)

    # Read original codebase
    original_files = {}
    for root, _, files in os.walk(base_dir):
        for file in files:
            file_path = os.path.relpath(os.path.join(root, file), base_dir)
            try:
                with open(os.path.join(base_dir, file_path), "r", encoding="utf-8") as f:
                    original_files[file_path] = f.read()
            except UnicodeDecodeError:
                logging.warning(f"Skipping binary file {file_path}")
                continue
            except Exception as e:
                logging.error(f"Failed to read {file_path}: {e}")
                continue

    # Parse modified prepped_dir.txt
    try:
        modified_files, commands = parse_prepped_dir(args.prepped_dir)
    except Exception as e:
        logging.error(f"Failed to parse '{args.prepped_dir}': {e}")
        sys.exit(1)

    # Compare and apply changes
    updates, new_files = compare_files(original_files, modified_files)
    if not updates and not new_files and not commands:
        logging.info("No changes or commands detected")
        return

    logging.info(
        f"Detected {len(updates)} modified files, {len(new_files)} new files, and {len(commands)} additional commands"
    )
    apply_changes(updates, new_files, commands, base_dir, config, args.dry_run)


if __name__ == "__main__":
    main()
