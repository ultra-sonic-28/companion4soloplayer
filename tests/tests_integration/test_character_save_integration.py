"""
Integration tests for the player character save system.

These tests exercise the save manager end-to-end with the real file
system and the real :class:`~companion4soloplayer.utils.slugify.Slugify`,
verifying that a character created through the core tracker can be
persisted, reloaded, and isolated per plugin.
"""

from pathlib import Path

import pytest

from companion4soloplayer.core.character_tracker import CharacterTracker
from companion4soloplayer.utils.character_save import (
    CharacterSaveManager,
    OverwriteConfirmationError,
)


def test_character_created_via_tracker_is_persisted_and_reloaded(tmp_path: Path) -> None:
    """A character created by the tracker round-trips through a real save file."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()
    character = tracker.create_character("Aragorn", "Ranger", {"body": 14, "agility": 12})
    character.race = "Dwarf"
    character.background = "Ranger of the North"
    character.skills = ["Athletics", "Perception"]
    character.spells = []
    character.saving_throws = {"magic": 12, "poison": 14}

    save_path = manager.save_character(character)

    # The save directory and file were created automatically.
    assert save_path.is_file()
    assert save_path.parent == tmp_path / "demo_plugin"

    # Reloading yields an equivalent character.
    reloaded = manager.load_character("aragorn")
    assert reloaded is not None
    assert reloaded.name == character.name
    assert reloaded.character_class == character.character_class
    assert reloaded.race == character.race
    assert reloaded.background == character.background
    assert reloaded.skills == character.skills
    assert reloaded.spells == character.spells
    assert reloaded.saving_throws == character.saving_throws
    assert reloaded.stats == character.stats


def test_spellcasting_character_persists_spells(tmp_path: Path) -> None:
    """A character with selected spells persists them in the save file."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()
    character = tracker.create_character("Gandalf", "Wizard", {"mind": 18})
    character.race = "Human"
    character.spells = ["Fireball", "Magic Missile"]

    manager.save_character(character)
    reloaded = manager.load_character("gandalf")

    assert reloaded is not None
    assert reloaded.spells == ["Fireball", "Magic Missile"]


def test_characters_are_isolated_per_plugin(tmp_path: Path) -> None:
    """Two plugins with same-named characters do not collide."""
    demo = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    other = CharacterSaveManager("other_plugin", saves_root=tmp_path)
    demo_tracker = CharacterTracker()
    other_tracker = CharacterTracker()

    demo.save_character(demo_tracker.create_character("Aragorn", "Ranger", {"body": 14}))
    other.save_character(other_tracker.create_character("Aragorn", "Warrior", {"body": 18}))

    assert demo.list_characters() == ["aragorn"]
    assert other.list_characters() == ["aragorn"]
    assert demo.load_character("aragorn").character_class == "Ranger"
    assert other.load_character("aragorn").character_class == "Warrior"


def test_update_and_resave_overwrites_existing_file(tmp_path: Path) -> None:
    """Re-saving a character overwrites the previous file content.

    The second save must pass ``overwrite=True`` because the file already
    exists and the manager no longer silently replaces it.
    """
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()
    character = tracker.create_character("Aragorn", "Ranger", {"body": 14})

    manager.save_character(character)
    character.current_hp = 5
    manager.save_character(character, overwrite=True)

    # Only one file exists and it holds the updated HP.
    files = list((tmp_path / "demo_plugin").glob("*.yaml"))
    assert len(files) == 1
    assert manager.load_character("aragorn").current_hp == 5


def test_save_over_existing_file_raises_overwrite_confirmation_needed(
    tmp_path: Path,
) -> None:
    """Saving over an existing file without overwrite=True raises the exception.

    The exception carries all data needed to build the comparison dialog.
    """
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)

    old_tracker = CharacterTracker()
    old_char = old_tracker.create_character("Aragorn", "Ranger", {"body": 14})
    old_char.race = "Dwarf"
    manager.save_character(old_char)

    new_tracker = CharacterTracker()
    new_char = new_tracker.create_character("Aragorn", "Warrior", {"body": 18})
    new_char.race = "Human"

    with pytest.raises(OverwriteConfirmationError) as exc_info:
        manager.save_character(new_char)

    exc = exc_info.value
    assert exc.file_path == tmp_path / "demo_plugin" / "aragorn.yaml"
    assert exc.old_character.race == "Dwarf"
    assert exc.old_character.character_class == "Ranger"
    assert exc.new_character.race == "Human"
    assert exc.new_character.character_class == "Warrior"
    assert exc.old_saved_at != ""


def test_overwrite_true_succeeds_after_confirmation_exception(tmp_path: Path) -> None:
    """After catching OverwriteConfirmationError, overwrite=True succeeds.

    This simulates the user clicking "Overwrite" in the dialog.
    """
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)

    old_tracker = CharacterTracker()
    old_char = old_tracker.create_character("Aragorn", "Ranger", {"body": 14})
    manager.save_character(old_char)

    new_tracker = CharacterTracker()
    new_char = new_tracker.create_character("Aragorn", "Warrior", {"body": 18})
    new_char.current_hp = 7

    # First attempt raises the exception
    with pytest.raises(OverwriteConfirmationError):
        manager.save_character(new_char)

    # Second attempt with overwrite=True succeeds
    path = manager.save_character(new_char, overwrite=True)
    assert path.is_file()

    reloaded = manager.load_character("aragorn")
    assert reloaded is not None
    assert reloaded.character_class == "Warrior"
    assert reloaded.current_hp == 7


def test_save_new_character_does_not_raise(tmp_path: Path) -> None:
    """Saving a brand-new character (no existing file) works as before."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()

    character = tracker.create_character("Legolas", "Ranger", {"agility": 16})
    character.race = "Elf"

    path = manager.save_character(character)

    assert path.is_file()
    assert path.name == "legolas.yaml"
    reloaded = manager.load_character("legolas")
    assert reloaded is not None
    assert reloaded.name == "Legolas"
    assert reloaded.race == "Elf"


def test_overwrite_error_carries_plugin_versions_end_to_end(tmp_path: Path) -> None:
    """Saving over an existing file yields an overwrite error carrying both
    plugin versions: the old one read from the saved file and the new one
    from the plugin configuration registry."""
    from companion4soloplayer.utils.plugin_config import (
        PluginConfigRegistry,
        VERSION_SECTION,
    )

    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)

    PluginConfigRegistry.reset()
    try:
        # Save the old character while the registry is empty: the file
        # records the default version.
        old_tracker = CharacterTracker()
        old_char = old_tracker.create_character("Aragorn", "Ranger", {"body": 14})
        old_char.race = "Dwarf"
        manager.save_character(old_char)

        # Register a newer plugin version, then try to save again.
        PluginConfigRegistry.instance().register(
            "demo_plugin", {VERSION_SECTION: "3.2.1"}
        )

        new_tracker = CharacterTracker()
        new_char = new_tracker.create_character("Aragorn", "Warrior", {"body": 18})

        with pytest.raises(OverwriteConfirmationError) as exc_info:
            manager.save_character(new_char)

        exc = exc_info.value
        # Old version is read from the saved file.
        assert exc.old_version == "0.0.0"
        # New version comes from the plugin configuration registry.
        assert exc.new_version == "3.2.1"
    finally:
        PluginConfigRegistry.reset()
