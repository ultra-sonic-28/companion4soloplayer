"""Game System Demo Plugin.
Provided as a generic example for creating new plugins and how to use them.

Game data ships as commented YAML files in the ``datas/`` directory
(plugin.yaml, classes.yaml, rules.yaml, workflow.yaml, ...). Rule
elements bound with ``!pyclass local:...`` are implemented by the
classes re-exported here (defined one file per class under ``rules/``)
and instantiated on demand by the core rule engine. The shared yes/no
oracle lives in ``companion4soloplayer.core.rules``.

The character creation workflow re-exports here too: its
``datas/workflow.yaml`` document references ``local:`` names (such as
the ``spell_available`` filter) that must resolve against this package
in development and in the compiled build alike.

This package facade keeps the public surface of the plugin: the core
plugin loader instantiates :class:`Plugin`, and the ``local:``
references of ``datas/rules.yaml`` and ``datas/workflow.yaml`` resolve
against this module.
"""

from __future__ import annotations

from .creation import FourSixKeepBestStrategy, spell_available
from .manifest import PluginMetadata
from .plugin import Plugin
from .rules import CharacterCreationRule, CombatRule, LootRule, MagicRule

__all__ = [
    "CharacterCreationRule",
    "CombatRule",
    "FourSixKeepBestStrategy",
    "LootRule",
    "MagicRule",
    "Plugin",
    "PluginMetadata",
    "spell_available",
]
