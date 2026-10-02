"""Character creation rule element (class catalog in classes.yaml)."""

from __future__ import annotations

from typing import Any

from ..data import load_data


class CharacterCreationRule:
    """Create starting characters from the class catalog (classes.yaml)."""

    def __init__(self, *, catalog: str = "classes.yaml") -> None:
        """Initialize the rule.

        Args:
            catalog: YAML file holding the character class catalog.
        """
        self.catalog = catalog

    def list_classes(self) -> list[dict]:
        """List the available character classes.

        Returns:
            The class catalog entries.
        """
        return list(load_data(self.catalog))

    def create(self, class_name: str, character_name: str) -> dict:
        """Create a character from a class of the catalog.

        Args:
            class_name: Class display name (case-insensitive).
            character_name: Name of the new character.

        Returns:
            Character record with ``name``, ``class``, ``stats`` and
            ``abilities`` entries plus ``current_hp`` when the class
            defines body points.

        Raises:
            KeyError: If no class matches ``class_name``.
        """
        for entry in self.list_classes():
            if str(entry.get("name", "")).lower() == class_name.lower():
                stats = dict(entry.get("base_stats", {}))
                abilities = entry.get("special_abilities") or entry.get("abilities") or []
                character: dict[str, Any] = {
                    "name": character_name,
                    "class": entry["name"],
                    "stats": stats,
                    "abilities": list(abilities),
                }
                if isinstance(stats.get("body"), int):
                    character["current_hp"] = stats["body"]
                return character
        raise KeyError(f"Unknown character class {class_name!r}")
