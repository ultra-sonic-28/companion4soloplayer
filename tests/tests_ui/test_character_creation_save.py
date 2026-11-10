"""
Unit tests for the save-on-create hook in ``MainWindow``.

Covers the conversion of a filled creation context into a
:class:`~companion4soloplayer.core.character_tracker.Character` ready to be
persisted by :class:`~companion4soloplayer.utils.character_save.CharacterSaveManager`.
"""

from companion4soloplayer.core.creation import CharacterCreationContext
from companion4soloplayer.ui.main_window import MainWindow


def test_character_from_context_maps_all_creation_fields() -> None:
    """The created character carries identity, class, race, skills, spells and saves."""
    context = CharacterCreationContext()
    context.set("choices.identity.name", "Aragorn")
    context.set("choices.identity.background", "Ranger of the North")
    context.set("choices.race", "Dwarf")
    context.set("choices.class", "Warrior")
    context.set("choices.skills", ["Athletics", "Perception"])
    context.set("choices.spells", [])
    context.set("values.attributes.body", 14)
    context.set("values.attributes.agility", 12)
    context.set("values.save.magic", 12)
    context.set("values.save.poison", 14)

    character = MainWindow._character_from_context(context)

    assert character.name == "Aragorn"
    assert character.background == "Ranger of the North"
    assert character.race == "Dwarf"
    assert character.character_class == "Warrior"
    assert character.skills == ["Athletics", "Perception"]
    assert character.spells == []
    assert character.stats == {"body": 14, "agility": 12}
    assert character.saving_throws == {"magic": 12, "poison": 14}
    assert character.max_hp == 14
    assert character.current_hp == 14


def test_character_from_context_falls_back_on_missing_values() -> None:
    """Missing optional fields fall back on safe defaults."""
    context = CharacterCreationContext()

    character = MainWindow._character_from_context(context)

    assert character.name == "Unnamed"
    assert character.character_class == "Unknown"
    assert character.race == ""
    assert character.background == ""
    assert character.stats == {}
    assert character.saving_throws == {}
    assert character.skills == []
    assert character.spells == []
    assert character.max_hp == 6
    assert character.current_hp == 6


def test_character_from_context_ignores_non_numeric_stats_and_saves() -> None:
    """Only numeric attribute and save values are kept."""
    context = CharacterCreationContext()
    context.set("choices.identity.name", "Test")
    context.set("values.attributes.body", 10)
    context.set("values.attributes.notes", "not a number")
    context.set("values.attributes.flag", True)
    context.set("values.save.magic", 11)
    context.set("values.save.will", "not a number")

    character = MainWindow._character_from_context(context)

    assert character.stats == {"body": 10}
    assert character.saving_throws == {"magic": 11}
