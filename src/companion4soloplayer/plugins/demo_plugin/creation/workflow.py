"""Assemble the character creation workflow of the demo game system.

The game-system specific parts of the feature live here and in the
``datas/`` directory:

- ``datas/workflow.yaml`` declares the **order of the steps**;
- ``datas/creation_rules.yaml`` declares the bonuses and maluses
  ("if Race=Dwarf then +2 Constitution", skill inheritance, automatic
  spell grants...);
- ``datas/attributes.yaml`` declares the player attributes (block
  title, and id/name/description of each attribute, in display order);
- the YAML catalogs (``races``, ``classes``, ``skills``, ``spells``)
  and the named strategies are gathered into the ``system`` mapping
  attached to the pipeline contexts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from companion4soloplayer.core.creation import (
    CharacterCreationPipeline,
    build_workflow,
    load_creation_rules,
)
from companion4soloplayer.core.creation.strategies import RollStrategy

from ..data import DATA_DIR, load_data
from .strategies import FourSixKeepBestStrategy

#: Data file declaring the player attributes of the game system.
ATTRIBUTES_FILE = "attributes.yaml"


def load_attributes() -> dict[str, Any]:
    """Load the attribute declarations of the game system.

    ``datas/attributes.yaml`` holds the title of the attributes block
    (``attributes.title``) and the ordered list of the attributes
    (``attributes.list``), each entry declaring its technical ``id``
    (state path and answer key), its display ``name`` and an optional
    ``description``. The list order is the display order of the
    fields in the player creation dialog.

    Returns:
        The normalized ``{"title": ..., "list": [...]}`` mapping.

    Raises:
        YamlLoadError: If the file is not valid YAML.
        ValueError: If the document is malformed (missing or empty
            title, missing list, entry without a valid ``id``,
            duplicate identifier).
    """
    document = load_data(ATTRIBUTES_FILE)
    if not isinstance(document, Mapping):
        raise ValueError(f"{ATTRIBUTES_FILE} must declare a mapping with an 'attributes' key")
    attributes = document.get("attributes")
    if not isinstance(attributes, Mapping):
        raise ValueError(f"{ATTRIBUTES_FILE} must declare an 'attributes' mapping")
    title = attributes.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"{ATTRIBUTES_FILE} requires a non-empty 'attributes.title' string")
    entries = attributes.get("list")
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
        raise ValueError(f"{ATTRIBUTES_FILE} requires an 'attributes.list' sequence")
    identifiers: list[str] = []
    for position, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ValueError(f"{ATTRIBUTES_FILE} attribute #{position + 1} must be a mapping")
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(
                f"{ATTRIBUTES_FILE} attribute #{position + 1} requires a non-empty 'id' string"
            )
        identifiers.append(identifier.strip())
    duplicated = sorted({name for name in identifiers if identifiers.count(name) > 1})
    if duplicated:
        raise ValueError(f"{ATTRIBUTES_FILE} declares duplicate attribute id(s): {duplicated!r}")
    return {"title": title.strip(), "list": [dict(entry) for entry in entries]}


def build_system() -> dict[str, Any]:
    """Gather the game data read by the creation steps.

    Returns:
        The ``system`` mapping attached to the pipeline: catalogs
        (``races``, ``classes``, ``skills``, ``spells``), the attribute
        declarations and block title read from ``datas/attributes.yaml``
        and the named attribute generation strategies.

    Raises:
        YamlLoadError: If a data file is not valid YAML.
        ValueError: If ``datas/attributes.yaml`` is malformed.
    """
    attributes = load_attributes()
    return {
        "attributes": attributes["list"],
        "attributes_title": attributes["title"],
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
