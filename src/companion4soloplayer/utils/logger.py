"""
Logging setup for Companion4SoloPlayer.

Reads the ``[logging]`` table of the configuration file and configures the
root logger with a file handler and a console handler, using the standard
level names of the :mod:`logging` module.
"""

import logging
from enum import StrEnum
from pathlib import Path

from companion4soloplayer import __version__
from companion4soloplayer.build_info import BUILD_NUMBER
from companion4soloplayer.utils.config_manager import ConfigManager

# Namespace of the application loggers: logging.getLogger(APP_LOGGER_NAME)
APP_LOGGER_NAME = "companion4soloplayer"

# Record layout written to the file and to the console.
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Fallbacks used when the configuration omits a key (file written before the
# key existed) or holds an invalid value.
DEFAULT_LEVEL = "INFO"
DEFAULT_FILE = "./companion4soloplayer.log"
DEFAULT_MODE = "write"


class LogMode(StrEnum):
    """Opening mode of the log file (``mode`` key of the ``[logging]`` table).

    Supporting a new mode only requires adding a member here and a branch
    in :func:`_file_mode`: the configuration keeps storing a plain string,
    so existing configuration files remain valid.
    """

    WRITE = "write"
    """Create the file, overwriting its previous content."""

    APPEND = "append"
    """Add the new records at the end of the existing file."""


def _file_mode(mode: LogMode) -> str:
    """Translate a :class:`LogMode` into the ``mode`` argument of ``open``.

    Args:
        mode: Mode requested by the configuration.

    Returns:
        ``"w"`` for :attr:`LogMode.WRITE`, ``"a"`` for :attr:`LogMode.APPEND`.
    """
    return "a" if mode == LogMode.APPEND else "w"


def _resolve_level(value: object) -> int | None:
    """Resolve a standard logging level name (``DEBUG``, ``WARNING``, ...).

    Args:
        value: Raw value read from the configuration.

    Returns:
        The numeric level defined by :mod:`logging`, or ``None`` when the
        value is not a known level name.
    """
    if not isinstance(value, str):
        return None
    return logging.getLevelNamesMapping().get(value.strip().upper())


def _resolve_mode(value: object) -> LogMode | None:
    """Resolve a log file mode from the configuration.

    Args:
        value: Raw value read from the configuration.

    Returns:
        The matching :class:`LogMode`, or ``None`` when the value is unknown.
    """
    if isinstance(value, LogMode):
        return value
    if not isinstance(value, str):
        return None
    try:
        return LogMode(value.strip().lower())
    except ValueError:
        return None


def _clear_root_handlers() -> None:
    """Remove and close every handler attached to the root logger."""
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()


def setup_logging(config: ConfigManager) -> None:
    """Configure the root logger from the ``[logging]`` table of the config.

    Called at the very beginning of the application startup, before the Qt
    application is built, so that everything happening later can be logged.

    The call is idempotent: the handlers installed by a previous call are
    removed first, so repeated calls never stack duplicate handlers.

    Args:
        config: Configuration holding the ``enabled``, ``level``, ``file``
            and ``mode`` keys of the ``[logging]`` table.

    Notes:
        When ``enabled`` is false, every record is blocked through
        :func:`logging.disable` and no handler is installed.
    """
    settings = config.logging()

    enabled = bool(settings.get("enabled", True))
    level_name = settings.get("level", DEFAULT_LEVEL)
    log_file = settings.get("file", DEFAULT_FILE)
    mode_name = settings.get("mode", DEFAULT_MODE)

    # Never stack handlers: this call replaces the previous configuration.
    _clear_root_handlers()

    if not enabled:
        # Blocks the records whatever their level (see logging.disable).
        logging.disable(logging.CRITICAL)
        return

    # Reactivate the records blocked by a previous disabled configuration.
    logging.disable(logging.NOTSET)

    level = _resolve_level(level_name)
    mode = _resolve_mode(mode_name)
    # Invalid values fall back to the documented defaults.
    level_value = logging.INFO if level is None else level
    mode_value = LogMode(DEFAULT_MODE) if mode is None else mode

    # A relative path is resolved against the working directory.
    log_path = Path(log_file).expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [
        # The UTF-8 encoding belongs to the file handler: basicConfig only
        # accepts its own ``encoding`` argument when ``handlers`` is omitted.
        logging.FileHandler(log_path, mode=_file_mode(mode_value), encoding="utf-8"),
        logging.StreamHandler(),  # console
    ]
    logging.basicConfig(level=level_value, format=LOG_FORMAT, handlers=handlers)

    logger = logging.getLogger(APP_LOGGER_NAME)

    # Log application name and version, so that the log file can be identified even when it is
    logger.info("Application started")
    logger.info("Companion4SoloPlayer v%s build %s", __version__, BUILD_NUMBER)

    # Invalid values are reported once the handlers are in place, so the
    # warning reaches both the log file and the console.
    if level is None:
        logger.warning("Unknown log level %r in the configuration: using INFO", level_name)
    if mode is None:
        logger.warning(
            "Unknown log file mode %r in the configuration: using %s",
            mode_name,
            LogMode(DEFAULT_MODE).value,
        )

    logger.info("Logging initialized")
