"""Shared yes/no oracle rule element.

The oracle is a generic solo decision aid: it rolls a die and maps the
result to a "no"/"yes" outcome with optional narrative twists. The
class is identical for every plugin, so it lives in the core package
and is referenced from each plugin ``rules.yaml`` with::

    oracle: !pyclass companion4soloplayer.core.rules:OracleRule
"""

from __future__ import annotations

from companion4soloplayer.core.dice_roller import DiceRoller
from companion4soloplayer.core.yaml_loader import DiceExpression


class OracleRule:
    """Simple yes/no oracle for solo decision making (1d6)."""

    OUTCOMES = {
        1: "no, and complications arise",
        2: "no",
        3: "no",
        4: "yes",
        5: "yes",
        6: "yes, and an extra opportunity arises",
    }

    def __init__(self, *, dice: DiceExpression | str = "1d6") -> None:
        """Initialize the rule.

        Args:
            dice: Dice notation drawn for the oracle answer.
        """
        self.dice = DiceExpression.parse(dice)

    def ask(self, roller: DiceRoller | None = None) -> str:
        """Draw an oracle answer.

        Args:
            roller: Optional dice roller.

        Returns:
            The outcome text for the rolled value.
        """
        roller = roller or DiceRoller()
        total = self.dice.roll(roller)
        return self.OUTCOMES[min(6, max(1, total))]
