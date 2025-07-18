import argparse
import json
import logging
from pathlib import Path
from prepdir import configure_logging
from .applydir_changes import ApplydirChanges
from .applydir_matcher import ApplydirMatcher
from .applydir_applicator import ApplydirApplicator
from .applydir_error import ApplydirError

def main():
    """CLI entry point for applydir utility."""
    parser = argparse.ArgumentParser(description="Applydir: Apply LLM-generated changes to a codebase.")
    parser.add_argument("input_file", type=str, help="Path to JSON file containing changes")
    parser.add_argument("--base-dir", type=str, default=".", help="Base directory for file paths (default: current directory)")
    parser.add_argument("--no-temp-files", action="store_true", help="Write changes directly to actual files")
    parser.add_argument("--non-ascii-action", choices=["error", "warning", "ignore"], default=None, help="Action for non-ASCII characters")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO", help="Logging level")
    args = parser.parse_args()

    # Set up logging
    logger = logging.getLogger("applydir")
    configure_logging(logger, level=args.log_level)

    # Build config override
    config_override = {}
    if args.no_temp_files:
        config_override["use_temp_files"] = False
    if args.non_ascii_action:
        config_override["validation"] = {"non_ascii": {"default": args.non_ascii_action}}

    # Read and parse input JSON
    try:
        with open(args.input_file, "r") as f:
            changes_json = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read input file: {str(e)}")
        return 1

    # Initialize components
    try:
        changes = ApplydirChanges(files=changes_json)
        matcher = ApplydirMatcher(similarity_threshold=0.95)
        applicator = ApplydirApplicator(
            base_dir=args.base_dir,
            changes=changes,
            matcher=matcher,
            logger=logger,
            config_override=config_override
        )

        # Validate and apply changes
        errors = changes.validate_changes(base_dir=args.base_dir)
        if errors:
            for error in errors:
                logger.log(
                    logging.WARNING if error.severity == "warning" else logging.ERROR,
                    f"{error.message}: {error.details}"
                )
            return 1

        errors = applicator.apply_changes()
        if errors:
            for error in errors:
                logger.log(
                    logging.WARNING if error.severity == "warning" else logging.ERROR,
                    f"{error.message}: {error.details}"
                )
            return 1

        logger.info("Changes applied successfully")
        return 0
    except Exception as e:
        logger.error(f"Application failed: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())