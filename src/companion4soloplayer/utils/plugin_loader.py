"""
Plugin loader utility.

Handles the discovery and safe loading of game plugins. This module is
a utility (``companion4soloplayer.utils``), not part of the generic
engine: the contract implemented by the plugins it returns is the
:class:`companion4soloplayer.core.interface.game_plugin.GamePlugin`
protocol.

Two operating modes are supported:

- Development: plugins live as regular Python packages
  (``src/companion4soloplayer/plugins/<name>_plugin/``) and are imported
  through the standard import machinery.
- Frozen application (PyInstaller one-dir build): each plugin ships as a
  compiled extension module (``<name>.pyd``) located in the
  ``plugins/`` folder next to the application ``_internal`` data, and is
  loaded dynamically through importlib.

Both kinds of plugin expose a ``Plugin`` class compatible with the
:class:`~companion4soloplayer.core.interface.game_plugin.GamePlugin`
protocol. Plugin data (manifest, classes, rules...)
ships as commented YAML files (``plugin.yaml``, ``rules.yaml``, ...)
loaded through :mod:`companion4soloplayer.utils.yaml_loader`, and rule
elements are bound to Python classes through the hybrid
:class:`companion4soloplayer.core.rule_engine.RuleEngine`.

A plugin may also ship an optional ``datas/config.yaml`` file (see
:mod:`companion4soloplayer.utils.plugin_config`): it is read when the
plugin is loaded and published in the plugin configuration registry,
which makes its values reachable from anywhere in the application.
"""

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import logging
import sys
import types
from pathlib import Path
from typing import Any, cast

from companion4soloplayer.core.interface.game_plugin import GamePlugin
from companion4soloplayer.utils.plugin_config import PluginConfigRegistry, load_plugin_config

logger = logging.getLogger(__name__)


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
        plugins_dir = Path(base) / "plugins"
    else:
        plugins_dir = Path(__file__).resolve().parents[1] / "plugins"
    logger.debug(
        "Resolved plugins directory: %s (frozen=%s, _MEIPASS=%s)",
        plugins_dir,
        getattr(sys, "frozen", False),
        getattr(sys, "_MEIPASS", None),
    )
    return plugins_dir


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


def _ensure_parent_packages(module_name: str) -> None:
    """Ensure the parent packages of a dotted module name exist in ``sys.modules``.

    Frozen builds ship compiled plugins as loose ``<name>.pyd`` files in
    ``<MEIPASS>/plugins/``: there is no ``companion4soloplayer/plugins/``
    package directory on disk. When such an extension is loaded with a dotted
    spec name (``companion4soloplayer.plugins.demo``), Python (and Nuitka's
    package initialisation) needs the parent package
    ``companion4soloplayer.plugins`` to be resolvable, otherwise the
    extension's initialisation raises::

        ModuleNotFoundError: No module named 'companion4soloplayer.plugins'

    Only missing parents are registered: already-imported packages (the real
    application package ``companion4soloplayer`` first and foremost) are left
    untouched so they are never replaced by a synthetic placeholder.
    """
    parts = module_name.split(".")
    for index in range(1, len(parts)):
        parent = ".".join(parts[:index])
        if parent in sys.modules:
            logger.debug("Parent package '%s' already present in sys.modules", parent)
            continue
        parent_module = types.ModuleType(parent)
        parent_module.__path__ = []
        parent_module.__package__ = ".".join(parts[: index - 1]) if index > 1 else ""
        sys.modules[parent] = parent_module
        logger.debug("Registered synthetic parent package '%s' in sys.modules", parent)


