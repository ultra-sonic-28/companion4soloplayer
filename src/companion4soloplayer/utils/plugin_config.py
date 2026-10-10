"""
Plugin configuration (``datas/config.yaml``) support.

Each plugin may ship an optional ``config.yaml`` file in its ``datas/``
data directory (same location as the ``plugin.yaml`` manifest). The
file declares how the plugin wants its features to behave inside the
application (dialog sizes today, other settings later) without any code
change: the values are plain YAML data, read when the plugin is loaded
and published in the :class:`PluginConfigRegistry`.

The registry is a singleton (same pattern as
:class:`~companion4soloplayer.utils.resource_manager.ResourceManager`),
so a configuration loaded once by
:class:`~companion4soloplayer.utils.plugin_loader.PluginLoader` is
reachable from anywhere in the application, whatever its context::

    size = PluginConfigRegistry.instance().character_creation_dialog_size()

Document shape::

    dialog:
      - character_creation_dialog:
        width: 860
        height: 800

Every section is optional: a missing file, a missing section or a
missing entry falls back on the application default.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Self

from companion4soloplayer.utils.yaml_loader import (
    YamlLoadError,
    YamlTagError,
    load_yaml_file,
)

logger = logging.getLogger(__name__)

# Plugin configuration files. YAML is the canonical format, stored in
# the plugin ``datas/`` data directory (same layout as the manifest).
PLUGIN_CONFIG_NAMES = ("datas/config.yaml", "config.yaml")

#: Section of ``config.yaml`` describing dialog tweaks.
DIALOG_SECTION = "dialog"

#: Name of the character creation dialog (``dialog`` section).
CHARACTER_CREATION_DIALOG = "character_creation_dialog"

#: Default minimum size of the character creation dialog, in pixels,
#: used when no plugin configuration declares one.
DEFAULT_CREATION_DIALOG_WIDTH = 860
DEFAULT_CREATION_DIALOG_HEIGHT = 800


def find_plugin_config(directories: Iterable[Path]) -> Path | None:
    """Locate the configuration file of a plugin.

    Directories are probed in order; the first one holding a
    configuration file wins. In each directory both the canonical
    ``datas/config.yaml`` location and the flat ``config.yaml`` fallback
    are accepted, exactly like the plugin manifest.

    Args:
        directories: Candidate plugin directories.

    Returns:
        Path of the configuration file, or None when no directory
        holds one.
    """
    for directory in directories:
        for name in PLUGIN_CONFIG_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def load_plugin_config(directories: Iterable[Path]) -> dict[str, Any]:
    """Load the configuration file of a plugin.

    A missing file, an unreadable file or an invalid YAML document is
    not an error: the plugin keeps working with an empty configuration
    and the application defaults apply.

    Args:
        directories: Candidate plugin directories, probed in order (see
            :func:`find_plugin_config`).

    Returns:
        The parsed configuration mapping, empty when no valid
        configuration file was found.
    """
    path = find_plugin_config(directories)
    if path is None:
        return {}
    try:
        document = load_yaml_file(path)
    except (OSError, YamlLoadError, YamlTagError) as exc:
        logger.warning("Ignoring invalid plugin configuration %s: %s", path, exc)
        return {}
    if document is None:
        return {}
    if not isinstance(document, Mapping):
        logger.warning("Ignoring plugin configuration %s: expected a YAML mapping", path)
        return {}
    return dict(document)


def dialog_settings(config: Mapping[str, Any], dialog_name: str) -> dict[str, Any]:
    """Return the settings declared for one dialog by a configuration.

    Dialogs are listed under the ``dialog`` section. Two spellings are
    accepted for an entry::

        # Settings nested under the dialog name
        - character_creation_dialog:
            width: 860
            height: 800

        # Settings written next to the dialog name (name -> null)
        - character_creation_dialog:
          width: 860
          height: 800

    Args:
        config: Parsed plugin configuration.
        dialog_name: Dialog identifier (e.g.
            ``"character_creation_dialog"``).

    Returns:
        The settings of the first matching entry, empty when the
        configuration declares no such dialog.
    """
    entries = config.get(DIALOG_SECTION)
    if not isinstance(entries, list):
        return {}
    for entry in entries:
        if not isinstance(entry, Mapping) or dialog_name not in entry:
            continue
        declared = entry[dialog_name]
        if isinstance(declared, Mapping):
            return dict(declared)
        # Flat spelling: the dialog name maps to null and the settings
        # are its siblings in the same mapping.
        return {key: value for key, value in entry.items() if key != dialog_name}
    return {}


def _positive_int(value: Any, default: int) -> int:
    """Return ``value`` as a positive int, or ``default`` when unusable.

    Args:
        value: Raw value read from the YAML document.
        default: Fallback value.

    Returns:
        The value when it is a positive integer, the default otherwise
        (booleans, negative values and non-integer types are rejected).
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value if value > 0 else default


