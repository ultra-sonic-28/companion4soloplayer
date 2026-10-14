"""Assemble the character creation workflow of the demo game system.

The game-system specific parts of the feature live here and in the
``datas/`` directory:

- ``datas/workflow.yaml`` declares the **order of the steps** and the
  generation mode/strategy of every attribute block (``classic_4d6``
  for the attributes, ``class_saves`` for the saving throws);
- ``datas/classes.yaml`` declares the base saving throws of each class
  (``save`` mapping read by the ``class_saves`` strategy);
- ``datas/creation_rules.yaml`` declares the bonuses and maluses
  ("if Race=Dwarf then +2 Constitution", skill inheritance, automatic
  spell grants...);
- ``datas/attributes.yaml`` declares the **attribute blocks** (one
  block per level-1 entry: block title, and id/name/description of each
  attribute, in display order);
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
from .strategies import ClassSavesStrategy, FourSixKeepBestStrategy

#: Data file declaring the player attributes of the game system.
ATTRIBUTES_FILE = "attributes.yaml"


def load_attributes() -> list[dict[str, Any]]:
    """Load the attribute block declarations of the game system.

    ``datas/attributes.yaml`` declares one **block** per level-1 entry
    (``attributes``, ``save``...): the entry key is the technical block
    identifier (step id and state path segment), and the entry mapping
    holds the title of the block (``title``) and the ordered list of its
    attributes (``list``), each entry declaring its technical ``id``
    (state path and answer key), its display ``name`` and an optional
    ``description``. The block order is the display order of the blocks
    in the player creation dialog, and the list order is the display
    order of the fields inside a block.

    Returns:
        One ``{"id": ..., "title": ..., "list": [...]}`` mapping per
        declared block, in declaration order.

    Raises:
        YamlLoadError: If the file is not valid YAML.
        ValueError: If the document is malformed (no block, a block
            without a valid ``id``/``title``/``list``, an entry without
            a valid ``id``, duplicate identifier inside a block).
    """
    document = load_data(ATTRIBUTES_FILE)
    if not isinstance(document, Mapping):
        raise ValueError(f"{ATTRIBUTES_FILE} must declare a mapping of attribute blocks")
    if not document:
        raise ValueError(f"{ATTRIBUTES_FILE} must declare at least one attribute block")
    blocks: list[dict[str, Any]] = []
    for key, block in document.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{ATTRIBUTES_FILE} requires non-empty block identifiers")
        identifier = key.strip()
        if not isinstance(block, Mapping):
            raise ValueError(
                f"{ATTRIBUTES_FILE} block {identifier!r} must be a mapping with 'title' and 'list'"
            )
        title = block.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(
                f"{ATTRIBUTES_FILE} block {identifier!r} requires a non-empty 'title' string"
            )
        entries = block.get("list")
        if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
            raise ValueError(f"{ATTRIBUTES_FILE} block {identifier!r} requires a 'list' sequence")
        identifiers: list[str] = []
        for position, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                raise ValueError(
                    f"{ATTRIBUTES_FILE} block {identifier!r} attribute #{position + 1} "
                    "must be a mapping"
                )
            attribute_id = entry.get("id")
            if not isinstance(attribute_id, str) or not attribute_id.strip():
                raise ValueError(
                    f"{ATTRIBUTES_FILE} block {identifier!r} attribute #{position + 1} "
                    "requires a non-empty 'id' string"
                )
            identifiers.append(attribute_id.strip())
        duplicated = sorted({name for name in identifiers if identifiers.count(name) > 1})
        if duplicated:
            raise ValueError(
                f"{ATTRIBUTES_FILE} block {identifier!r} declares duplicate "
                f"attribute id(s): {duplicated!r}"
            )
        blocks.append(
            {"id": identifier, "title": title.strip(), "list": [dict(entry) for entry in entries]}
        )
    return blocks


def build_system() -> dict[str, Any]:
    """Gather the game data read by the creation steps.

    Returns:
        The ``system`` mapping attached to the pipeline: catalogs
        (``races``, ``classes``, ``skills``, ``spells``), the attribute
        blocks read from ``datas/attributes.yaml`` (``attribute_blocks``,
        one entry per level-1 entry of the document, plus the first
        block mirrored under the legacy ``attributes`` /
        ``attributes_title`` keys) and the named attribute generation
        strategies.

    Raises:
        YamlLoadError: If a data file is not valid YAML.
        ValueError: If ``datas/attributes.yaml`` is malformed.
    """
    blocks = load_attributes()
    first = blocks[0]
    return {
        "attributes": first["list"],
        "attributes_title": first["title"],
        "attribute_blocks": {block["id"]: block for block in blocks},
        "races": load_data("races.yaml"),
        "classes": load_data("classes.yaml"),
        "skills": load_data("skills.yaml"),
        "spells": load_data("spells.yaml"),
        "strategies": {
            # The attributes are rolled with dice...
            "classic_4d6": FourSixKeepBestStrategy(),
            "3d6": RollStrategy("3d6"),
            "4d6_drop_lowest": RollStrategy("4d6", keep=3),
            # ... while the saving throws are assigned from the class
            # chosen in classes.yaml (no dice draw at creation).
            "class_saves": ClassSavesStrategy(),
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
