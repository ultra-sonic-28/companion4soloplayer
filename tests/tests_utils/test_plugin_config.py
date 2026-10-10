"""Unit tests for the plugin configuration support (``utils.plugin_config``).

Each plugin may ship an optional ``datas/config.yaml`` file declaring
how it integrates in the application (dialog sizes, ...). The file is
read when the plugin is loaded and published in the
:class:`~companion4soloplayer.utils.plugin_config.PluginConfigRegistry`,
a singleton reachable from anywhere in the application.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from companion4soloplayer.plugins.demo_plugin.data import DATA_DIR
from companion4soloplayer.utils.plugin_config import (
    CHARACTER_CREATION_DIALOG,
    DEFAULT_CREATION_DIALOG_HEIGHT,
    DEFAULT_CREATION_DIALOG_WIDTH,
    PluginConfigRegistry,
    dialog_settings,
    find_plugin_config,
    load_plugin_config,
)

#: Configuration document using the flat spelling: the dialog name maps
#: to null and the settings are its siblings.
FLAT_CONFIG = """
dialog:
  - character_creation_dialog:
    width: 1024
    height: 768
"""

#: Same settings, nested under the dialog name.
NESTED_CONFIG = """
dialog:
  - character_creation_dialog:
      width: 1024
      height: 768
"""


@pytest.fixture(autouse=True)
def isolated_registry() -> Iterator[None]:
    """Keep the singleton registry isolated between tests."""
    PluginConfigRegistry.reset()
    yield
    PluginConfigRegistry.reset()


# ----------------------------------------------------------------------
# File discovery and loading
# ----------------------------------------------------------------------


def test_find_plugin_config_prefers_the_datas_directory(tmp_path: Path) -> None:
    """``datas/config.yaml`` wins over the flat ``config.yaml`` fallback."""
    (tmp_path / "datas").mkdir()
    canonical = tmp_path / "datas" / "config.yaml"
    canonical.write_text("dialog: []\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("dialog: []\n", encoding="utf-8")

    assert find_plugin_config([tmp_path]) == canonical


def test_find_plugin_config_accepts_the_flat_fallback(tmp_path: Path) -> None:
    """A ``config.yaml`` next to the plugin code is also recognized."""
    fallback = tmp_path / "config.yaml"
    fallback.write_text("dialog: []\n", encoding="utf-8")

    assert find_plugin_config([tmp_path]) == fallback


def test_find_plugin_config_probes_directories_in_order(tmp_path: Path) -> None:
    """The first directory holding a file wins."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    expected = second / "datas" / "config.yaml"
    expected.parent.mkdir()
    expected.write_text("dialog: []\n", encoding="utf-8")

    assert find_plugin_config([first, second]) == expected


def test_find_plugin_config_returns_none_when_missing(tmp_path: Path) -> None:
    assert find_plugin_config([tmp_path]) is None


def test_load_plugin_config_parses_the_document(tmp_path: Path) -> None:
    """The requested flat spelling parses into settings per dialog."""
    (tmp_path / "datas").mkdir()
    (tmp_path / "datas" / "config.yaml").write_text(FLAT_CONFIG, encoding="utf-8")

    config = load_plugin_config([tmp_path])

    assert config == {"dialog": [{"character_creation_dialog": None, "width": 1024, "height": 768}]}


def test_load_plugin_config_is_empty_when_missing(tmp_path: Path) -> None:
    assert load_plugin_config([tmp_path]) == {}


def test_load_plugin_config_tolerates_invalid_yaml(tmp_path: Path) -> None:
    """A broken file never breaks the plugin: defaults still apply."""
    (tmp_path / "datas").mkdir()
    (tmp_path / "datas" / "config.yaml").write_text("{\n", encoding="utf-8")

    assert load_plugin_config([tmp_path]) == {}


def test_load_plugin_config_ignores_non_mapping_documents(tmp_path: Path) -> None:
    """Only mappings are accepted as plugin configurations."""
    (tmp_path / "datas").mkdir()
    (tmp_path / "datas" / "config.yaml").write_text("- one\n- two\n", encoding="utf-8")

    assert load_plugin_config([tmp_path]) == {}


def test_load_plugin_config_ignores_empty_documents(tmp_path: Path) -> None:
    (tmp_path / "datas").mkdir()
    (tmp_path / "datas" / "config.yaml").write_text("# only a comment\n", encoding="utf-8")

    assert load_plugin_config([tmp_path]) == {}


def test_demo_plugin_ships_a_configuration_file() -> None:
    """The demo plugin declares its dialog size in ``datas/config.yaml``."""
    config = load_plugin_config([DATA_DIR])
    assert dialog_settings(config, CHARACTER_CREATION_DIALOG) == {"width": 860, "height": 800}


