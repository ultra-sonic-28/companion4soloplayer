"""Availability filters used by the creation steps of the demo system.

The functions are referenced from ``datas/workflow.yaml`` with a
``!pyclass local:...`` reference and resolved against the plugin
package, which re-exports them (see the plugin ``__init__``).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from companion4soloplayer.core.creation.context import CharacterCreationContext

#: Highest spell level a starting character of the demo system may pick.
MAX_STARTING_SPELL_LEVEL = 1


def _chosen_entry(
    catalog_key: str,
    answer_key: str,
    context: CharacterCreationContext,
) -> Mapping[str, Any] | None:
    """Return the catalog entry chosen at ``answer_key``.

    Args:
        catalog_key: Catalog key of the system data (``races``,
            ``classes``).
        answer_key: State path holding the chosen name (``choices.race``,
            ``choices.class``).
        context: Current creation state.

    Returns:
        The chosen catalog entry, or None when nothing is chosen (or
        the game system declares no such catalog).
    """
    chosen = context.peek(answer_key)
    if not isinstance(chosen, str) or not chosen:
        return None
    for entry in context.system.get(catalog_key) or []:
        if isinstance(entry, Mapping) and entry.get("name") == chosen:
            return entry
    return None


def can_cast_spells(context: CharacterCreationContext) -> bool:
    """Tell whether the character is allowed to cast spells.

    The ``can_cast_spells`` flag of ``datas/races.yaml`` and
    ``datas/classes.yaml`` drives the answer: the character may cast as
    soon as the chosen race **or** the chosen class declares the flag.
    With no race and no class chosen yet, nothing may be cast, which
    keeps the spells block of the creation dialog hidden until a
    spellcasting choice is made.

    Args:
        context: Current creation state of the character.

    Returns:
        True when the chosen race or class can cast spells.

    Example:
        >>> from companion4soloplayer.core.creation.context import (
        ...     CharacterCreationContext)
        >>> context = CharacterCreationContext()
        >>> can_cast_spells(context)
        False
        >>> context.set("choices.class", "Wizard")
        >>> can_cast_spells(context)
        True
    """
    race = _chosen_entry("races", "choices.race", context)
    character_class = _chosen_entry("classes", "choices.class", context)
    for entry in (race, character_class):
        if entry is not None and entry.get("can_cast_spells") is True:
            return True
    return False


def skill_available(skill: Mapping[str, Any], context: CharacterCreationContext) -> bool:
    """Tell whether the skills of the catalog may be picked yet.

    The demo system proposes its skill catalog once the player has
    chosen a race **or** a class: at the very start of the creation
    dialog, before any choice, the skill list stays empty.

    Args:
        skill: Skill catalog entry (unused, the catalog is not
            restricted entry by entry).
        context: Current creation state of the character.

    Returns:
        True when a race or a class is already chosen.

    Example:
        >>> from companion4soloplayer.core.creation.context import (
        ...     CharacterCreationContext)
        >>> context = CharacterCreationContext()
        >>> skill_available({"name": "Athletics"}, context)
        False
        >>> context.set("choices.race", "Dwarf")
        >>> skill_available({"name": "Athletics"}, context)
        True
    """
    return bool(context.peek("choices.race") or context.peek("choices.class"))


def spell_available(spell: Mapping[str, Any], context: CharacterCreationContext) -> bool:
    """Tell whether a spell may be picked by the current character.

    The filter implements the "choice from a filtered list" model:

    - the character must be able to cast spells at all (see
      :func:`can_cast_spells`, driven by the ``can_cast_spells`` flag
      of the chosen race/class): otherwise no spell at all is
      proposed;
    - the spell level must not exceed
      :data:`MAX_STARTING_SPELL_LEVEL`;
    - a spell declaring ``classes`` requires the chosen class to be one
      of them (without a chosen class, only classless spells remain);
    - a spell declaring ``requires_skill`` needs that skill in the
      effective skill list (picks **and** rule grants).

    Args:
        spell: Spell catalog entry (``name``, ``level``, ``classes``,
            optional ``requires_skill``...).
        context: Current creation state of the character.

    Returns:
        True when the spell is available for this character.

    Example:
        >>> from companion4soloplayer.core.creation.context import (
        ...     CharacterCreationContext)
        >>> context = CharacterCreationContext()
        >>> context.set("choices.class", "Wizard")
        >>> spell_available({"name": "Spark", "level": 1,
        ...                  "classes": ["Wizard"]}, context)
        True
        >>> spell_available({"name": "Fireball", "level": 2,
        ...                  "classes": ["Wizard"]}, context)
        False
    """
    if not can_cast_spells(context):
        return False
    level = spell.get("level", 1)
    if not isinstance(level, int) or isinstance(level, bool):
        return False
    if level > MAX_STARTING_SPELL_LEVEL:
        return False
    classes = spell.get("classes") or []
    if classes and context.peek("choices.class") not in classes:
        return False
    required = spell.get("requires_skill")
    if required is not None:
        skills = context.effective("values.skills") or []
        if required not in skills:
            return False
    return True
