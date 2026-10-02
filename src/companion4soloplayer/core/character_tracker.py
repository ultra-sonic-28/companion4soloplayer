"""
Character tracking module.
Manages character stats, inventory, and status.
"""

from pydantic import BaseModel, Field


class Character(BaseModel):
    """Representation of a game character."""
    name: str = Field(..., description="Character name")
    character_class: str = Field(..., description="Character class")
    max_hp: int = Field(..., description="Maximum hit points")
    current_hp: int = Field(..., description="Current hit points")
    stats: dict[str, int] = Field(default_factory=dict, description="Character stats")
    inventory: list[str] = Field(default_factory=list, description="Inventory items")
    equipment: list[str] = Field(default_factory=list, description="Equipped items")


class CharacterTracker:
    """Manages multiple characters in a party."""

    def __init__(self) -> None:
        """Initialize the character tracker."""
        self.characters: dict[str, Character] = {}

    def create_character(
        self,
        name: str,
        character_class: str,
        stats: dict[str, int]
    ) -> Character:
        """Create a new character.

        Args:
            name: Character name
            character_class: Character class
            stats: Character statistics

        Returns:
            The created Character object

        Raises:
            ValueError: If character name already exists
        """
        if name in self.characters:
            raise ValueError(f"Character '{name}' already exists")

        max_hp = stats.get('body', 6)
        character = Character(
            name=name,
            character_class=character_class,
            max_hp=max_hp,
            current_hp=max_hp,
            stats=stats
        )
        self.characters[name] = character
        return character

    def get_character(self, name: str) -> Character | None:
        """Get a character by name.

        Args:
            name: Character name

        Returns:
            Character object or None if not found
        """
        return self.characters.get(name)

    def remove_character(self, name: str) -> bool:
        """Remove a character from the party.

        Args:
            name: Character name

        Returns:
            True if character was removed, False if not found
        """
        if name in self.characters:
            del self.characters[name]
            return True
        return False