# ----------------------------------------------------------------------
# Dialog settings
# ----------------------------------------------------------------------


def test_dialog_settings_reads_the_flat_spelling() -> None:
    """Settings written next to the dialog name are collected."""
    config = {"dialog": [{"character_creation_dialog": None, "width": 1024, "height": 768}]}

    assert dialog_settings(config, CHARACTER_CREATION_DIALOG) == {
        "width": 1024,
        "height": 768,
    }


def test_dialog_settings_reads_the_nested_spelling() -> None:
    """Settings nested under the dialog name are collected too."""
    config = {"dialog": [{"character_creation_dialog": {"width": 1024, "height": 768}}]}

    assert dialog_settings(config, CHARACTER_CREATION_DIALOG) == {
        "width": 1024,
        "height": 768,
    }


def test_dialog_settings_skips_unrelated_and_malformed_entries() -> None:
    """Only the first matching entry of a well-formed list is used."""
    config = {
        "dialog": [
            42,
            "character_creation_dialog",
            {"other_dialog": {"width": 1}},
            {"character_creation_dialog": {"width": 900, "height": 700}},
        ]
    }

    assert dialog_settings(config, CHARACTER_CREATION_DIALOG) == {
        "width": 900,
        "height": 700,
    }


def test_dialog_settings_is_empty_without_a_dialog_section() -> None:
    assert dialog_settings({}, CHARACTER_CREATION_DIALOG) == {}
    assert dialog_settings({"dialog": "nope"}, CHARACTER_CREATION_DIALOG) == {}


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------


def test_registry_is_a_singleton() -> None:
    """The registry is shared by the whole application."""
    assert PluginConfigRegistry.instance() is PluginConfigRegistry.instance()


def test_register_and_read_a_configuration() -> None:
    registry = PluginConfigRegistry.instance()
    registry.register("demo", {"dialog": []})

    assert registry.plugin_names() == ("demo",)
    assert registry.config("demo") == {"dialog": []}


def test_config_of_an_unknown_plugin_is_empty() -> None:
    assert PluginConfigRegistry.instance().config("nope") == {}


def test_config_defaults_to_the_first_registered_plugin() -> None:
    """Without a name, the first registered plugin is consulted."""
    registry = PluginConfigRegistry.instance()
    registry.register("first", {"source": "first"})
    registry.register("second", {"source": "second"})

    assert registry.config() == {"source": "first"}
    assert registry.config("second") == {"source": "second"}


def test_unregister_drops_the_configuration() -> None:
    registry = PluginConfigRegistry.instance()
    registry.register("demo")
    registry.unregister("demo")

    assert registry.plugin_names() == ()


def test_register_replaces_a_previous_configuration() -> None:
    registry = PluginConfigRegistry.instance()
    registry.register("demo", {"width": 1})
    registry.register("demo", {"width": 2})

    assert registry.config("demo") == {"width": 2}


def test_character_creation_dialog_size_uses_the_plugin_values() -> None:
    """The flat spelling of the demo configuration drives the size."""
    registry = PluginConfigRegistry.instance()
    registry.register(
        "demo", {"dialog": [{"character_creation_dialog": None, "width": 1024, "height": 768}]}
    )

    assert registry.character_creation_dialog_size("demo") == (1024, 768)
    # No name: the first registered plugin applies.
    assert registry.character_creation_dialog_size() == (1024, 768)


def test_character_creation_dialog_size_falls_back_on_defaults() -> None:
    """No registry, unknown plugin or no settings -> 860 x 800."""
    registry = PluginConfigRegistry.instance()

    assert registry.character_creation_dialog_size() == (
        DEFAULT_CREATION_DIALOG_WIDTH,
        DEFAULT_CREATION_DIALOG_HEIGHT,
    )
    registry.register("demo", {})
    assert registry.character_creation_dialog_size("demo") == (
        DEFAULT_CREATION_DIALOG_WIDTH,
        DEFAULT_CREATION_DIALOG_HEIGHT,
    )
    assert registry.character_creation_dialog_size("unknown") == (
        DEFAULT_CREATION_DIALOG_WIDTH,
        DEFAULT_CREATION_DIALOG_HEIGHT,
    )


def test_character_creation_dialog_size_ignores_invalid_values() -> None:
    """Invalid width/height entries fall back on the default, one by one."""
    registry = PluginConfigRegistry.instance()
    registry.register(
        "demo",
        {"dialog": [{"character_creation_dialog": None, "width": "wide", "height": -3}]},
    )

    assert registry.character_creation_dialog_size("demo") == (
        DEFAULT_CREATION_DIALOG_WIDTH,
        DEFAULT_CREATION_DIALOG_HEIGHT,
    )
