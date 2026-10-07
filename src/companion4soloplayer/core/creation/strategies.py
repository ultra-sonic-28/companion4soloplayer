"""Attribute generation strategies.

A strategy knows how to produce the *base* value of one attribute.
The :class:`~companion4soloplayer.core.creation.steps.attributes.AttributeGenerationStep`
resolves the configured strategy (instance, name looked up in
``context.system["strategies"]`` or class to instantiate) and calls it
once per randomly generated attribute; manual and mixed generation are
handled by the step itself.

Strategies are pluggable: plugins subclass
:class:`AttributeGenerationStrategy` to implement the methods of their
game system (see
``companion4soloplayer.plugins.demo_plugin.creation.strategies``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from companion4soloplayer.core.dice_expression import DiceExpression
from companion4soloplayer.core.dice_roller import DiceRoller


class AttributeGenerationStrategy(ABC):
    """Contract of the attribute generation strategies."""

    @abstractmethod
    def roll(self, attribute: str, roller: DiceRoller) -> int:
        """Generate the base value of one attribute.

        Args:
            attribute: Attribute name (strategies may adapt, for
                example by capping a value per attribute).
            roller: Dice roller to use (injectable for reproducible
                rolls).

        Returns:
            The generated base value.
        """
        ...


class RollStrategy(AttributeGenerationStrategy):
    """Sum dice results, optionally keeping only the best/worst dice.

    The classic "roll 4d6 and keep the three highest" method is
    ``RollStrategy("4d6", keep=3)``; a plain "3d6" is
    ``RollStrategy("3d6")``.

    Args:
        dice: Dice notation to roll (``3d6``, ``4d6-2``...). The
            modifier applies to the final total.
        keep: Number of dice kept in the sum (None = keep them all).
        keep_best: When True the highest dice are kept, otherwise the
            lowest ones.

    Raises:
        DiceExpressionError: If the notation is invalid.
        ValueError: If ``keep`` is out of the ``1..count`` range.

    Example:
        >>> from companion4soloplayer.core.dice_roller import DiceRoller
        >>> strategy = RollStrategy("4d6", keep=3)
        >>> 3 <= strategy.roll("strength", DiceRoller(seed=0)) <= 18
        True
    """

    def __init__(
        self,
        dice: DiceExpression | str = "4d6",
        *,
        keep: int | None = None,
        keep_best: bool = True,
    ) -> None:
        """Initialize the strategy.

        Args:
            dice: Dice notation to roll.
            keep: Number of dice kept in the sum.
            keep_best: Keep the highest (True) or lowest (False) dice.
        """
        self.dice = DiceExpression.parse(dice)
        if keep is not None and not 1 <= keep <= self.dice.count:
            raise ValueError(
                f"keep must be between 1 and {self.dice.count} (the rolled dice count), got {keep}"
            )
        self.keep = keep
        self.keep_best = keep_best

    def roll(self, attribute: str, roller: DiceRoller) -> int:
        """Roll the dice and return the generated value.

        Args:
            attribute: Attribute name (unused by this generic
                strategy, kept for the common contract).
            roller: Dice roller to use.

        Returns:
            The sum of the kept dice plus the expression modifier.
        """
        _, total = self.roll_detail(attribute, roller)
        return total

    def roll_detail(self, attribute: str, roller: DiceRoller) -> tuple[list[int], int]:
        """Roll the dice and return both the raw rolls and the total.

        Args:
            attribute: Attribute name (unused by this generic
                strategy, kept for the common contract).
            roller: Dice roller to use.

        Returns:
            Tuple ``(kept dice, total including the modifier)``.
        """
        results = roller.roll_dice(self.dice.count, self.dice.sides)
        kept = results
        if self.keep is not None:
            kept = sorted(results, reverse=self.keep_best)[: self.keep]
        return list(kept), sum(kept) + self.dice.modifier


class ConstantStrategy(AttributeGenerationStrategy):
    """Always return the same value (fixed arrays, system defaults).

    Args:
        value: Value returned for every attribute.

    Example:
        >>> ConstantStrategy(10).roll("mind", DiceRoller())
        10
    """

    def __init__(self, value: int) -> None:
        """Initialize the strategy.

        Args:
            value: Fixed value returned for every attribute.
        """
        self.value = int(value)

    def roll(self, attribute: str, roller: DiceRoller) -> int:
        """Return the fixed value.

        Args:
            attribute: Attribute name (unused).
            roller: Dice roller (unused).

        Returns:
            The configured value.
        """
        return self.value
