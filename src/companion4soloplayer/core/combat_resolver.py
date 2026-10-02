"""
Combat resolution module.
Handles combat mechanics and damage calculation.
"""

from companion4soloplayer.core.character_tracker import Character
from companion4soloplayer.core.dice_roller import DiceRoller


class CombatResolver:
    """Resolves combat encounters."""

    def __init__(self) -> None:
        """Initialize the combat resolver."""
        self.dice_roller = DiceRoller()

    def calculate_damage(
        self,
        attacker: Character,
        defender: Character,
        weapon_damage: int
    ) -> int:
        """Calculate damage dealt in an attack.

        Args:
            attacker: Attacking character
            defender: Defending character
            weapon_damage: Base weapon damage

        Returns:
            Damage dealt after defense
        """
        strength_modifier = attacker.stats.get('strength', 0)
        base_damage = weapon_damage + strength_modifier

        defense = defender.stats.get('armor', 0)
        damage = max(0, base_damage - defense)

        return damage

    def apply_damage(self, character: Character, damage: int) -> int:
        """Apply damage to a character.

        Args:
            character: Character to damage
            damage: Damage amount

        Returns:
            Remaining hit points
        """
        character.current_hp = max(0, character.current_hp - damage)
        return character.current_hp
