"""
Tests for the player character save manager (``utils.character_save``).

Covers directory auto-creation, save/load round-trips, slug-based file
naming, listing, deletion, and corruption handling.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from companion4soloplayer.core.character_tracker import CharacterTracker
from companion4soloplayer.utils.character_save import (
    SAVE_FORMAT_VERSION,
    CharacterSaveManager,
    SavedCharacter,
    default_saves_root,
)
from companion4soloplayer.utils.slugify import Slugify


def test_default_saves_root_is_data_saves_under_project_root() -> None:
    """The default saves root is <project root>/data/saves."""
    root = default_saves_root()
    assert root.name == "saves"
    assert root.parent.name == "data"


def test_save_character_creates_plugin_directory_and_file(tmp_path: Path) -> None:
    """Saving creates the plugin sub-directory and a slug-named YAML file."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()
    character = tracker.create_character("Aragorn", "Ranger", {"body": 14})

    path = manager.save_character(character)

    assert path.is_file()
    assert path.parent == tmp_path / "demo_plugin"
    assert path.name == "aragorn.yaml"
    assert path.parent.is_dir()


def test_save_and_load_round_trip_preserves_all_fields(tmp_path: Path) -> None:
    """A saved character is read back with all its fields intact."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()
    character = tracker.create_character("Dwarf Warrior", "Warrior", {"body": 16, "agility": 10})
    character.current_hp = 22
    character.inventory = ["sword", "shield"]
    character.equipment = ["chainmail"]

    manager.save_character(character)
    reloaded = manager.load_character("dwarf-warrior")

    assert reloaded is not None
    assert reloaded.name == "Dwarf Warrior"
    assert reloaded.character_class == "Warrior"
    assert reloaded.max_hp == 16
    assert reloaded.current_hp == 22
    assert reloaded.stats == {"body": 16, "agility": 10}
    assert reloaded.inventory == ["sword", "shield"]


def test_load_unknown_character_returns_none(tmp_path: Path) -> None:
    """Loading a non-existent slug returns None instead of raising."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    assert manager.load_character("does-not-exist") is None


def test_list_characters_returns_sorted_slugs(tmp_path: Path) -> None:
    """Listing returns the slugs of all saved characters, sorted."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()
    manager.save_character(tracker.create_character("Zebra", "Rogue", {"body": 1}))
    manager.save_character(tracker.create_character("Alice", "Mage", {"mind": 1}))
    manager.save_character(tracker.create_character("Mara", "Cleric", {"body": 1}))

    assert manager.list_characters() == ["alice", "mara", "zebra"]


def test_list_characters_empty_when_directory_missing(tmp_path: Path) -> None:
    """Listing an unused plugin returns an empty list."""
    manager = CharacterSaveManager("unused_plugin", saves_root=tmp_path)
    assert manager.list_characters() == []


def test_delete_character_removes_file_and_reports_success(tmp_path: Path) -> None:
    """Deletion removes the file and returns True; a second call returns False."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()
    manager.save_character(tracker.create_character("Solo", "Warrior", {"body": 1}))

    assert manager.character_exists("solo")
    assert manager.delete_character("solo") is True
    assert manager.character_exists("solo") is False
    assert manager.delete_character("solo") is False


def test_invalid_save_file_raises_value_error(tmp_path: Path) -> None:
    """A corrupted save file raises a ValueError on load."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    file_path = tmp_path / "demo_plugin" / "broken.yaml"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("not: [valid", encoding="utf-8")  # invalid YAML

    with pytest.raises(ValueError, match="Invalid save file"):
        manager.load_character("broken")


def test_slugify_is_used_for_file_naming(tmp_path: Path) -> None:
    """The file name is the slugified character name."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()
    manager.save_character(
        tracker.create_character("Elf Archer (2024)!", "Ranger", {"agility": 17})
    )

    slugger = Slugify()
    slug = slugger("Elf Archer (2024)!")
    assert (tmp_path / "demo_plugin" / f"{slug}.yaml").is_file()


def test_saved_character_model_round_trip() -> None:
    """SavedCharacter serializes and deserializes losslessly."""
    tracker = CharacterTracker()
    character = tracker.create_character("Test", "Warrior", {"body": 10})
    saved = SavedCharacter(
        plugin_name="demo_plugin",
        saved_at=datetime.now(UTC),
        version=SAVE_FORMAT_VERSION,
        character=character,
    )

    restored = SavedCharacter.from_dict(saved.to_dict())
    assert restored.plugin_name == "demo_plugin"
    assert restored.version == SAVE_FORMAT_VERSION
    assert restored.character.name == "Test"
    assert restored.character.stats == {"body": 10}


def test_saved_file_is_structured_yaml_with_metadata(tmp_path: Path) -> None:
    """The file contains plugin, timestamp, version and character blocks."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()
    character = tracker.create_character("Gandalf", "Wizard", {"mind": 18})
    manager.save_character(character)

    content = (tmp_path / "demo_plugin" / "gandalf.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    assert data["plugin_name"] == "demo_plugin"
    assert data["version"] == SAVE_FORMAT_VERSION
    assert isinstance(datetime.fromisoformat(data["saved_at"]), datetime)
    assert data["character"]["name"] == "Gandalf"
    assert data["character"]["character_class"] == "Wizard"
