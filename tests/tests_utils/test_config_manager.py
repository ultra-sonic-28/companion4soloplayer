"""
Tests for the ConfigManager.

Covers the default path resolution (``data/config/config.toml``), the
automatic creation of the file and of its parent folders, and the
save/load round-trip of the window settings.
"""

from pathlib import Path

from companion4soloplayer.utils.config_manager import (
    CONFIG_FILENAME,
    DEFAULT_THEME,
    ConfigManager,
    TooltipCornerType,
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


def test_default_logging_settings(tmp_path: Path) -> None:
    """The [logging] section is created with its documented defaults."""
    config = ConfigManager(tmp_path / "config.toml")
    settings = config.logging()

    assert settings["enabled"] is True
    assert settings["level"] == "DEBUG"
    assert settings["file"] == "./companion4soloplayer.log"
    assert settings["mode"] == "write"


def test_default_appearance_settings(tmp_path: Path) -> None:
    """The [appearance] section is created with the default theme."""
    config = ConfigManager(tmp_path / "config.toml")
    settings = config.appearance()

    assert settings["theme"] == "light_blue.xml"
    assert settings["theme"] == DEFAULT_THEME


def test_created_file_contains_appearance_section(tmp_path: Path) -> None:
    """A brand new file documents the [appearance] table."""
    path = tmp_path / "config.toml"

    ConfigManager(path)

    content = path.read_text(encoding="utf-8")
    assert "[appearance]" in content
    assert 'theme = "light_blue.xml"' in content


def test_reload_keeps_default_theme_when_absent(tmp_path: Path) -> None:
    """A file without [appearance] still yields the default theme."""
    path = tmp_path / "config.toml"
    path.write_text("[window]\nx = 10\ny = 20\n", encoding="utf-8")

    settings = ConfigManager(path).appearance()

    assert settings["theme"] == "light_blue.xml"


def test_reload_keeps_default_theme_for_missing_key(tmp_path: Path) -> None:
    """An [appearance] table without ``theme`` keeps the default value."""
    path = tmp_path / "config.toml"
    path.write_text("[appearance]\nfont_size = 12\n", encoding="utf-8")

    settings = ConfigManager(path).appearance()

    assert settings["theme"] == "light_blue.xml"


def test_theme_round_trip(tmp_path: Path) -> None:
    """A theme written by one manager is read back by a new one."""
    path = tmp_path / "config.toml"

    config = ConfigManager(path)
    config.appearance()["theme"] = "dark_teal.xml"
    config.save()

    reloaded = ConfigManager(path).appearance()
    assert reloaded["theme"] == "dark_teal.xml"


def test_default_tooltip_settings(tmp_path: Path) -> None:
    """The [tooltip] section is created with its documented defaults."""
    config = ConfigManager(tmp_path / "config.toml")
    settings = config.tooltip()

    assert settings["background_color"] == "#ffffff"
    assert settings["text_color"] == "#000000"
    assert settings["border_color"] == "#3b3a98"
    assert settings["border_size"] == 2
    assert settings["border_radius"] == 5
    assert settings["corner_type"] == "round"


def test_created_file_contains_tooltip_section(tmp_path: Path) -> None:
    """A brand new file documents the [tooltip] table."""
    path = tmp_path / "config.toml"

    ConfigManager(path)

    content = path.read_text(encoding="utf-8")
    assert "[tooltip]" in content
    assert 'background_color = "#ffffff"' in content
    assert 'corner_type = "round"' in content


def test_reload_keeps_default_tooltip_settings(tmp_path: Path) -> None:
    """A file without [tooltip] still yields the default style values."""
    path = tmp_path / "config.toml"
    path.write_text("[window]\nx = 10\ny = 20\n", encoding="utf-8")

    settings = ConfigManager(path).tooltip()

    assert settings["background_color"] == "#ffffff"
    assert settings["border_size"] == 2
    assert settings["corner_type"] == "round"


def test_tooltip_corner_type_round_trip(tmp_path: Path) -> None:
    """A corner shape written by one manager is read back by a new one."""
    path = tmp_path / "config.toml"

    config = ConfigManager(path)
    config.tooltip()["corner_type"] = "square"
    config.save()

    reloaded = ConfigManager(path)
    assert reloaded.tooltip_corner_type() is TooltipCornerType.SQUARE


def test_tooltip_corner_type_defaults_to_round(tmp_path: Path) -> None:
    """A missing or invalid corner shape falls back on round."""
    path = tmp_path / "config.toml"

    # Missing key: the default table provides "round".
    config = ConfigManager(path)
    del config.tooltip()["corner_type"]
    assert config.tooltip_corner_type() is TooltipCornerType.ROUND

    # Invalid value: documented fallback.
    path.write_text('[tooltip]\ncorner_type = "octagonal"\n', encoding="utf-8")
    assert ConfigManager(path).tooltip_corner_type() is TooltipCornerType.ROUND


def test_tooltip_settings_round_trip(tmp_path: Path) -> None:
    """Tooltip values written by one manager are read back by a new one."""
    path = tmp_path / "config.toml"

    config = ConfigManager(path)
    settings = config.tooltip()
    settings["background_color"] = "#101010"
    settings["text_color"] = "#eeeeee"
    settings["border_color"] = "#ff0000"
    settings["border_size"] = 4
    settings["border_radius"] = 10
    config.save()

    reloaded = ConfigManager(path).tooltip()
    assert reloaded["background_color"] == "#101010"
    assert reloaded["text_color"] == "#eeeeee"
    assert reloaded["border_color"] == "#ff0000"
    assert reloaded["border_size"] == 4
    assert reloaded["border_radius"] == 10


def test_invalid_toml_file_is_preserved_as_invalid_copy(tmp_path: Path) -> None:
    """An unreadable file is kept aside before the defaults are written.

    ``corner_type = round`` (unquoted) is invalid TOML: loading such a
    file must not silently destroy it, since it only holds the user's
    own edits. The content is copied to ``config.toml.invalid`` and the
    configuration falls back on the defaults.
    """
    path = tmp_path / "config.toml"
    path.write_text(
        '[tooltip]\nbackground_color = "#ff0000"\ncorner_type = round\n',
        encoding="utf-8",
    )

    config = ConfigManager(path)

    # The application starts with the defaults...
    assert config.tooltip()["background_color"] == "#ffffff"
    assert config.tooltip_corner_type() is TooltipCornerType.ROUND
    # ... the file itself is rewritten valid...
    assert "corner_type" in path.read_text(encoding="utf-8")
    # ... and the original content is preserved next to it.
    invalid = tmp_path / "config.toml.invalid"
    assert invalid.is_file()
    assert "#ff0000" in invalid.read_text(encoding="utf-8")


def test_invalid_toml_file_is_preserved_only_on_parse_error(tmp_path: Path) -> None:
    """A valid file never produces an ``.invalid`` copy."""
    path = tmp_path / "config.toml"

    ConfigManager(path)

    assert not (tmp_path / "config.toml.invalid").exists()


def test_removed_file_keeps_in_memory_values(tmp_path: Path) -> None:
    """Reloading after an external removal keeps the current values."""
    path = tmp_path / "config.toml"
    config = ConfigManager(path)
    config.tooltip()["background_color"] = "#00ff00"
    path.unlink()

    config.load()

    assert config.tooltip()["background_color"] == "#00ff00"
    assert not path.exists()
