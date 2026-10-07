"""Attribute generation strategies of the demo game system.

Plugin strategies extend the core contract
:class:`~companion4soloplayer.core.creation.strategies.AttributeGenerationStrategy`
with the generation methods of the game system. They are registered in
the ``system["strategies"]`` mapping (see :func:`build_system
<companion4soloplayer.plugins.demo_plugin.creation.workflow.build_system>`)
so the workflow YAML can refer to them by name.
"""

from __future__ import annotations

from companion4soloplayer.core.creation.strategies import (
    AttributeGenerationStrategy,
    RollStrategy,
)
from companion4soloplayer.core.dice_roller import DiceRoller


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
