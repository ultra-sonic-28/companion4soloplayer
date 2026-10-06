"""
Dice expression module.

Parses and evaluates dice notation (``2d6``, ``1d20+3``, ``d6-1``, ...)
used by the game rules. An expression is pure data: parsing never rolls
anything, and rolling is delegated to
:class:`DiceRoller <companion4soloplayer.core.dice_roller.DiceRoller>`.

This is a generic game mechanism shared by the core rule elements and the
plugins; the YAML ``!dice`` tag of
:mod:`companion4soloplayer.utils.yaml_loader` parses documents into the
value objects defined here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from companion4soloplayer.core.dice_roller import DiceRoller

# Accepts "2d6", "d20", "1d20+3", "4d6-2" (case-insensitive).
_DICE_PATTERN = re.compile(r"^(?P<count>\d*)[dD](?P<sides>\d+)(?P<modifier>[+-]\d+)?$")


class DiceExpressionError(ValueError):
    """Raised when a dice notation is invalid."""


@dataclass(frozen=True)
class DiceExpression:
    """A parsed dice expression such as ``2d6`` or ``1d20+3``.

    Attributes:
        count: Number of dice to roll (at least 1).
        sides: Number of sides per die (at least 2).
        modifier: Value added to (or subtracted from) the dice total.
    """

    count: int
    sides: int
    modifier: int = 0

    @classmethod
    def parse(cls, value: DiceExpression | str) -> DiceExpression:
        """Parse a dice notation string (already-parsed values pass through).

        Args:
            value: Dice notation such as ``2d6``, ``d20``, ``1d20+3``.

        Returns:
            The parsed :class:`DiceExpression`.

        Raises:
            DiceExpressionError: If the notation is invalid.
        """
        if isinstance(value, DiceExpression):
            return value
        match = _DICE_PATTERN.match(value.strip())
        if match is None:
            raise DiceExpressionError(
                f"Invalid dice notation {value!r}: expected '<count>d<sides>[+/-<modifier>]'"
            )
        count = int(match.group("count")) if match.group("count") else 1
        sides = int(match.group("sides"))
        if count < 1 or sides < 2:
            raise DiceExpressionError(
                f"Invalid dice notation {value!r}: count >= 1 and sides >= 2 required"
            )
        modifier = int(match.group("modifier")) if match.group("modifier") else 0
        return cls(count=count, sides=sides, modifier=modifier)

    @property
    def notation(self) -> str:
        """Return the canonical notation (``2d6+1``)."""
        modifier = f"{self.modifier:+d}" if self.modifier else ""
        return f"{self.count}d{self.sides}{modifier}"

    def __str__(self) -> str:
        """Return the canonical notation."""
        return self.notation

    def roll(self, roller: DiceRoller | None = None) -> int:
        """Roll the expression and return the total, modifier included.

        Args:
            roller: Optional dice roller; a fresh one is created when omitted.

        Returns:
            Sum of the dice results plus the modifier.
        """
        _, total = self.roll_detail(roller)
        return total

    def roll_detail(self, roller: DiceRoller | None = None) -> tuple[list[int], int]:
        """Roll the expression and return both the dice results and the total.

        Args:
            roller: Optional dice roller; a fresh one is created when omitted.

        Returns:
            Tuple ``(dice results, total including modifier)``.
        """
        roller = roller or DiceRoller()
        results = roller.roll_dice(self.count, self.sides)
        return results, sum(results) + self.modifier
