"""
Tests for the window settings (geometry and maximized state) restored
from, and saved to, the configuration file.
"""

from pathlib import Path

from PySide6.QtCore import QRect
from pytestqt.qtbot import QtBot

from companion4soloplayer.app.application import application_config
from companion4soloplayer.ui.main_window import MainWindow
from companion4soloplayer.utils.config_manager import ConfigManager

# Geometry comfortably above the 1200x800 minimum size of the main window
SAVED_GEOMETRY = QRect(60, 70, 1300, 850)
NEW_GEOMETRY = QRect(100, 120, 1440, 900)


def _write_window_config(tmp_path: Path, *, maximized: bool = False) -> ConfigManager:
    """Write a configuration file holding the given window settings.

    Args:
        tmp_path: Directory of the configuration file.
        maximized: Value of the ``maximized`` flag.

    Returns:
        A fresh manager re-reading the file from disk, as a new application
        launch would do.
    """
    path = tmp_path / "config.toml"
    config = ConfigManager(path)
    window = config.window()
    window["x"] = SAVED_GEOMETRY.x()
    window["y"] = SAVED_GEOMETRY.y()
    window["width"] = SAVED_GEOMETRY.width()
    window["height"] = SAVED_GEOMETRY.height()
    window["maximized"] = maximized
    config.save()
    return ConfigManager(path)


def test_application_config_is_none_without_companion_application() -> None:
    """A plain QApplication (the one pytest-qt creates) carries no configuration."""
    assert application_config() is None


def test_window_geometry_restored_from_config(qtbot: QtBot, tmp_path: Path) -> None:
    """The window geometry stored in the configuration is applied on start."""
    config = _write_window_config(tmp_path)
    window = MainWindow(config=config)
    qtbot.addWidget(window)

    window.show()
    qtbot.waitExposed(window)

    assert window.geometry() == SAVED_GEOMETRY
    assert not window.isMaximized()


def test_window_geometry_saved_on_close(qtbot: QtBot, tmp_path: Path) -> None:
    """Closing the window writes its geometry back to the configuration."""
    config = _write_window_config(tmp_path)
    window = MainWindow(config=config)
    qtbot.addWidget(window)

    window.show()
    qtbot.waitExposed(window)
    window.setGeometry(NEW_GEOMETRY)
    window.close()

    saved = ConfigManager(tmp_path / "config.toml").window()
    assert (saved["x"], saved["y"]) == (NEW_GEOMETRY.x(), NEW_GEOMETRY.y())
    assert (saved["width"], saved["height"]) == (
        NEW_GEOMETRY.width(),
        NEW_GEOMETRY.height(),
    )
    assert saved["maximized"] is False


def test_window_restored_maximized_from_config(qtbot: QtBot, tmp_path: Path) -> None:
    """A maximized window in the configuration is shown maximized."""
    config = _write_window_config(tmp_path, maximized=True)
    window = MainWindow(config=config)
    qtbot.addWidget(window)

    window.show()
    qtbot.waitExposed(window)

    assert window.isMaximized()


def test_maximized_state_saved_on_close(qtbot: QtBot, tmp_path: Path) -> None:
    """Closing a maximized window keeps the flag and the normal geometry."""
    config = _write_window_config(tmp_path, maximized=True)
    window = MainWindow(config=config)
    qtbot.addWidget(window)

    window.show()
    qtbot.waitExposed(window)
    window.close()

    saved = ConfigManager(tmp_path / "config.toml").window()
    assert saved["maximized"] is True
    # The saved geometry must be the restored one, not the maximized rectangle
    assert (saved["width"], saved["height"]) == (
        SAVED_GEOMETRY.width(),
        SAVED_GEOMETRY.height(),
    )


def test_window_without_config_uses_qt_defaults(qtbot: QtBot) -> None:
    """Without any configuration, the window still shows with its default size."""
    window = MainWindow()
    qtbot.addWidget(window)

    window.show()
    qtbot.waitExposed(window)

    assert window.isVisible()
    # Default size is 1280x720, clamped up to the 1200x800 minimum height
    assert window.width() >= 1200
    assert window.height() >= 800
    assert not window.isMaximized()
