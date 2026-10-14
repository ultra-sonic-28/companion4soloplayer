"""Attribute generation strategies of the demo game system.

Plugin strategies extend the core contract
:class:`~companion4soloplayer.core.creation.strategies.AttributeGenerationStrategy`
with the generation methods of the game system. They are registered in
the ``system["strategies"]`` mapping (see :func:`build_system
<companion4soloplayer.plugins.demo_plugin.creation.workflow.build_system>`)
so the workflow YAML can refer to them by name:

- ``classic_4d6``: roll 4d6, drop the lowest die (the attributes);
- ``class_saves``: assign the saving throws declared by the chosen
  class, without any dice draw (the saving throws).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from companion4soloplayer.core.creation.context import CharacterCreationContext
from companion4soloplayer.core.creation.steps.base import StepConfigurationError
from companion4soloplayer.core.creation.strategies import (
    AttributeGenerationStrategy,
    RollStrategy,
)
from companion4soloplayer.core.dice_roller import DiceRoller

#: Saving throws assigned while no class is chosen (or an unknown one).
DEFAULT_SAVE = 10


class FourSixKeepBestStrategy(AttributeGenerationStrategy):
    """Roll 4d6 and keep the three highest dice.

    The classic method of the demo system: each attribute rolls four
    six-sided dice and drops the lowest one, giving values between 3
    and 18 with a slighter higher average than a plain 3d6.

    Example:
        >>> from companion4soloplayer.core.dice_roller import DiceRoller
        >>> strategy = FourSixKeepBestStrategy()
        >>> 3 <= strategy.roll("strength", DiceRoller(seed=7)) <= 18
        True
    """

    def __init__(self) -> None:
        """Initialize the strategy (4d6, keep the 3 best dice)."""
        self._roll = RollStrategy("4d6", keep=3)

    def roll(self, attribute: str, roller: DiceRoller) -> int:
        """Roll 4d6 and return the sum of the three highest dice.

        Args:
            attribute: Attribute name (unused by this method).
            roller: Dice roller to use.

        Returns:
            The generated value, between 3 and 18.
        """
        return self._roll.roll(attribute, roller)


class ClassSavesStrategy(AttributeGenerationStrategy):
    """Assign the saving throws declared by the chosen class.

    No dice are drawn during the creation: the base value of every
    saving throw comes from the ``save`` mapping of the class entry in
    ``classes.yaml``::

        - name: Adventurer
          save:
            poison: 16
            magic: 19

    The race and class bonuses declared by ``creation_rules.yaml``
    (``+2 poison save for a Dwarf``, ...) are layered on top of that
    base by the rules engine, so this strategy only produces the base
    values.

    Until a class is chosen (the class may stay undefined) the neutral
    :data:`DEFAULT_SAVE` value is assigned.

    Args:
        default: Value assigned when no class applies.

    Example:
        >>> from companion4soloplayer.core.creation import (
        ...     CharacterCreationContext)
        >>> context = CharacterCreationContext(
        ...     system={"classes": [{"name": "Adventurer",
        ...                          "save": {"poison": 16, "magic": 19}}]})
        >>> context.set("choices.class", "Adventurer")
        >>> ClassSavesStrategy().roll_for("magic", DiceRoller(), context)
        19
    """

    def __init__(self, default: int = DEFAULT_SAVE) -> None:
        """Initialize the strategy.

        Args:
            default: Value assigned when no class applies.
        """
        self.default = int(default)

    def roll(self, attribute: str, roller: DiceRoller) -> int:
        """Return the neutral value (no creation state available).

        Args:
            attribute: Attribute name (unused by this method).
            roller: Dice roller (unused: no draw at all).

        Returns:
            The default saving throw.
        """
        return self.default

    def roll_for(
        self,
        attribute: str,
        roller: DiceRoller,
        context: CharacterCreationContext,
    ) -> int:
        """Return the saving throw of ``attribute`` for the chosen class.

        Args:
            attribute: Saving throw name (``poison``, ``magic``...).
            roller: Dice roller (unused: no draw at all).
            context: Current creation state (reads ``choices.class``
                and the ``classes`` catalog of ``context.system``).

        Returns:
            The base saving throw declared by the class, or the
            default value while no class is chosen.

        Raises:
            StepConfigurationError: If the chosen class declares no
                ``save`` mapping or no value for this saving throw.
        """
        name = context.peek("choices.class")
        if not isinstance(name, str) or not name.strip():
            return self.default
        entry = _class_entry(context.system.get("classes"), name.strip())
        if entry is None:
            # A class outside of the catalog stays unassigned.
            return self.default
        saves = entry.get("save")
        if not isinstance(saves, Mapping):
            raise StepConfigurationError(
                f"Class {name!r} declares no 'save' mapping of base saving throws"
            )
        value = saves.get(attribute)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise StepConfigurationError(
                f"Class {name!r} declares no numeric saving throw for {attribute!r} "
                f"(got {value!r})"
            )
        return int(value)


def _class_entry(catalog: Any, name: str) -> Mapping[str, Any] | None:
    """Return the entry of ``name`` in the class catalog.

    Args:
        catalog: Raw ``classes`` catalog of ``context.system``
            (sequence of mappings declaring a ``name``).
        name: Name of the wanted class.

    Returns:
        The matching class entry, or None when the catalog holds no
        such class (a missing or malformed catalog behaves the same).
    """
    if isinstance(catalog, (str, bytes)) or not isinstance(catalog, Sequence):
        return None
    for entry in catalog:
        if isinstance(entry, Mapping) and entry.get("name") == name:
            return entry
    return None
