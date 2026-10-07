"""Assemble the character creation workflow of the demo game system.

The game-system specific parts of the feature live here and in the
``datas/`` directory:

- ``datas/workflow.yaml`` declares the **order of the steps**;
- ``datas/creation_rules.yaml`` declares the bonuses and maluses
  ("if Race=Dwarf then +2 Constitution", skill inheritance, automatic
  spell grants...);
- the YAML catalogs (``races``, ``classes``, ``skills``, ``spells``)
  and the named strategies are gathered into the ``system`` mapping
  attached to the pipeline contexts.
"""

from __future__ import annotations

from typing import Any

from companion4soloplayer.core.creation import (
    CharacterCreationPipeline,
    build_workflow,
    load_creation_rules,
)
from companion4soloplayer.core.creation.strategies import RollStrategy

from ..data import DATA_DIR, load_data
from .strategies import FourSixKeepBestStrategy

#: Attribute names of the demo game system, in generation order.
ATTRIBUTES: tuple[str, ...] = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)


def build_system() -> dict[str, Any]:
    """Gather the game data read by the creation steps.

    Returns:
        The ``system`` mapping attached to the pipeline: catalogs
        (``races``, ``classes``, ``skills``, ``spells``), attribute
        names and the named attribute generation strategies.
    """
    return {
        "attributes": list(ATTRIBUTES),
        "races": load_data("races.yaml"),
        "classes": load_data("classes.yaml"),
        "skills": load_data("skills.yaml"),
        "spells": load_data("spells.yaml"),
        "strategies": {
            "classic_4d6": FourSixKeepBestStrategy(),
            "3d6": RollStrategy("3d6"),
            "4d6_drop_lowest": RollStrategy("4d6", keep=3),
        },
    }


def create_character_creation(*, base_module: str | None = None) -> CharacterCreationPipeline:
    """Build the character creation pipeline of the demo game system.

    Args:
        base_module: Module resolving the ``local:`` references of
            ``workflow.yaml`` (the plugin package). Defaults to the
            parent package of this module, which is the plugin package
            in development and in the compiled build alike; the plugin
            facade passes its own ``__package__`` explicitly.

    Returns:
        The assembled pipeline (steps in workflow order, creation rules,
        game data).

    Raises:
        YamlLoadError: If a data file is not valid YAML.
        RuleDefinitionError: If ``creation_rules.yaml`` is malformed.
        WorkflowError: If ``workflow.yaml`` cannot be turned into a
            pipeline.
    """
    workflow = load_data("workflow.yaml")
    rules = load_creation_rules(DATA_DIR / "creation_rules.yaml")
    if base_module is None:
        package = __package__ or ""
        parent, _, _ = package.rpartition(".")
        base_module = parent or package
    return build_workflow(
        workflow,
        rules=rules,
        base_module=base_module,
        system=build_system(),
    )
