"""
Tests for the ConfigManager.

Covers the default path resolution (``data/config/config.toml``), the
automatic creation of the file and of its parent folders, and the
save/load round-trip of the window settings.
"""

from pathlib import Path

from companion4soloplayer.utils.config_manager import (
    CONFIG_FILENAME,
    ConfigManager,
    default_config_path,
)

# tests/tests_utils/test_config_manager.py -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_default_config_path_follows_project_layout() -> None:
    """The default path is <project root>/data/config/config.toml."""
    path = default_config_path()

    assert path.name == CONFIG_FILENAME
    assert path.parent.name == "config"
    assert path.parent.parent.name == "data"
    assert path.parent.parent.parent == PROJECT_ROOT


def test_config_manager_creates_missing_file_and_parents(tmp_path: Path) -> None:
    """A missing configuration file is created, together with its folders."""
    path = tmp_path / "nested" / "config" / "config.toml"

    ConfigManager(path)

    assert path.is_file()


def test_window_settings_round_trip(tmp_path: Path) -> None:
    """Values written by one manager are read back by a new one."""
    path = tmp_path / "config.toml"

    config = ConfigManager(path)
    window = config.window()
    window["x"] = 42
    window["y"] = 84
    window["width"] = 1920
    window["height"] = 1080
    window["maximized"] = False
    config.save()

    reloaded = ConfigManager(path).window()
    assert (reloaded["x"], reloaded["y"]) == (42, 84)
    assert (reloaded["width"], reloaded["height"]) == (1920, 1080)
    assert reloaded["maximized"] is False


def test_reload_keeps_default_values_for_missing_keys(tmp_path: Path) -> None:
    """A partial file is merged with the default values on load."""
    path = tmp_path / "config.toml"
    path.write_text("[window]\nx = 10\ny = 20\n", encoding="utf-8")

    window = ConfigManager(path).window()

    assert (window["x"], window["y"]) == (10, 20)
    # Keys absent from the file keep their default value
    assert window["width"] == 1280
    assert window["height"] == 720
    assert window["maximized"] is True