class _PluginSubmoduleFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Import finder temporaire pour les sous-modules d'un plugin compilé.

    In frozen mode (Nuitka package mode), a plugin's ``.pyd`` file is loaded
    under a canonical name (``companion4soloplayer.plugins.demo_plugin``),
    while its internal code references its submodules using the same development-time
    names (``companion4soloplayer.plugins.demo_plugin.creation``, ``...rules``, etc.).
    In frozen mode, these submodules do not exist as separate files on disk; instead,
    they are merged into the ``.pyd`` file.

    This finder creates separate submodules whose ``__getattr__`` delegates to the
    main module of the ``.pyd`` file. Thus, a ``from .creation import X``
    resolves the submodule ``demo_plugin.creation`` and then retrieves the
    attribute ``X`` from the main module (which contains all the code merged by
    Nuitka). Creating delegating modules for leaf names (e.g.
    ``demo_plugin.plugin.Plugin``, ``demo_plugin.creation.filters.skill_available``)
    shadows the real callables during ``exec_module``; when those placeholders are
    later encountered (e.g. by ``local:`` references in workflow.yaml),
    :meth:`companion4soloplayer.core.rule_engine.RuleEngine._resolve_through_canonical_path`
    resolves them to the actual callables through the canonical ``demo.*`` path.

    This finder is inserted into ``sys.meta_path`` only during
    :meth:`exec_module` and is removed immediately afterward, so as not to
    affect the rest of the application. This is not a PyInstaller hook;
    it is an internal execution mechanism used by the loader.
    """

    def __init__(
        self,
        package_prefixes: list[str],
        target_module: types.ModuleType,
    ) -> None:
        self.package_prefixes = package_prefixes
        self.target_module = target_module

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> importlib.machinery.ModuleSpec | None:
        for prefix in self.package_prefixes:
            if (
                fullname.startswith(prefix + ".")
                and fullname not in sys.modules
            ):
                return importlib.machinery.ModuleSpec(
                    fullname,
                    self,
                    origin="<plugin-submodule>",
                )
        return None

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType | None:
        # Create a submodule separate from the main module. Its __getattr__
        # delegates to the main module for lazy access to attributes
        # merged by Nuitka.
        sub = types.ModuleType(spec.name)
        sub.__package__ = spec.parent
        sub.__getattr__ = lambda name: getattr(self.target_module, name)  # type: ignore[assignment]
        sys.modules[spec.name] = sub
        logger.debug("Created submodule '%s' delegating to '%s'", spec.name, self.target_module.__name__)
        return sub

    def exec_module(self, module: types.ModuleType) -> None:
        # Nothing to execute: the submodule delegates to the main module.
        pass


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
        logger.debug("PluginLoader initialized (plugins_dir=%s)", self.plugins_dir)

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
        logger.info("Discovered plugins: %s", plugins)
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
                logger.debug("Found compiled extension '%s' at %s", plugin_name, candidate)
                return candidate
        logger.debug("No compiled extension for '%s' in %s", plugin_name, directory)
        return None

    def _load_compiled(self, plugin_name: str, library_path: Path) -> GamePlugin | None:
        """Load a compiled plugin library and instantiate its Plugin class."""
        # The .pyd file is loaded under its canonical name (without the _plugin suffix,
        # e.g., companion4soloplayer.plugins.demo) so that the PyInit_demo
        # export from the compiled extension can be located by importlib.
        # However, the compiled code (in Nuitka package mode) references its
        # submodules using their development names (demo_plugin.creation, etc.),
        # which necessitates the additional prefixes handled by the finder below.
        module_name = f"companion4soloplayer.plugins.{plugin_name}"
        alias_name = f"{module_name}{_PLUGIN_PACKAGE_SUFFIX}"
        logger.debug(
            "Loading compiled plugin '%s' from %s (spec name: %s, alias: %s)",
            plugin_name,
            library_path,
            module_name,
            alias_name,
        )
        # The frozen build ships loose ``<name>.pyd`` files: the parent package
        # ``companion4soloplayer.plugins`` does not exist on disk. Register it
        # (and any other missing parent) in sys.modules so the extension's
        # relative imports and Nuitka package initialisation can resolve it.
        _ensure_parent_packages(module_name)
        spec = importlib.util.spec_from_file_location(module_name, str(library_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create import spec for {library_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        logger.debug("Created module '%s' and registered it in sys.modules", spec.name)
        # Register the module under its development name with the
        # _plugin suffix, so that relative imports within the compiled code—which
        # resolve to companion4soloplayer.plugins.demo_plugin—can find the
        # module. The alias is a *separate* wrapper module (not the same object
        # as the canonical module) whose __getattr__ delegates to the canonical
        # module. This ensures the canonical module's attributes
        # (demo.Plugin, demo.skill_available, ...) are never replaced by
        # synthetic placeholders created by the finder; when those
        # placeholders are encountered (e.g. by local: references in
        # workflow.yaml), RuleEngine._resolve_through_canonical_path
        # resolves them to the actual callables through the demo.* path.
        if alias_name not in sys.modules:
            alias_module = types.ModuleType(alias_name)
            alias_module.__package__ = module.__package__
            alias_module.__path__ = [str(library_path.parent / plugin_name)]
            alias_module.__getattr__ = lambda name: getattr(module, name)  # type: ignore[assignment]
            sys.modules[alias_name] = alias_module
            logger.debug(
                "Registered alias '%s' -> '%s' in sys.modules", alias_name, spec.name
            )
        try:
            # Insert a temporary finder to resolve submodules of the
            # compiled package to the main .pyd module during
            # exec_module. This is not a PyInstaller hook; it is an
            # internal execution mechanism within the loader, active only
            # while the plugin is being loaded.
            #
            # All imports using the development name with the
            # ``_plugin`` suffix (e.g., ``demo_plugin.creation``) need to
            # be intercepted: these are hardcoded into the compiled
            # code and refer to submodules that do not exist as
            # separate files in frozen mode. Canonical relative imports
            # (e.g., ``demo.creation``), by contrast, are resolved by
            # Nuitka itself during package initialization, which creates
            # the actual submodules (and thus the actual classes, such
            # as ``Plugin``). Intercepting those would prevent Nuitka
            # from creating them and would link ``demo.Plugin`` to an
            # empty module instead of the class, rendering
            # ``module.Plugin()`` unusable.
            finder = _PluginSubmoduleFinder([alias_name], module)
            sys.meta_path.insert(0, finder)
            logger.debug(
                "Installed temporary submodule finder for '%s'", module_name
            )
            try:
                spec.loader.exec_module(module)
                plugin = cast(GamePlugin, module.Plugin())
            finally:
                sys.meta_path.remove(finder)
                logger.debug(
                    "Removed temporary submodule finder for '%s'", module_name
                )
        except Exception:
            # Never leave a half-initialized module registered.
            sys.modules.pop(spec.name, None)
            sys.modules.pop(alias_name, None)
            logger.debug("Failed to execute compiled plugin '%s'; module unregistered", plugin_name)
            raise
        self.loaded_plugins[plugin_name] = plugin
        logger.info(
            "Compiled plugin '%s' loaded successfully (type=%s)",
            plugin_name,
            type(plugin).__name__,
        )
        return plugin

    def _load_source(self, plugin_name: str) -> GamePlugin | None:
        """Load a source plugin package and instantiate its Plugin class."""
        module_name = f"companion4soloplayer.plugins.{plugin_name}{_PLUGIN_PACKAGE_SUFFIX}"
        logger.debug("Loading source plugin '%s' via %s", plugin_name, module_name)
        module = importlib.import_module(module_name)
        plugin = cast(GamePlugin, module.Plugin())
        self.loaded_plugins[plugin_name] = plugin
        logger.debug(
            "Source plugin '%s' loaded successfully (type=%s)",
            plugin_name,
            type(plugin).__name__,
        )
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
            logger.debug("Plugin '%s' already loaded, returning cached instance", plugin_name)
            return self.loaded_plugins[plugin_name]

        logger.debug("Loading plugin '%s' (plugins_dir=%s)", plugin_name, self.plugins_dir)
        try:
            library_path = self._find_extension(plugin_name, self.plugins_dir)
            if library_path is not None:
                logger.debug("Found compiled extension for plugin '%s': %s", plugin_name, library_path)
                plugin = self._load_compiled(plugin_name, library_path)
            elif (
                importlib.util.find_spec(
                    f"companion4soloplayer.plugins.{plugin_name}{_PLUGIN_PACKAGE_SUFFIX}"
                )
                is not None
            ):
                logger.debug("Found source package for plugin '%s'", plugin_name)
                plugin = self._load_source(plugin_name)
            else:
                message = f"Plugin {plugin_name} not found in {self.plugins_dir}"
                logger.debug(message)
                self.last_errors[plugin_name] = f"plugin library not found in {self.plugins_dir}"
                return None
        except Exception as e:
            self.last_errors[plugin_name] = f"{type(e).__name__}: {e}"
            logger.debug("Error loading plugin '%s': %s", plugin_name, e, exc_info=True)
            print(f"Error loading plugin {plugin_name}: {e}")
            return None
        self._publish_config(plugin_name, library_path)
        self.last_errors.pop(plugin_name, None)
        logger.info("Plugin '%s' fully loaded and config published", plugin_name)
        return plugin

    def _publish_config(self, plugin_name: str, library_path: Path | None) -> None:
        """Load the ``datas/config.yaml`` file of a plugin and publish it.

        The configuration is registered in the global
        :class:`~companion4soloplayer.utils.plugin_config.PluginConfigRegistry`,
        which makes its values reachable from anywhere in the
        application, whatever the context. A plugin without a
        configuration file (or with an invalid one) publishes an empty
        mapping: the application defaults apply.

        Args:
            plugin_name: Plugin name.
            library_path: Path of the compiled library, or None when the
                plugin was loaded from its source package.
        """
        logger.debug("Publishing config for plugin '%s' (library_path=%s)", plugin_name, library_path)
        candidates: list[Path] = []
        if library_path is not None:
            # Compiled library: data files sit in <plugins_dir>/<name>/.
            candidates.append(library_path.parent / plugin_name)
        # Source package: data files sit in the package itself.
        candidates.append(self.plugins_dir / f"{plugin_name}{_PLUGIN_PACKAGE_SUFFIX}")
        candidates.append(self.plugins_dir / plugin_name)
        PluginConfigRegistry.instance().register(plugin_name, load_plugin_config(candidates))
        logger.debug("Config published for plugin '%s' (candidates=%s)", plugin_name, candidates)

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
        so a subsequent load re-imports it from disk, together with the
        configuration published in the plugin configuration registry.

        Args:
            plugin_name: Plugin name

        Returns:
            True if plugin was unloaded, False if not found
        """
        if plugin_name in self.loaded_plugins:
            del self.loaded_plugins[plugin_name]
            PluginConfigRegistry.instance().unregister(plugin_name)
            canonical = f"companion4soloplayer.plugins.{plugin_name}"
            alias = f"{canonical}{_PLUGIN_PACKAGE_SUFFIX}"
            sys.modules.pop(canonical, None)
            sys.modules.pop(alias, None)
            # Nettoyer aussi les sous-modules créés par le finder lors du chargement.
            for name in list(sys.modules):
                if name.startswith(canonical + ".") or name.startswith(alias + "."):
                    del sys.modules[name]
            logger.debug("Plugin '%s' unloaded", plugin_name)
            return True
        logger.debug("Plugin '%s' is not loaded, nothing to unload", plugin_name)
        return False
