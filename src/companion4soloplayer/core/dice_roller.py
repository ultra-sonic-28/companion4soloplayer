"""
Dice rolling module.
Handles all dice rolling mechanics.
"""

import random


class DiceRoller:
    """Handles dice rolling operations."""

    def __init__(self, seed: int | None = None) -> None:
        """Initialize the dice roller.

        Args:
            seed: Optional random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)

    def roll_dice(self, count: int, sides: int) -> list[int]:
        """Roll multiple dice.

        Args:
            count: Number of dice to roll
            sides: Number of sides on each die

        Returns:
            List of dice results

        Raises:
            ValueError: If count or sides is less than 1
        """
        if count < 1:
            raise ValueError("Count must be at least 1")
        if sides < 1:
            raise ValueError("Sides must be at least 1")

        return [random.randint(1, sides) for _ in range(count)]

    def roll_single(self, sides: int) -> int:
        """Roll a single die.

        Args:
            sides: Number of sides on the die

        Returns:
            Die result
        """
        return random.randint(1, sides)

    def roll_with_modifier(self, count: int, sides: int, modifier: int) -> tuple[list[int], int]:
        """Roll dice with a modifier.

        Args:
            count: Number of dice to roll
            sides: Number of sides on each die
            modifier: Modifier to add to total

        Returns:
            Tuple of (dice results, total with modifier)
        """
        results = self.roll_dice(count, sides)
        total = sum(results) + modifier
        return results, total
