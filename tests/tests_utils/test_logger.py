"""
Tests for the logging setup (``setup_logging`` and the ``LogMode`` enum).

Covers the reading of the ``[logging]`` table of the configuration file:
enable/disable, standard level names, log file, write/append modes, and
the idempotence of repeated calls.
"""

import io
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from companion4soloplayer.utils.config_manager import ConfigManager
from companion4soloplayer.utils.logger import (
    APP_LOGGER_NAME,
    LogMode,
    _file_mode,
    _resolve_level,
    _resolve_mode,
    setup_logging,
)


def _reset_root_logger() -> None:
    """Restore the root logger to its pristine state."""
    logging.disable(logging.NOTSET)
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()


@pytest.fixture(autouse=True)
def clean_root_logger() -> Iterator[None]:
    """Give every test a pristine root logger, and leave it clean."""
    _reset_root_logger()
    yield
    _reset_root_logger()


def _log_file(tmp_path: Path) -> Path:
    """Return the log file used by the tests (always inside ``tmp_path``)."""
    return tmp_path / "app.log"


def _write_config(tmp_path: Path, **settings: object) -> ConfigManager:
    """Write a configuration file holding the given ``[logging]`` values.

    Args:
        tmp_path: Temporary directory holding the configuration file.
        settings: Values to store in the ``[logging]`` table.

    Returns:
        A manager re-reading the file, as a new application launch would.
    """
    path = tmp_path / "config.toml"
    config = ConfigManager(path)
    log = config.logging()
    log["file"] = str(_log_file(tmp_path))
    log.update(settings)
    config.save()
    return ConfigManager(path)


def _flush() -> None:
    """Flush every root handler so the file content can be asserted."""
    for handler in logging.getLogger().handlers:
        handler.flush()


def _file_handlers() -> list[logging.FileHandler]:
    """Return the file handlers currently attached to the root logger."""
    return [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, logging.FileHandler)
    ]


def test_setup_logging_applies_level_and_creates_file(tmp_path: Path) -> None:
    """The level and the log file of the configuration are applied."""
    setup_logging(_write_config(tmp_path, level="DEBUG"))

    assert logging.getLogger().level == logging.DEBUG
    assert [Path(handler.baseFilename) for handler in _file_handlers()] == [
        _log_file(tmp_path).resolve()
    ]


def test_records_are_written_to_the_file(tmp_path: Path) -> None:
    """DEBUG records reach the file when the configured level allows them."""
    setup_logging(_write_config(tmp_path, level="DEBUG"))

    logging.getLogger(APP_LOGGER_NAME).debug("hello from the tests")
    _flush()

    content = _log_file(tmp_path).read_text(encoding="utf-8")
    assert "[DEBUG]" in content
    assert "hello from the tests" in content
    assert "Logging initialized" in content


def test_write_mode_overwrites_the_existing_file(tmp_path: Path) -> None:
    """mode = "write" discards the content written by a previous run."""
    log_file = _log_file(tmp_path)
    log_file.write_text("content of the previous run\n", encoding="utf-8")

    setup_logging(_write_config(tmp_path, mode="write"))

    content = log_file.read_text(encoding="utf-8")
    # The previous content is gone, only the new records remain
    assert "content of the previous run" not in content
    assert "Logging initialized" in content


def test_append_mode_keeps_the_existing_content(tmp_path: Path) -> None:
    """mode = "append" keeps the previous content and adds new records."""
    log_file = _log_file(tmp_path)
    log_file.write_text("content of the previous run\n", encoding="utf-8")

    setup_logging(_write_config(tmp_path, mode="append"))
    logging.getLogger(APP_LOGGER_NAME).info("new record")
    _flush()

    content = log_file.read_text(encoding="utf-8")
    assert "content of the previous run" in content
    assert "new record" in content


def test_disabled_logging_installs_no_handler(tmp_path: Path) -> None:
    """enabled = false installs no file handler and blocks every record."""
    setup_logging(_write_config(tmp_path, enabled=False))

    assert _file_handlers() == []
    assert not _log_file(tmp_path).exists()

    # Even a critical record must not reach a handler.
    probe = io.StringIO()
    handler = logging.StreamHandler(probe)
    logging.getLogger().addHandler(handler)
    logging.getLogger(APP_LOGGER_NAME).critical("must be blocked")
    handler.flush()
    assert probe.getvalue() == ""


def test_setup_logging_reenables_a_previously_disabled_configuration(
    tmp_path: Path,
) -> None:
    """A disabled configuration does not prevent a later enabled one."""
    setup_logging(_write_config(tmp_path, enabled=False))
    setup_logging(_write_config(tmp_path, enabled=True, level="INFO"))

    logging.getLogger(APP_LOGGER_NAME).info("logging is back")
    _flush()

    assert "logging is back" in _log_file(tmp_path).read_text(encoding="utf-8")


def test_repeated_setup_does_not_stack_file_handlers(tmp_path: Path) -> None:
    """Calling setup_logging twice replaces the previous handlers."""
    setup_logging(_write_config(tmp_path, level="DEBUG"))
    setup_logging(_write_config(tmp_path, level="ERROR"))

    assert len(_file_handlers()) == 1
    assert logging.getLogger().level == logging.ERROR


def test_unknown_level_falls_back_to_info(tmp_path: Path) -> None:
    """A non-standard level name falls back to INFO and is reported."""
    setup_logging(_write_config(tmp_path, level="NOT_A_LEVEL"))
    _flush()

    assert logging.getLogger().level == logging.INFO
    assert "Unknown log level" in _log_file(tmp_path).read_text(encoding="utf-8")


def test_unknown_mode_falls_back_to_write(tmp_path: Path) -> None:
    """An unknown mode falls back to write and is reported."""
    log_file = _log_file(tmp_path)
    log_file.write_text("content of the previous run\n", encoding="utf-8")

    setup_logging(_write_config(tmp_path, mode="overwrite"))
    _flush()

    content = log_file.read_text(encoding="utf-8")
    assert "content of the previous run" not in content
    assert "Unknown log file mode" in content


def test_resolve_level_uses_standard_logging_names() -> None:
    """Levels follow the standard names of the logging module."""
    assert _resolve_level("DEBUG") == logging.DEBUG
    assert _resolve_level(" Warning ") == logging.WARNING
    assert _resolve_level("critical") == logging.CRITICAL
    assert _resolve_level("NOT_A_LEVEL") is None
    assert _resolve_level(10) is None


def test_resolve_mode_accepts_write_and_append() -> None:
    """The supported modes are converted to the enum, unknown ones rejected."""
    assert _resolve_mode("write") is LogMode.WRITE
    assert _resolve_mode("APPEND") is LogMode.APPEND
    assert _resolve_mode("overwrite") is None
    assert _resolve_mode(True) is None


def test_file_mode_matches_the_enum() -> None:
    """The enum translates to the open() mode expected by FileHandler."""
    assert _file_mode(LogMode.WRITE) == "w"
    assert _file_mode(LogMode.APPEND) == "a"
