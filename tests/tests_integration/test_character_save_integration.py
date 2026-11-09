"""
Integration tests for the player character save system.

These tests exercise the save manager end-to-end with the real file
system and the real :class:`~companion4soloplayer.utils.slugify.Slugify`,
verifying that a character created through the core tracker can be
persisted, reloaded, and isolated per plugin.
"""

from pathlib import Path

from companion4soloplayer.core.character_tracker import CharacterTracker
from companion4soloplayer.utils.character_save import CharacterSaveManager


def test_character_created_via_tracker_is_persisted_and_reloaded(tmp_path: Path) -> None:
    """A character created by the tracker round-trips through a real save file."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()
    character = tracker.create_character("Aragorn", "Ranger", {"body": 14, "agility": 12})

    save_path = manager.save_character(character)

    # The save directory and file were created automatically.
    assert save_path.is_file()
    assert save_path.parent == tmp_path / "demo_plugin"

    # Reloading yields an equivalent character.
    reloaded = manager.load_character("aragorn")
    assert reloaded is not None
    assert reloaded.name == character.name
    assert reloaded.character_class == character.character_class
    assert reloaded.stats == character.stats


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
    """Re-saving a character overwrites the previous file content."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()
    character = tracker.create_character("Aragorn", "Ranger", {"body": 14})

    manager.save_character(character)
    character.current_hp = 5
    manager.save_character(character)

    # Only one file exists and it holds the updated HP.
    files = list((tmp_path / "demo_plugin").glob("*.yaml"))
    assert len(files) == 1
    assert manager.load_character("aragorn").current_hp == 5
