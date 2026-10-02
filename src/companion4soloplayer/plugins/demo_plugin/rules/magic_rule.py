"""Magic rule element (arcane casting check based on the mind stat)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from companion4soloplayer.core.dice_roller import DiceRoller
from companion4soloplayer.core.yaml_loader import DiceExpression

from ..data import get_stat


class MagicRule:
    """Arcane casting check based on the caster's mind stat."""

    def __init__(
        self,
        *,
        dice: DiceExpression | str = "1d6",
        difficulty: int = 4,
        mana_cost: int = 1,
        stat: str = "mind",
    ) -> None:
        """Initialize the rule (parameters come from ``rules.yaml``).

        Args:
            dice: Dice notation rolled for the casting check.
            difficulty: Target total needed for success.
            mana_cost: Mana spent on a casting attempt.
            stat: Caster stat added to the roll.
        """
        self.dice = DiceExpression.parse(dice)
        self.difficulty = difficulty
        self.mana_cost = mana_cost
        self.stat = stat

    def cast(
        self,
        spell: str,
        caster: Mapping[str, Any],
        roller: DiceRoller | None = None,
    ) -> dict:
        """Attempt to cast a spell.

        Args:
            spell: Spell or ability name.
            caster: Casting character record.
            roller: Optional dice roller.

        Returns:
            Result record with ``spell``, ``total``, ``difficulty``,
            ``success`` and ``mana_cost`` entries.
        """
        roller = roller or DiceRoller()
        total = self.dice.roll(roller) + get_stat(caster, self.stat)
        return {
            "spell": spell,
            "total": total,
            "difficulty": self.difficulty,
            "success": total >= self.difficulty,
            "mana_cost": self.mana_cost,
        }
