import logging
import sys
from pathlib import Path

from dynaconf import Dynaconf

if sys.version_info < (3, 9):
    import importlib_resources as resources
else:
    from importlib import resources

logger = logging.getLogger(__name__)


def load_config(tool_name: str, config_path: str = None) -> Dynaconf:
    settings_files = []
    if config_path:
        settings_files.append(config_path)
    else:
        settings_files.append(f".{tool_name}/config.yaml")
        settings_files.append(str(Path.home() / f".{tool_name}" / "config.yaml"))
        try:
            with resources.files(tool_name).joinpath("config.yaml") as bundled:
                settings_files.append(str(bundled))
        except Exception as e:
            logger.warning(f"Failed to load bundled config for {tool_name}: {e}")

    config = Dynaconf(
        settings_files=settings_files,
        envvar_prefix=tool_name.upper(),
        load_dotenv=True,
        merge_enabled=True,
        root_path=Path.cwd(),
        lowercase_read=True,
    )

    # Validate shell_type
    valid_shells = {"bash", "powershell", "cmd"}
    shell_type = config.get("COMMANDS", {}).get("SHELL_TYPE", "bash")
    if shell_type not in valid_shells:
        logger.warning(f"Invalid shell_type '{shell_type}' in config; defaulting to 'bash'")
        config.COMMANDS.SHELL_TYPE = "bash"

    # Validate auto_apply
    if not isinstance(config.get("APPLY_CHANGES", {}).get("AUTO_APPLY"), bool):
        logger.warning("Invalid or missing 'AUTO_APPLY' in config; defaulting to False")
        config.APPLY_CHANGES.AUTO_APPLY = False

    logger.debug(f"Attempted config files for {tool_name}: {settings_files}")
    return config
