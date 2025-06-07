import os
import sys
import argparse
from pathlib import Path
import difflib
from typing import Dict, Tuple, List
import yaml
import logging

def setup_logging(config: Dict) -> None:
    """Configure logging based on config settings."""
    log_level = getattr(logging, config.get("logging", {}).get("level", "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        # Validate config
        if not isinstance(config.get("apply_changes", {}).get("auto_apply"), bool):
            logging.warning("Invalid or missing 'auto_apply' in config; defaulting to False")
            config.setdefault("apply_changes", {})["auto_apply"] = False
        valid_shells = {"bash", "powershell", "cmd"}
        shell_type = config.get("commands", {}).get("shell_type", "bash")
        if shell_type not in valid_shells:
            logging.warning(f"Invalid shell_type '{shell_type}'; defaulting to 'bash'")
            config.setdefault("commands", {})["shell_type"] = "bash"
        return config
    except Exception as e:
        logging.error(f"Failed to load config from {config_path}: {e}")
        return {"apply_changes": {"auto_apply": False}, "commands": {"shell_type": "bash"}}

def parse_prepped_dir(file_path: str) -> Tuple[Dict[str, str], List[str]]:
    """Parse a prepped_dir.txt file into a dictionary of file paths and contents, plus additional commands."""
    files: Dict[str, str] = {}
    commands: List[str] = []
    current_file = None
    current_content = []
    in_content = False
    in_commands = False

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if line.startswith('=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= Begin File: '):
                    if current_file and current_content:
                        files[current_file] = '\n'.join(current_content).strip()
                        current_content = []
                    current_file = line.split("'", 2)[1]
                    in_content = True
                    in_commands = False
                    continue
                if line.startswith('=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= End File: '):
                    in_content = False
                    if current_file and current_content:
                        files[current_file] = '\n'.join(current_content).strip()
                        current_content = []
                    continue
                if line.startswith('=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= Begin Additional Commands =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-='):
                    in_content = False
                    in_commands = True
                    continue
                if line.startswith('=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= End Additional Commands =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-='):
                    in_commands = False
                    continue
                if line.startswith('File listing generated') or line.startswith('Base directory is'):
                    continue
                if in_content:
                    current_content.append(line)
                elif in_commands:
                    commands.append(line.strip())
    except Exception as e:
        logging.error(f"Failed to parse {file_path}: {e}")
        raise

    if current_file and current_content:
        files[current_file] = '\n'.join(current_content).strip()

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
        fromfile=f'Original: {file_path}',
        tofile=f'Modified: {file_path}',
    )
    logging.info(''.join(diff))

def apply_changes(updates: Dict[str, str], new_files: Dict[str, str], commands: List[str], base_dir: str, config: Dict, dry_run: bool = False) -> None:
    """Apply updates and new files to the codebase, and handle additional commands."""
    auto_apply = config.get("apply_changes", {}).get("auto_apply", False)
    shell_type = config.get("commands", {}).get("shell_type", "bash")

    # Handle updates
    for file_path, content in updates.items():
        full_path = os.path.join(base_dir, file_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                if original_content != content:
                    logging.info(f"Proposed changes for {file_path}:")
                    show_diff(original_content, content, file_path)
                    if dry_run:
                        logging.info(f"Dry run: Would update {file_path}")
                    elif auto_apply:
                        with open(full_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        logging.info(f"Automatically updated {file_path}")
                    else:
                        confirm = input(f"Apply changes to {file_path}? (y/n): ").lower()
                        if confirm == 'y':
                            with open(full_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            logging.info(f"Updated {file_path}")
                        else:
                            logging.info(f"Skipped {file_path}")
            except Exception as e:
                logging.error(f"Failed to process {file_path}: {e}")
        else:
            logging.warning(f"{file_path} does not exist in codebase; treating as new file")
            new_files[file_path] = content

    # Handle new files
    for file_path, content in new_files.items():
        full_path = os.path.join(base_dir, file_path)
        logging.info(f"New file proposed: {file_path}")
        logging.info(f"Content (first 100 chars):\n{content[:100]}..." if len(content) > 100 else content)
        if dry_run:
            logging.info(f"Dry run: Would create {file_path}")
        elif auto_apply:
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logging.info(f"Automatically created {file_path}")
            except Exception as e:
                logging.error(f"Failed to create {file_path}: {e}")
        else:
            confirm = input(f"Create {file_path}? (y/n): ").lower()
            if confirm == 'y':
                try:
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logging.info(f"Created {file_path}")
                except Exception as e:
                    logging.error(f"Failed to create {file_path}: {e}")
            else:
                logging.info(f"Skipped {file_path}")

    # Handle additional commands
    if commands:
        logging.info(f"Proposed additional commands ({shell_type}):")
        for cmd in commands:
            logging.info(f"  {cmd}")
        if dry_run:
            logging.info("Dry run: Commands not executed")
        elif auto_apply:
            logging.info("Commands not executed automatically in auto_apply mode. Please run them manually.")
        else:
            confirm = input(f"Review commands above (intended for {shell_type}). Run them manually or press Enter to skip: ")
            if confirm:
                logging.info("Commands not executed automatically. Please run them manually.")

def main():
    parser = argparse.ArgumentParser(description="Apply changes from a modified prepped_dir.txt to the codebase.")
    parser.add_argument("prepped_dir", help="Path to the modified prepped_dir.txt file")
    parser.add_argument("--base-dir", default=".", help="Base directory of the codebase")
    parser.add_argument("--config", default="src/applydir/config.yaml", help="Path to configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Show changes and commands without applying them")
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
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
                with open(os.path.join(base_dir, file_path), 'r', encoding='utf-8') as f:
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

    logging.info(f"Detected {len(updates)} modified files, {len(new_files)} new files, and {len(commands)} additional commands")
    apply_changes(updates, new_files, commands, base_dir, config, args.dry_run)

if __name__ == "__main__":
    main()