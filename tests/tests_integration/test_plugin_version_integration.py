"""
Integration tests for plugin version loading.

These tests verify that the version declared in a plugin's
``datas/config.yaml`` is read end-to-end: from the YAML file on disk,
through the plugin loader, into the plugin configuration registry, and
finally reachable via :meth:PluginConfigRegistry.plugin_version.
"""

from pathlib import Path

import pytest

from companion4soloplayer.utils.plugin_config import PluginConfigRegistry
from companion4soloplayer.utils.plugin_loader import PluginLoader

PLUGINS_SRC = Path(__file__).resolve().parents[2] / "src" / "companion4soloplayer" / "plugins"


@pytest.fixture
def loader() -> PluginLoader:
    """Return a plugin loader pointing at the source plugins."""
    return PluginLoader(plugins_dir=str(PLUGINS_SRC))


def test_loaded_plugin_exposes_its_version(loader: PluginLoader) -> None:
    """The demo plugin version declared in config.yaml is reachable."""
    PluginConfigRegistry.reset()
    try:
        assert loader.load_plugin("demo") is not None
        assert PluginConfigRegistry.instance().plugin_version("demo") == "1.0.0"
    finally:
        PluginConfigRegistry.reset()


def test_loaded_plugin_version_via_default_name(loader: PluginLoader) -> None:
    """Calling plugin_version() without a name uses the first plugin."""
    PluginConfigRegistry.reset()
    try:
        assert loader.load_plugin("demo") is not None
        assert PluginConfigRegistry.instance().plugin_version() == "1.0.0"
    finally:
        PluginConfigRegistry.reset()


def test_plugin_without_config_section_reports_default_version() -> None:
    """A plugin configuration without a ``version`` section reports ``0.0.0``."""
    PluginConfigRegistry.reset()
    try:
        PluginConfigRegistry.instance().register("demo", {"dialog": []})
        assert PluginConfigRegistry.instance().plugin_version("demo") == "0.0.0"
    finally:
        PluginConfigRegistry.reset()
