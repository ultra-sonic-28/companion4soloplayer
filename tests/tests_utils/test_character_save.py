"""
Tests for the player character save manager (``utils.character_save``).

Covers directory auto-creation, save/load round-trips, slug-based file
naming, listing, deletion, and corruption handling.
"""

import textwrap
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
    character.race = "Dwarf"
    character.background = "Born under the mountain"
    character.current_hp = 22
    character.inventory = ["sword", "shield"]
    character.equipment = ["chainmail"]
    character.saving_throws = {"magic": 12, "poison": 14}
    character.skills = ["Athletics", "Perception"]
    character.spells = []

    manager.save_character(character)
    reloaded = manager.load_character("dwarf-warrior")

    assert reloaded is not None
    assert reloaded.name == "Dwarf Warrior"
    assert reloaded.character_class == "Warrior"
    assert reloaded.race == "Dwarf"
    assert reloaded.background == "Born under the mountain"
    assert reloaded.max_hp == 16
    assert reloaded.current_hp == 22
    assert reloaded.stats == {"body": 16, "agility": 10}
    assert reloaded.saving_throws == {"magic": 12, "poison": 14}
    assert reloaded.skills == ["Athletics", "Perception"]
    assert reloaded.spells == []
    assert reloaded.inventory == ["sword", "shield"]
    assert reloaded.equipment == ["chainmail"]


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




def test_load_old_version_one_save_loads_with_defaults(tmp_path: Path) -> None:
    """A save file written with format version 1 still loads with defaults.

    New fields (race, background, skills, spells, saving_throws) are
    absent from old files and fall back on their pydantic defaults.
    """
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    file_path = tmp_path / "demo_plugin" / "old-hero.yaml"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    old_save = textwrap.dedent("""\
        plugin_name: demo_plugin
        saved_at: 2026-01-01T00:00:00+00:00
        version: "1"
        character:
          name: Old Hero
          character_class: Warrior
          max_hp: 20
          current_hp: 15
          stats:
            body: 16
          inventory: []
          equipment: []
        """)
    file_path.write_text(old_save, encoding="utf-8")

    character = manager.load_character("old-hero")

    assert character is not None
    assert character.name == "Old Hero"
    assert character.character_class == "Warrior"
    assert character.max_hp == 20
    assert character.current_hp == 15
    assert character.stats == {"body": 16}
    # New fields fall back on their defaults.
    assert character.race == ""
    assert character.background == ""
    assert character.saving_throws == {}
    assert character.skills == []
    assert character.spells == []


def test_saved_character_model_round_trip() -> None:
    """SavedCharacter serializes and deserializes losslessly."""
    tracker = CharacterTracker()
    character = tracker.create_character("Test", "Warrior", {"body": 10})
    character.race = "Human"
    character.background = "A simple test"
    character.saving_throws = {"magic": 11}
    character.skills = ["Athletics"]
    character.spells = ["Fireball"]
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
    assert restored.character.race == "Human"
    assert restored.character.background == "A simple test"
    assert restored.character.saving_throws == {"magic": 11}
    assert restored.character.skills == ["Athletics"]
    assert restored.character.spells == ["Fireball"]


def test_saved_file_is_structured_yaml_with_metadata(tmp_path: Path) -> None:
    """The file contains plugin, timestamp, version and character blocks."""
    manager = CharacterSaveManager("demo_plugin", saves_root=tmp_path)
    tracker = CharacterTracker()
    character = tracker.create_character("Gandalf", "Wizard", {"mind": 18})
    character.race = "Human"
    character.background = "Wise wanderer"
    character.saving_throws = {"magic": 15}
    character.skills = ["Arcana"]
    character.spells = ["Fireball", "Magic Missile"]
    manager.save_character(character)

    content = (tmp_path / "demo_plugin" / "gandalf.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    assert data["plugin_name"] == "demo_plugin"
    assert data["version"] == SAVE_FORMAT_VERSION
    assert isinstance(datetime.fromisoformat(data["saved_at"]), datetime)
    assert data["character"]["name"] == "Gandalf"
    assert data["character"]["character_class"] == "Wizard"
    assert data["character"]["race"] == "Human"
    assert data["character"]["background"] == "Wise wanderer"
    assert data["character"]["saving_throws"] == {"magic": 15}
    assert data["character"]["skills"] == ["Arcana"]
    assert data["character"]["spells"] == ["Fireball", "Magic Missile"]
