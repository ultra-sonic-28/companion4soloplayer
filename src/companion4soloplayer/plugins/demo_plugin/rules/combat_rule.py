"""Opposed-roll combat rule element (see the ``combat`` rule section)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from companion4soloplayer.core.dice_expression import DiceExpression
from companion4soloplayer.core.dice_roller import DiceRoller

from ..data import get_stat


class CombatRule:
    """Opposed-roll combat resolution (see the ``combat`` rule section).

    The attacker rolls ``attack_dice`` plus their attack stat; the
    defender rolls ``defense_dice`` (when set) plus their defense stat.
    A non-negative margin deals ``base_damage`` plus the margin, capped
    at ``max_damage``; a negative margin deals no damage.
    """

    def __init__(
        self,
        *,
        attack_dice: DiceExpression | str | None = None,
        defense_dice: DiceExpression | str | None = None,
        attack_stat: str | list[str] = "attack",
        defense_stat: str | list[str] = "defense",
        base_damage: int = 1,
        max_damage: int = 3,
    ) -> None:
        """Initialize the rule (parameters come from ``rules.yaml``).

        Args:
            attack_dice: Dice notation rolled by the attacker.
            defense_dice: Dice notation rolled by the defender, or None
                when the defense value is static.
            attack_stat: Attacker stat name or ordered fallback list.
            defense_stat: Defender stat name or ordered fallback list.
            base_damage: Damage dealt on any successful attack.
            max_damage: Upper bound of the damage per attack.
        """
        self.attack_dice = DiceExpression.parse(attack_dice or "1d6")
        self.defense_dice = DiceExpression.parse(defense_dice) if defense_dice else None
        self.attack_stat = attack_stat
        self.defense_stat = defense_stat
        self.base_damage = base_damage
        self.max_damage = max_damage

    def resolve(
        self,
        attacker: Mapping[str, Any],
        defender: Mapping[str, Any],
        roller: DiceRoller | None = None,
    ) -> dict:
        """Resolve one attack of ``attacker`` against ``defender``.

        Args:
            attacker: Attacking character or monster record.
            defender: Defending character or monster record.
            roller: Optional dice roller (a fresh one when omitted).

        Returns:
            Result record with ``attack``, ``defense``, ``net``,
            ``success`` and ``damage`` entries.
        """
        roller = roller or DiceRoller()
        attack_score = self.attack_dice.roll(roller) + get_stat(attacker, self.attack_stat)
        defense_score = get_stat(defender, self.defense_stat)
        if self.defense_dice is not None:
            defense_score += self.defense_dice.roll(roller)
        net = attack_score - defense_score
        success = net >= 0
        damage = min(self.max_damage, self.base_damage + max(0, net)) if success else 0
        return {
            "attack": attack_score,
            "defense": defense_score,
            "net": net,
            "success": success,
            "damage": damage,
        }
