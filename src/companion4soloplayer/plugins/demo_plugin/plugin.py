"""Plugin facade: the ``Plugin`` class loaded by the plugin loader.

The facade exposes the
:class:`~companion4soloplayer.core.interface.game_plugin.GamePlugin`
protocol API, serves the YAML data documents from the ``datas/``
directory, binds the hybrid rule engine (declarative ``rules.yaml`` +
Python rule elements) and assembles the character creation workflow
(``datas/workflow.yaml`` + ``datas/creation_rules.yaml``).
"""

from __future__ import annotations

from typing import Any

from companion4soloplayer.core.creation import CharacterCreationPipeline
from companion4soloplayer.core.rule_engine import RuleEngine

from .creation.workflow import create_character_creation as build_character_creation
from .data import DATA_DIR, load_data
from .manifest import PluginMetadata


class Plugin:
    """Game System Demo Plugin implementation."""

    def __init__(self) -> None:
        """Initialize the plugin and load its manifest."""
        self._metadata = PluginMetadata(**load_data("plugin.yaml"))
        self._engine: RuleEngine | None = None
        self._creation: CharacterCreationPipeline | None = None

    @property
    def name(self) -> str:
        """Plugin name."""
        return self._metadata.name

    @property
    def version(self) -> str:
        """Plugin version."""
        return self._metadata.version

    @property
    def description(self) -> str:
        """Plugin description."""
        return self._metadata.description

    def get_classes(self) -> list[dict]:
        """Get character classes."""
        return list(load_data("classes.yaml"))

    def get_monsters(self) -> list[dict]:
        """Get monsters."""
        return list(load_data("monsters.yaml"))

    def get_items(self) -> list[dict]:
        """Get items."""
        return list(load_data("items.yaml"))

    def get_rules(self) -> dict:
        """Get game rules (declarative YAML document)."""
        return dict(self.get_rule_engine().rules)

    def get_rule_engine(self) -> RuleEngine:
        """Get the hybrid rule engine bound to this plugin package."""
        if self._engine is None:
            self._engine = RuleEngine.from_yaml(
                DATA_DIR / "rules.yaml",
                base_module=__package__,
            )
        return self._engine

    def create_component(self, kind: str) -> Any:
        """Instantiate a rule component declared in ``rules.yaml``.

        Args:
            kind: Rule kind (see ``core.rule_engine.RULE_KINDS``).

        Returns:
            The instantiated component (cached by the rule engine).
        """
        return self.get_rule_engine().component(kind)

    def create_character_creation(self) -> CharacterCreationPipeline:
        """Get the character creation workflow of this game system.

        The pipeline is built once (the object is stateless and
        reusable) from ``datas/workflow.yaml`` (step order),
        ``datas/creation_rules.yaml`` (bonuses/maluses) and the YAML
        catalogs of the plugin.

        Returns:
            The assembled creation pipeline.

        Raises:
            YamlLoadError: If a data file is not valid YAML.
            RuleDefinitionError: If the creation rules are malformed.
            WorkflowError: If the workflow cannot be built.
        """
        if self._creation is None:
            # base_module is this plugin package: 'local:' references
            # of workflow.yaml resolve against it, exactly like the
            # 'local:' references of rules.yaml.
            self._creation = build_character_creation(base_module=__package__)
        return self._creation

    def generate_dungeon(self, config: dict) -> dict:
        """Generate a dungeon."""
        return {
            "rooms": [],
            "config": config,
        }
