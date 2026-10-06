"""``GamePlugin`` contract implemented by every game plugin."""

from typing import Any, Protocol

from companion4soloplayer.core.rule_engine import RuleEngine


class GamePlugin(Protocol):
    """Interface for game plugins.

    The protocol is structural: the facade class of a plugin
    (``Plugin``) is loaded by
    :class:`companion4soloplayer.utils.plugin_loader.PluginLoader` and
    used through this contract without inheriting from it.
    """

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
