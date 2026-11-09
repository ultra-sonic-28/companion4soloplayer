"""
Unit tests for the save-on-create hook in ``MainWindow``.

Covers the conversion of a filled creation context into a
:class:`~companion4soloplayer.core.character_tracker.Character` ready to be
persisted by :class:`~companion4soloplayer.utils.character_save.CharacterSaveManager`.
"""

from companion4soloplayer.core.creation import CharacterCreationContext
from companion4soloplayer.ui.main_window import MainWindow


def test_character_from_context_maps_name_class_and_attributes() -> None:
    """The created character carries the identity, class and attributes."""
    context = CharacterCreationContext()
    context.set("choices.identity.name", "Aragorn")
    context.set("choices.identity.background", "Ranger of the North")
    context.set("choices.class", "Ranger")
    context.set("values.attributes.body", 14)
    context.set("values.attributes.agility", 12)

    character = MainWindow._character_from_context(context)

    assert character.name == "Aragorn"
    assert character.character_class == "Ranger"
    assert character.stats == {"body": 14, "agility": 12}
    assert character.max_hp == 14
    assert character.current_hp == 14


def test_character_from_context_falls_back_on_missing_values() -> None:
    """Missing optional fields fall back on safe defaults."""
    context = CharacterCreationContext()

    character = MainWindow._character_from_context(context)

    assert character.name == "Unnamed"
    assert character.character_class == "Unknown"
    assert character.stats == {}
    assert character.max_hp == 6
    assert character.current_hp == 6


def test_character_from_context_ignores_non_numeric_stats() -> None:
    """Only numeric attribute values are kept in the character stats."""
    context = CharacterCreationContext()
    context.set("choices.identity.name", "Test")
    context.set("values.attributes.body", 10)
    context.set("values.attributes.notes", "not a number")
    context.set("values.attributes.flag", True)

    character = MainWindow._character_from_context(context)

    assert character.stats == {"body": 10}
