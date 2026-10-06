"""
Plugin loader module.
Handles dynamic loading of game plugins.

Two operating modes are supported:

- Development: plugins live as regular Python packages
  (``src/companion4soloplayer/plugins/<name>_plugin/``) and are imported
  through the standard import machinery.
- Frozen application (PyInstaller one-dir build): each plugin ships as a
  compiled extension module (``<name>.pyd``) located in the
  ``plugins/`` folder next to the application ``_internal`` data, and is
  loaded dynamically through importlib.

Both kinds of plugin expose a ``Plugin`` class compatible with the
:class:`GamePlugin` protocol. Plugin data (manifest, classes, rules...)
ships as commented YAML files (``plugin.yaml``, ``rules.yaml``, ...)
loaded through :mod:`companion4soloplayer.utils.yaml_loader`, and rule
elements are bound to Python classes through the hybrid
:class:`companion4soloplayer.core.rule_engine.RuleEngine`.
"""

import importlib
import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from typing import Any, Protocol, cast

from companion4soloplayer.core.rule_engine import RuleEngine


def _default_plugins_dir() -> Path:
    """Return the directory holding the plugins.

    In a frozen (PyInstaller) application the compiled plugin libraries
    (``*.pyd``) are collected into ``<sys._MEIPASS>/plugins``. In a regular
    (development) install they are the Python packages stored in
    ``companion4soloplayer/plugins``.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None)
        if base is None:
            base = Path(sys.executable).parent
        return Path(base) / "plugins"
    return Path(__file__).resolve().parents[1] / "plugins"


# Source package names carry a "_plugin" suffix in development (e.g.
# ``demo_plugin``) while the compiled libraries drop it
# (e.g. ``demo.pyd``). The canonical plugin name is therefore the
# identifier without the suffix.
_PLUGIN_PACKAGE_SUFFIX = "_plugin"

# Extensions considered as compiled plugin libraries.
_EXTENSION_SUFFIXES = tuple(importlib.machinery.EXTENSION_SUFFIXES)

# Plugin manifests. YAML is the canonical format, stored in the plugin
# ``datas/`` data directory.
MANIFEST_NAMES = ("datas/plugin.yaml", "plugin.yaml")


def _has_manifest(directory: Path) -> bool:
    """Tell whether a directory contains a plugin manifest.

    Args:
        directory: Directory to check.

    Returns:
        True if ``plugin.yaml`` is present.
    """
    return any((directory / name).is_file() for name in MANIFEST_NAMES)


class GamePlugin(Protocol):
    """Interface for game plugins."""

    @property
    def name(self) -> str:
        """Plugin name (generic, no trademarked names)."""
        ...

    @property
    def version(self) -> str:
        """Plugin version."""
        ...

    @property
    def description(self) -> str:
        """Plugin description."""
        ...

    def get_classes(self) -> list[dict]:
        """Get character classes."""
        ...

    def get_monsters(self) -> list[dict]:
        """Get monsters."""
        ...

    def get_items(self) -> list[dict]:
        """Get items."""
        ...

    def get_rules(self) -> dict:
        """Get game rules."""
        ...

    def generate_dungeon(self, config: dict) -> dict:
        """Generate a dungeon."""
        ...

    def get_rule_engine(self) -> RuleEngine:
        """Get the hybrid (YAML data + Python classes) rule engine."""
        ...

    def create_component(self, kind: str) -> Any:
        """Instantiate a rule component declared in ``rules.yaml``."""
        ...


class PluginLoader:
    """Loads and manages game plugins.

    Plugins are discovered either as compiled extension libraries
    (``<name>.pyd``) or as source packages (``<name>_plugin``) and are
    loaded lazily, on demand, through :meth:`load_plugin`.
    """

    def __init__(self, plugins_dir: str | None = None) -> None:
        """Initialize the plugin loader.

        Args:
            plugins_dir: Directory containing plugins. When omitted, the
                directory is resolved automatically: ``<sys._MEIPASS>/plugins``
                for a frozen application, the ``companion4soloplayer/plugins``
                package otherwise.
        """
        self.plugins_dir = Path(plugins_dir) if plugins_dir else _default_plugins_dir()
        self.loaded_plugins: dict[str, GamePlugin] = {}
        #: Last load failure per plugin name (``"ErrorType: message"``).
        #: The released application runs without a console, so this is
        #: how callers (MainWindow) surface the real reason of a failure.
        self.last_errors: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _iter_plugin_dirs(self) -> list[Path]:
        """Return plugin directories containing a ``plugin.yaml`` manifest."""
        if not self.plugins_dir.is_dir():
            return []
        return sorted(
            item for item in self.plugins_dir.iterdir() if item.is_dir() and _has_manifest(item)
        )

    def discover_plugins(self) -> list[str]:
        """Discover available plugins.

        Both compiled libraries (``demo.pyd``) and source packages
        (``demo_plugin``) are recognized.

        Returns:
            List of plugin names
        """
        plugins = []
        for item in self._iter_plugin_dirs():
            # A directory only qualifies as a plugin when its code is
            # available: either a compiled library next to the manifest or
            # an importable source package.
            if (
                self._find_extension(item.name.replace(_PLUGIN_PACKAGE_SUFFIX, ""), item.parent)
                or importlib.util.find_spec(f"companion4soloplayer.plugins.{item.name}") is not None
            ):
                plugins.append(item.name.replace(_PLUGIN_PACKAGE_SUFFIX, ""))
        return plugins

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @staticmethod
    def _find_extension(plugin_name: str, directory: Path) -> Path | None:
        """Locate a compiled plugin library (``<name>.pyd``) in a directory."""
        for suffix in _EXTENSION_SUFFIXES:
            candidate = directory / f"{plugin_name}{suffix}"
            if candidate.is_file():
                return candidate
        return None

    def _load_compiled(self, plugin_name: str, library_path: Path) -> GamePlugin | None:
        """Load a compiled plugin library and instantiate its Plugin class."""
        spec = importlib.util.spec_from_file_location(
            f"companion4soloplayer.plugins.{plugin_name}",
            library_path,
            loader=importlib.machinery.ExtensionFileLoader(
                f"companion4soloplayer.plugins.{plugin_name}", str(library_path)
            ),
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create import spec for {library_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
            plugin = cast(GamePlugin, module.Plugin())
        except Exception:
            # Never leave a half-initialized module registered.
            sys.modules.pop(spec.name, None)
            raise
        self.loaded_plugins[plugin_name] = plugin
        return plugin

    def _load_source(self, plugin_name: str) -> GamePlugin | None:
        """Load a source plugin package and instantiate its Plugin class."""
        module = importlib.import_module(
            f"companion4soloplayer.plugins.{plugin_name}{_PLUGIN_PACKAGE_SUFFIX}"
        )
        plugin = cast(GamePlugin, module.Plugin())
        self.loaded_plugins[plugin_name] = plugin
        return plugin

    def load_plugin(self, plugin_name: str) -> GamePlugin | None:
        """Load a plugin on demand by name.

        Compiled libraries (``<name>.pyd`` in the plugins directory) are
        preferred; in development the ``<name>_plugin`` source package is
        used as a fallback.

        Args:
            plugin_name: Plugin name (without the ``_plugin`` suffix)

        Returns:
            Loaded plugin or None if not found
        """
        if plugin_name in self.loaded_plugins:
            return self.loaded_plugins[plugin_name]

        try:
            library_path = self._find_extension(plugin_name, self.plugins_dir)
            if library_path is not None:
                plugin = self._load_compiled(plugin_name, library_path)
            elif (
                importlib.util.find_spec(
                    f"companion4soloplayer.plugins.{plugin_name}{_PLUGIN_PACKAGE_SUFFIX}"
                )
                is not None
            ):
                plugin = self._load_source(plugin_name)
            else:
                print(f"Plugin {plugin_name} not found in {self.plugins_dir}")
                self.last_errors[plugin_name] = f"plugin library not found in {self.plugins_dir}"
                return None
        except Exception as e:
            self.last_errors[plugin_name] = f"{type(e).__name__}: {e}"
            print(f"Error loading plugin {plugin_name}: {e}")
            return None
        self.last_errors.pop(plugin_name, None)
        return plugin

    def get_plugin(self, plugin_name: str) -> GamePlugin | None:
        """Get a loaded plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            Plugin or None if not loaded
        """
        return self.loaded_plugins.get(plugin_name)

    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin.

        Also drops the dynamically registered module (compiled libraries)
        so a subsequent load re-imports it from disk.

        Args:
            plugin_name: Plugin name

        Returns:
            True if plugin was unloaded, False if not found
        """
        if plugin_name in self.loaded_plugins:
            del self.loaded_plugins[plugin_name]
            sys.modules.pop(f"companion4soloplayer.plugins.{plugin_name}", None)
            return True
        return False
