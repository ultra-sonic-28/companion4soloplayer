"""Rule elements implemented by the demo plugin.

Each rule class lives in its own module, named after the class. The
classes are re-exported by the plugin package ``__init__`` so the
``local:`` references of ``datas/rules.yaml`` resolve against the
declaring package in development and in the compiled build alike.
"""

from .character_creation_rule import CharacterCreationRule
from .combat_rule import CombatRule
from .loot_rule import LootRule
from .magic_rule import MagicRule

__all__ = ["CharacterCreationRule", "CombatRule", "LootRule", "MagicRule"]
