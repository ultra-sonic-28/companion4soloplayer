"""Generic game interfaces of the engine.

This package hosts the contracts shared between the generic engine and
the game plugins (for example :class:`GamePlugin`). It contains
interfaces only: concrete mechanisms such as plugin discovery and
loading live in :mod:`companion4soloplayer.utils.plugin_loader`.
"""

from companion4soloplayer.core.interface.game_plugin import GamePlugin

__all__ = ["GamePlugin"]
