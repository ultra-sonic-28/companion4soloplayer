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


def spell_available(spell: Mapping[str, Any], context: CharacterCreationContext) -> bool:
    """Tell whether a spell may be picked by the current character.

    The filter implements the "choice from a filtered list" model:

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
