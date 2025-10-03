import argparse
import json
import logging
from pathlib import Path
from prepdir import configure_logging
from .applydir_changes import ApplydirChanges
from .applydir_matcher import ApplydirMatcher
from .applydir_applicator import ApplydirApplicator
from .applydir_error import ApplydirError, ErrorSeverity


def main():
    parser = argparse.ArgumentParser(description="Applydir: Apply LLM-generated changes to a codebase.")
    parser.add_argument("input_file", type=str, help="Path to JSON file containing changes")
    parser.add_argument(
        "--base-dir", type=str, default=".", help="Base directory for file paths (default: current directory)"
    )
    parser.add_argument("--no-allow-file-deletion", action="store_true", help="Disable file deletion")
    parser.add_argument(
        "--non-ascii-action",
        choices=["error", "warning", "ignore"],
        default=None,
        help="Action for non-ASCII characters",
    )
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO", help="Logging level"
    )
    args = parser.parse_args()

    logger = logging.getLogger("applydir")
    configure_logging(logger, level=args.log_level)

    config_override = {
        "allow_file_deletion": not args.no_allow_file_deletion,
    }
    if args.non_ascii_action:
        config_override["validation"] = {"non_ascii": {"default": args.non_ascii_action}}

    try:
        with open(args.input_file, "r") as f:
            changes_json = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read input file: {str(e)}")
        return 1

    try:
        if "file_entries" not in changes_json:
            logger.error("JSON must contain a non-empty array of file entries")
            return 1
        changes = ApplydirChanges(file_entries=changes_json["file_entries"])
        matcher = ApplydirMatcher(similarity_threshold=0.95)
        applicator = ApplydirApplicator(
            base_dir=args.base_dir, changes=changes, matcher=matcher, logger=logger, config_override=config_override
        )

        errors = changes.validate_changes(base_dir=args.base_dir, config=config_override)
        if errors:
            for error in errors:
                logger.log(
                    logging.WARNING if error.severity == "warning" else logging.ERROR,
                    f"{error.message}: {error.details}",
                )
            return 1

        errors = applicator.apply_changes()
        has_errors = False
        for error in errors:
            log_level = (
                logging.INFO
                if error.severity == ErrorSeverity.INFO
                else logging.WARNING
                if error.severity == ErrorSeverity.WARNING
                else logging.ERROR
            )
            logger.log(log_level, f"{error.message}: {error.details}")
            if error.severity in [ErrorSeverity.ERROR, ErrorSeverity.WARNING]:
                has_errors = True
        if has_errors:
            return 1

        logger.info("Changes applied successfully")
        return 0
    except Exception as e:
        logger.error(f"Application failed: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main())