class PluginConfigRegistry:
    """Singleton registry publishing the configuration of loaded plugins.

    The plugin loader registers the ``datas/config.yaml`` document of
    each plugin it loads and unregisters it on unload, so any component
    of the application reads the settings of the active game system
    through :meth:`instance`, without holding a reference to the plugin
    itself.
    """

    _instance: Self | None = None
    _initialized: bool = False

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize an empty registry (first call only, singleton)."""
        if self._initialized:
            return
        self._configs: dict[str, dict[str, Any]] = {}
        self._initialized = True

    @classmethod
    def instance(cls) -> Self:
        """Return the single instance of the registry."""
        if cls._instance is None:
            cls()
        assert cls._instance is not None
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for tests)."""
        cls._instance = None
        cls._initialized = False

    # ------------------------------------------------------------------ #
    # Registration                                                        #
    # ------------------------------------------------------------------ #

    def register(self, plugin_name: str, config: Mapping[str, Any] | None = None) -> None:
        """Publish the configuration of a plugin (replacing any previous one).

        Args:
            plugin_name: Plugin name.
            config: Parsed ``datas/config.yaml`` document; an empty or
                missing configuration publishes nothing meaningful (the
                application defaults apply).
        """
        self._configs[plugin_name] = dict(config or {})

    def unregister(self, plugin_name: str) -> None:
        """Drop the configuration published for a plugin.

        Args:
            plugin_name: Plugin name.
        """
        self._configs.pop(plugin_name, None)

    def plugin_names(self) -> tuple[str, ...]:
        """Return the names of the plugins holding a registered configuration."""
        return tuple(self._configs)

    def config(self, plugin_name: str | None = None) -> dict[str, Any]:
        """Return the configuration published for a plugin.

        Args:
            plugin_name: Plugin name. ``None`` returns the configuration
                of the first registered plugin (the typical case of a
                single active game system).

        Returns:
            A copy of the configuration, empty when nothing matches.
        """
        if plugin_name is not None:
            return dict(self._configs.get(plugin_name, {}))
        if self._configs:
            return dict(next(iter(self._configs.values())))
        return {}

    # ------------------------------------------------------------------ #
    # Settings                                                            #
    # ------------------------------------------------------------------ #

    def dialog_settings(self, dialog_name: str, plugin_name: str | None = None) -> dict[str, Any]:
        """Return the settings declared for a dialog.

        Args:
            dialog_name: Dialog identifier (e.g.
                ``"character_creation_dialog"``).
            plugin_name: Plugin whose configuration is consulted, ``None``
                for the first registered plugin.

        Returns:
            The declared settings, empty when the plugin declares none.
        """
        return dialog_settings(self.config(plugin_name), dialog_name)

    def character_creation_dialog_size(self, plugin_name: str | None = None) -> tuple[int, int]:
        """Return the minimum size of the character creation dialog.

        Reads the ``width`` / ``height`` entries of the
        ``character_creation_dialog`` entry of the ``dialog`` section of
        the plugin configuration. Missing or invalid entries fall back
        on the application defaults (860 x 800 pixels).

        Args:
            plugin_name: Plugin whose configuration is consulted, ``None``
                for the first registered plugin.

        Returns:
            ``(width, height)`` in pixels.
        """
        settings = self.dialog_settings(CHARACTER_CREATION_DIALOG, plugin_name)
        return (
            _positive_int(settings.get("width"), DEFAULT_CREATION_DIALOG_WIDTH),
            _positive_int(settings.get("height"), DEFAULT_CREATION_DIALOG_HEIGHT),
        )
