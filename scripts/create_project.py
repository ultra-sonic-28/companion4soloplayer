#!/usr/bin/env python3
"""
C4SP - Automatic project structure creation script.
Run this script to create the whole tree and base files.

Generated layout (src layout):

    companion4soloplayer/
    ├── src/companion4soloplayer/                # Python sources (importable package)
    │   ├── main.py                              # Main entry point for Companion4SoloPlayer
    │   ├── core/                                # Generic engine
    │   │   └── rules/                           # Shared rule elements
    │   ├── plugins/                             # Game-specific modules
    │   │   └── demo_plugin/                     # Demo plugin
    │   │       ├── rules/                       # Plugin specific rules
    │   │       └── datas/                       # Plugin specific datas
    │   └── ui/                                  # User interface
    │       └── dialogs/                         # Dialog windows
    ├── companion4soloplayer.spec                # PyInstaller build recipe
    ├── companion4soloplayer.code-workspace      # VS Code workspace file
    ├── pyproject.toml                           # Project configuration
    ├── README.md                                # Main README with disclaimer
    ├── CONTEXT.md                               # Complete development guide
    ├── LICENSE                                  # MIT license
    ├── .gitignore                               # Git ignore
    ├── .vscode/                                 # Visual Studio Code workspace settings
    ├── assets/                                  # Shared assets (CC0 only)
    ├── data/                                    # User data
    ├── tests/                                   # Tests folders
    |   ├── test_core/                           # Core unit tests
    |   ├── test_ui/                             # Core UI tests
    |   └── test_plugins/                        # Plugins tests
    ├── docs/                                    # Technical documentation
    ├── scripts/                                 # Project scripts
    ├── build/                                   # Build folder, PyInstaller output (generated)
    └── dist/                                    # Release folder, PyInstaller output (generated)
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from string import Template
from typing import TextIO

_RESET = "\x1b[0m"

_TITLE_STYLE = "97;44"  # white on blue
_STEP_STYLE = "97;44"  # white on blue
_WARNING_STYLE = "97;48;5;208"  # white on orange (256-color)
_SUCCESS_STYLE = "97;42"  # white on green
_CHECK_STYLE = "32;49"  # green on the terminal default background
_ERROR_STYLE = "97;41"  # white on red

_TITLE_WIDTH = 85  # total width of the boxed title banner

# ---------------------------------------------------------------------------
# Destination mapping
# ---------------------------------------------------------------------------
# Python sources live in the importable package "src/companion4soloplayer";
# project-root files (README, LICENSE, ...) stay at the repository root.
# PATH_RULES maps a logical file path prefix to its destination prefix in
# the generated project tree. resolve_destination() walks these rules in
# order and rewrites the first matching prefix.
# ---------------------------------------------------------------------------

SRC_PACKAGE = "src/companion4soloplayer"
SRC_TESTS = "tests"
SRC_SCRIPTS = "scripts"

PATH_RULES: list[tuple[str, str]] = [
    # (source prefix, destination prefix)
    ("main.py", f"{SRC_PACKAGE}/main.py"),
    ("core/", f"{SRC_PACKAGE}/core/"),
    ("plugins/", f"{SRC_PACKAGE}/plugins/"),
    ("ui/", f"{SRC_PACKAGE}/ui/"),
    ("tests_core", f"{SRC_TESTS}/tests_core"),
    ("tests_plugins", f"{SRC_TESTS}/tests_plugins"),
    ("tests_ui", f"{SRC_TESTS}/tests_ui"),
    ("companion4soloplayer/", f"{SRC_PACKAGE}/"),
    # Project-root files: kept at the repository root (explicit, no prefix)
    ("README.md", "README.md"),
    ("CONTEXT.md", "CONTEXT.md"),
    ("LICENSE", "LICENSE"),
    (".gitignore", ".gitignore"),
    ("pyproject.toml", "pyproject.toml"),
    ("companion4soloplayer.spec", "companion4soloplayer.spec"),
    ("pyproject.toml", "pyproject.toml"),
    # Documentation configuration files
    ("mkdocs.yml", "mkdocs.yml"),
    # Scripts (Powershell and others, with or without prefix)
    ("make_icon.py", f"{SRC_SCRIPTS}/make_icon.py"),
    ("resize_logo.py", f"{SRC_SCRIPTS}/resize_logo.py"),
    ("compile_plugins.py", f"{SRC_SCRIPTS}/compile_plugins.py"),
    # Editor settings (Visual Studio Code workspace)
    (".vscode/settings.json", ".vscode/settings.json"),
    ("companion4soloplayer.code-workspace", "companion4soloplayer.code-workspace"),
]

# Files and directories that must survive a cleanup performed by this
# script. The .git directory holds the version control history: it can
# never be regenerated and must never be deleted by a cleanup.
PRESERVED_FILES = [
    "scripts/create_project.py",
    "assets/icons/logo-512x512.png",
    ".bintools",
    ".git",
]

# Artifacts telling the project has already been generated: the presence
# of any of them in the project directory means create_project.py already
# ran once. The scripts/ directory only legitimately holds
# create_project.py, hence the two generated scripts act as markers too.
GENERATED_ARTIFACTS = [
    f"{SRC_PACKAGE}",
    ".vscode",
    "CONTEXT.md",
    "LICENSE",
    ".gitignore",
    "pyproject.toml",
    "companion4soloplayer.spec",
    "companion4soloplayer.code-workspace",
    f"{SRC_SCRIPTS}/make_icon.py",
    f"{SRC_SCRIPTS}/resize_logo.py",
    f"{SRC_SCRIPTS}/compile_plugins.py",
]


@dataclass(frozen=True)
class DeletionDisplayRule:
    max_depth: int          # 0 = completely hide, 1 = root folder only, etc.
    show_root: bool = True  # Show at least the root folder?


SUPPRESS_DELETION_DETAILS: dict[str, DeletionDisplayRule] = {
    ".nox":        DeletionDisplayRule(max_depth=2),
    ".ruff_cache": DeletionDisplayRule(max_depth=1),
    ".mypy_cache": DeletionDisplayRule(max_depth=1),
    "htmlcov":     DeletionDisplayRule(max_depth=1),
    "build":       DeletionDisplayRule(max_depth=1),
    "dist":        DeletionDisplayRule(max_depth=1),
    ".venv":       DeletionDisplayRule(max_depth=0),  # Fully hidden
    "__pycache__": DeletionDisplayRule(max_depth=0),  # Fully hidden
}


def _supports_colors(
    stream: TextIO,
) -> bool:
    """Return whether the stream should receive ANSI colors.

    Colors are disabled when the output is redirected (pipes,
    CI logs, test captures) unless FORCE_COLOR is set, and can
    be forced off with the standard NO_COLOR convention.
    """

    if os.environ.get("NO_COLOR"):
        return False

    if os.environ.get("FORCE_COLOR"):
        return True

    return hasattr(stream, "isatty") and stream.isatty()


def _paint(
    text: str,
    attributes: str,
    stream: TextIO,
) -> str:
    """Wrap text in ANSI colors when the stream supports them."""

    if not _supports_colors(stream):
        return text

    return f"\x1b[{attributes}m{text}{_RESET}"


def _print_step(
    label: str,
) -> None:
    """Print a numbered pipeline step heading."""

    print()
    print(
        _paint(
            f"{label}",
            _STEP_STYLE,
            sys.stdout,
        )
    )


def _print_success(
    label: str,
) -> None:
    """Print a success message."""

    print(
        "  "
        + _paint(
            f"{label}",
            _SUCCESS_STYLE,
            sys.stdout,
        )
    )
    print()


def _print_error(
    label: str,
) -> None:
    """Print an error message."""

    print(
        _paint(
            f" ⚠️ {label}",
            _ERROR_STYLE,
            sys.stdout,
        )
    )
    print()


def _print_warning(
    label: str,
) -> None:
    """Print a warning message."""

    print(
        _paint(
            f" ⚠️ {label}",
            _WARNING_STYLE,
            sys.stdout,
        )
    )
    print()


def _print_with_check(
    label: str,
) -> None:
    """Print a success message."""

    print(
        "  "
        + _paint(
            "✓",
            _CHECK_STYLE,
            sys.stdout,
        )
        + f" {label}"
    )


def _print_deleted(
    path: str,
) -> None:
    """Print a deleted element, using the create_file() line format."""

    print(
        "  "
        + _paint(
            "✗",
            _CHECK_STYLE,
            sys.stdout,
        )
        + f" {path}"
    )


def _print_title(
    label: str,
    color_scheme: str,
) -> None:
    """Print the title banner inside a 70-character wide frame.

    The title line is: "=" + a 68-character content area + "=".
    The content area holds the centered title, painted white on green
    (the green background covers the full 68-character area, padding
    included).
    """

    text = label.strip()

    # 1. Découpe le texte en plusieurs lignes (gère aussi \r\n)
    lines = text.splitlines()

    # 2. Centre chaque ligne individuellement sur la largeur disponible
    centered_lines = [line.center(_TITLE_WIDTH - 2) for line in lines]

    # Bordure supérieure
    print(_paint(" " * _TITLE_WIDTH, color_scheme, sys.stdout))

    # 3. Impression ligne par ligne pour éviter tout débordement de couleur
    for line in centered_lines:
        print(
            _paint(
                " " + line + " ",
                color_scheme,
                sys.stdout,
            )
        )

    # Bordure inférieure
    print(_paint(" " * _TITLE_WIDTH, color_scheme, sys.stdout))

    print()


def resolve_destination(filepath: str) -> str:
    """Resolve the destination path of a file according to PATH_RULES.

    Args:
        filepath: Original (logical) file path used by the create_* functions

    Returns:
        The rewritten destination path in the generated project tree
    """
    for source_prefix, destination_prefix in PATH_RULES:
        if filepath.startswith(source_prefix):
            return filepath.replace(source_prefix, destination_prefix, 1)
    # No rule matched: keep the file at the project root
    return filepath


def _project_already_generated() -> bool:
    """Return whether the project directory already holds generated files.

    Detection checks the markers listed in GENERATED_ARTIFACTS. The
    scripts/ directory itself is ignored: it only legitimately contains
    this script (create_project.py).
    """

    root = os.getcwd()
    return any(os.path.exists(os.path.join(root, artifact)) for artifact in GENERATED_ARTIFACTS)


def _should_print_deletion(relative: str) -> bool:
    """Return True if the deletion of `relative` should be displayed.

    Some cache/tool directories have their output suppressed beyond a
    certain depth to avoid flooding the logs.
    """
    parts = PurePosixPath(relative).parts
    if not parts:
        return True
    top = parts[0]
    if top in SUPPRESS_DELETION_DETAILS:
        rule = SUPPRESS_DELETION_DETAILS[top]
        depth = len(parts)
        if depth == 1 and not rule.show_root:
            return False
        return depth <= rule.max_depth
    return True


def _remove_tree(path: str) -> None:
    """Delete a file or a directory tree, preserving PRESERVED_FILES.

    Every actually deleted element (file or emptied directory) is
    displayed with the create_file() line format, unless it lives
    inside a directory listed in SUPPRESS_DELETION_DETAILS beyond
    the configured depth.

    Args:
        path: Absolute path to delete
    """
    relative = os.path.relpath(path, os.getcwd()).replace("\\", "/")
    if relative in PRESERVED_FILES:
        return

    if os.path.isdir(path):
        for name in os.listdir(path):
            _remove_tree(os.path.join(path, name))
        try:
            os.rmdir(path)
        except OSError:
            # Directory still holds a preserved file (e.g. the logo):
            # it is kept, hence not reported as deleted.
            return
        if _should_print_deletion(relative):
            _print_deleted(relative)
    else:
        os.remove(path)
        if _should_print_deletion(relative):
            _print_deleted(relative)


def _cleanup_generated_project() -> None:
    """Delete all project content except the preserved files.

    Preserved:
    - scripts/create_project.py (this script)
    - assets/icons/logo-512x512.png (project logo)
    - .bintools/ (Qt utilities, Zig compiler)
    - .git/ (version control history)
    """

    root = os.getcwd()
    for entry in os.listdir(root):
        _remove_tree(os.path.join(root, entry))

    _print_success(" Cleaned project directory! ")


def _confirm_project_cleanup(
    message: str = "    Delete everything and regenerate? [y/N]: ",
) -> bool:
    """Ask the user to confirm wiping the project directory.

    Args:
        message: Confirmation prompt displayed to the user

    Returns:
        True when the user confirms the deletion
    """

    answer = input(message)
    return answer.strip().lower() in ("y", "yes")


def _cleanup_only() -> None:
    """Run the --cleanup mode: clean the project directory, then exit.

    The cleanup only targets an already generated project: when no
    generated artifact is found, nothing is deleted and the script
    exits, so it can never wipe arbitrary user content.
    """

    if not _project_already_generated():
        _print_warning(
            "No generated project found in this directory: nothing to clean up!"
        )
        sys.exit(0)

    _print_title(
        "This project directory contains generated files\nand maybe user created files!!!",
        _WARNING_STYLE,
    )
    print(
        "  Everything will be deleted except:\n"
        "    - scripts/create_project.py\n"
        "    - assets/icons/logo-512x512.png\n"
        "    - .bintools/ (Qt utilities, Zig compiler)\n"
        "    - .git/ (version control history)\n"
    )

    if not _confirm_project_cleanup("    Delete everything? [y/N]: "):
        _print_warning("Aborted: the project directory was left untouched! ")
        sys.exit(0)

    _print_step(" Cleaning up the project directory ")
    _cleanup_generated_project()
    _create_default_readme()


# ---------------------------------------------------------------------------
# Default README creation
# ---------------------------------------------------------------------------

def _create_default_readme() -> None:
    """Create a default README.md file in the project root."""
    readme_content = """# Companion4SoloPlayer
"""
    create_file("README.md", readme_content)

    _print_success(" Default README created successfully! ")


# ---------------------------------------------------------------------------
# Project structure creation
# ---------------------------------------------------------------------------
def create_directory_structure() -> None:
    """Create the whole project tree."""
    _print_step(" Creating project structure ")

    directories = [
        f"{SRC_PACKAGE}/core",
        f"{SRC_PACKAGE}/core/rules",
        f"{SRC_PACKAGE}/plugins/demo_plugin",
        f"{SRC_PACKAGE}/plugins/demo_plugin/datas/",
        f"{SRC_PACKAGE}/plugins/demo_plugin/rules/",
        f"{SRC_PACKAGE}/ui/dialogs",
        "assets/icons",
        "assets/fonts",
        "assets/sounds",
        "data/saves",
        "data/custom_quests",
        "data/config",
        "tests/tests_core",
        "tests/tests_plugins",
        "tests/tests_ui",
        "docs",
        "docs/assets",
        "docs/scripts",
        "docs/companion4soloplayer",
        "docs/companion4soloplayer/core",
        "docs/companion4soloplayer/core/rules",
        "docs/companion4soloplayer/plugins",
        "docs/companion4soloplayer/plugins/demo_plugin",
        "docs/companion4soloplayer/ui",
        "docs/companion4soloplayer/ui/dialogs",
        "scripts",
        "build",
        ".vscode",
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

        print(
            "  "
            + _paint(
                "✓",
                _CHECK_STYLE,
                sys.stdout,
            )
            + f" {directory}"
        )

    _print_success(" Structure created successfully! ")


# ---------------------------------------------------------------------------
# Files creation function
# ---------------------------------------------------------------------------
def create_file(filepath: str, content: str) -> None:
    """Create a file at its mapped destination in the project tree."""
    destination = resolve_destination(filepath)
    with open(destination, "w", encoding="utf-8") as f:
        f.write(content)

    print(
        "  "
        + _paint(
            "✓",
            _CHECK_STYLE,
            sys.stdout,
        )
        + f" {destination}"
    )

# ---------------------------------------------------------------------------
# Core module files
# ---------------------------------------------------------------------------
def create_core_files() -> None:
    """Create the core module files."""
    _print_step(" Creating core files ")

    _create_core_package_init()
    _create_core_character_tracker()
    _create_core_dice_roller()
    _create_core_combat_resolver()
    _create_core_procedural_generator()
    _create_core_quest_manager()
    _create_core_plugin_loader()
    _create_core_rule_engine()
    _create_core_yaml_loader()

    _create_core_rules_package_init()
    _create_core_rules_oracle_rule()

    _print_success(" Core files created ")


# ---------------------------------------------------------------------------
def _create_core_package_init() -> None:
    # core/__init__.py
    # NOTE: no version here - the version lives in the package metadata
    # (pyproject.toml) and is exposed by companion4soloplayer/__init__.py
    create_file(
        "core/__init__.py",
        '''"""
Core module for Companion4SoloPlayer.
Contains the generic game engine components.
"""
''',
    )


# ---------------------------------------------------------------------------
def _create_core_character_tracker() -> None:
    # core/character_tracker.py
    create_file(
        "core/character_tracker.py",
        '''"""
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
''',
    )


# ---------------------------------------------------------------------------
def _create_core_dice_roller() -> None:
    # core/dice_roller.py
    create_file(
        "core/dice_roller.py",
        '''"""
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
''',
    )


# ---------------------------------------------------------------------------
def _create_core_combat_resolver() -> None:
    # core/combat_resolver.py
    create_file(
        "core/combat_resolver.py",
        '''"""
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
''',
    )


# ---------------------------------------------------------------------------
def _create_core_procedural_generator() -> None:
    # core/procedural_generator.py
    create_file(
        "core/procedural_generator.py",
        '''"""
Procedural generation module.
Generates dungeons, rooms, and encounters.
"""

import random


class ProceduralGenerator:
    """Generates procedural content for dungeons."""

    def __init__(self, seed: int | None = None) -> None:
        """Initialize the generator.

        Args:
            seed: Optional random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)

    def generate_room(self, room_type: str, level: int) -> dict:
        """Generate a dungeon room.

        Args:
            room_type: Type of room ('corridor', 'room', 'intersection', 'stairs')
            level: Dungeon level (1-10)

        Returns:
            Dictionary with room characteristics

        Raises:
            ValueError: If room_type is invalid or level out of range
        """
        if level < 1 or level > 10:
            raise ValueError("Level must be between 1 and 10")

        room_templates = {
            'corridor': [
                {'width': 1, 'length': 5, 'description': 'A narrow stone corridor'},
                {'width': 1, 'length': 8, 'description': 'A long, dark passage'},
                {'width': 2, 'length': 6, 'description': 'A wide hallway'},
            ],
            'room': [
                {'width': 4, 'length': 4, 'description': 'A small square chamber'},
                {'width': 5, 'length': 5, 'description': 'A medium-sized room'},
                {'width': 6, 'length': 8, 'description': 'A large hall'},
            ],
            'intersection': [
                {'width': 3, 'length': 3, 'description': 'A crossroads'},
                {'width': 4, 'length': 4, 'description': 'A four-way junction'},
            ],
            'stairs': [
                {'width': 2, 'length': 3, 'description': 'Stone stairs leading down'},
            ]
        }

        if room_type not in room_templates:
            raise ValueError(f"Invalid room type: {room_type}")

        template = random.choice(room_templates[room_type])
        difficulty_modifier = level / 10

        return {
            'type': room_type,
            'dimensions': (template['width'], template['length']),
            'description': template['description'],
            'level': level,
            'difficulty': difficulty_modifier
        }

    def generate_dungeon(self, num_rooms: int, level: int) -> list[dict]:
        """Generate a complete dungeon.

        Args:
            num_rooms: Number of rooms to generate
            level: Dungeon level (1-10)

        Returns:
            List of room dictionaries
        """
        rooms = []
        room_types = ['corridor', 'room', 'intersection', 'stairs']

        for i in range(num_rooms):
            room_type = random.choice(room_types)
            room = self.generate_room(room_type, level)
            room['id'] = i
            rooms.append(room)

        return rooms
''',
    )


# ---------------------------------------------------------------------------
def _create_core_quest_manager() -> None:
    # core/quest_manager.py
    create_file(
        "core/quest_manager.py",
        '''"""
Quest management module.
Handles quest tracking and objectives.
"""

from enum import Enum

from pydantic import BaseModel, Field


class QuestStatus(Enum):
    """Quest status enumeration."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Objective(BaseModel):
    """Quest objective."""
    description: str = Field(..., description="Objective description")
    completed: bool = Field(default=False, description="Completion status")


class Quest(BaseModel):
    """Quest representation."""
    name: str = Field(..., description="Quest name")
    description: str = Field(..., description="Quest description")
    objectives: list[Objective] = Field(default_factory=list, description="Quest objectives")
    status: QuestStatus = Field(default=QuestStatus.NOT_STARTED, description="Quest status")
    rewards: dict[str, int] = Field(default_factory=dict, description="Quest rewards")


class QuestManager:
    """Manages quests and their progression."""

    def __init__(self) -> None:
        """Initialize the quest manager."""
        self.quests: dict[str, Quest] = {}
        self.active_quest: str | None = None

    def create_quest(
        self,
        name: str,
        description: str,
        objectives: list[str]
    ) -> Quest:
        """Create a new quest.

        Args:
            name: Quest name
            description: Quest description
            objectives: List of objective descriptions

        Returns:
            The created Quest object

        Raises:
            ValueError: If quest name already exists
        """
        if name in self.quests:
            raise ValueError(f"Quest '{name}' already exists")

        quest = Quest(
            name=name,
            description=description,
            objectives=[Objective(description=obj) for obj in objectives]
        )
        self.quests[name] = quest
        return quest

    def start_quest(self, name: str) -> bool:
        """Start a quest.

        Args:
            name: Quest name

        Returns:
            True if quest was started, False if not found
        """
        if name in self.quests:
            self.quests[name].status = QuestStatus.IN_PROGRESS
            self.active_quest = name
            return True
        return False

    def complete_objective(self, quest_name: str, objective_index: int) -> bool:
        """Mark an objective as completed.

        Args:
            quest_name: Quest name
            objective_index: Index of the objective

        Returns:
            True if objective was completed, False if invalid
        """
        if quest_name not in self.quests:
            return False

        quest = self.quests[quest_name]
        if 0 <= objective_index < len(quest.objectives):
            quest.objectives[objective_index].completed = True

            if all(obj.completed for obj in quest.objectives):
                quest.status = QuestStatus.COMPLETED

            return True
        return False

    def get_active_quest(self) -> Quest | None:
        """Get the currently active quest.

        Returns:
            Active quest or None
        """
        if self.active_quest:
            return self.quests.get(self.active_quest)
        return None
''',
    )


# ---------------------------------------------------------------------------
def _create_core_plugin_loader() -> None:
    # core/plugin_loader.py
    create_file(
        "core/plugin_loader.py",
        '''"""
Plugin loader module.
Handles dynamic loading of game plugins.

Two operating modes are supported:

- Development: plugins live as regular Python packages
  (``src/companion4soloplayer/plugins/<name>_plugin/``) and are imported
  through the standard import machinery.
- Frozen application (PyInstaller one-dir build): each plugin ships as a
  compiled extension module (``<name>.pyd``) located in the
  ``plugins/`` folder next to the application ``_internal`` data, and is
  loaded dynamically through importlib.

Both kinds of plugin expose a ``Plugin`` class compatible with the
:class:`GamePlugin` protocol. Plugin data (manifest, classes, rules...)
ships as commented YAML files (``plugin.yaml``, ``rules.yaml``, ...)
loaded through :mod:`companion4soloplayer.core.yaml_loader`, and rule
elements are bound to Python classes through the hybrid
:class:`companion4soloplayer.core.rule_engine.RuleEngine`.
"""

import importlib
import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from typing import Any, Protocol, cast

from companion4soloplayer.core.rule_engine import RuleEngine


def _default_plugins_dir() -> Path:
    """Return the directory holding the plugins.

    In a frozen (PyInstaller) application the compiled plugin libraries
    (``*.pyd``) are collected into ``<sys._MEIPASS>/plugins``. In a regular
    (development) install they are the Python packages stored in
    ``companion4soloplayer/plugins``.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None)
        if base is None:
            base = Path(sys.executable).parent
        return Path(base) / "plugins"
    return Path(__file__).resolve().parents[1] / "plugins"


# Source package names carry a "_plugin" suffix in development (e.g.
# ``demo_plugin``) while the compiled libraries drop it
# (e.g. ``demo.pyd``). The canonical plugin name is therefore the
# identifier without the suffix.
_PLUGIN_PACKAGE_SUFFIX = "_plugin"

# Extensions considered as compiled plugin libraries.
_EXTENSION_SUFFIXES = tuple(importlib.machinery.EXTENSION_SUFFIXES)

# Plugin manifests. YAML is the canonical format, stored in the plugin
# ``datas/`` data directory.
MANIFEST_NAMES = ("datas/plugin.yaml", "plugin.yaml")


def _has_manifest(directory: Path) -> bool:
    """Tell whether a directory contains a plugin manifest.

    Args:
        directory: Directory to check.

    Returns:
        True if ``plugin.yaml`` is present.
    """
    return any((directory / name).is_file() for name in MANIFEST_NAMES)


class GamePlugin(Protocol):
    """Interface for game plugins."""

    @property
    def name(self) -> str:
        """Plugin name (generic, no trademarked names)."""
        ...

    @property
    def version(self) -> str:
        """Plugin version."""
        ...

    @property
    def description(self) -> str:
        """Plugin description."""
        ...

    def get_classes(self) -> list[dict]:
        """Get character classes."""
        ...

    def get_monsters(self) -> list[dict]:
        """Get monsters."""
        ...

    def get_items(self) -> list[dict]:
        """Get items."""
        ...

    def get_rules(self) -> dict:
        """Get game rules."""
        ...

    def generate_dungeon(self, config: dict) -> dict:
        """Generate a dungeon."""
        ...

    def get_rule_engine(self) -> RuleEngine:
        """Get the hybrid (YAML data + Python classes) rule engine."""
        ...

    def create_component(self, kind: str) -> Any:
        """Instantiate a rule component declared in ``rules.yaml``."""
        ...


class PluginLoader:
    """Loads and manages game plugins.

    Plugins are discovered either as compiled extension libraries
    (``<name>.pyd``) or as source packages (``<name>_plugin``) and are
    loaded lazily, on demand, through :meth:`load_plugin`.
    """

    def __init__(self, plugins_dir: str | None = None) -> None:
        """Initialize the plugin loader.

        Args:
            plugins_dir: Directory containing plugins. When omitted, the
                directory is resolved automatically: ``<sys._MEIPASS>/plugins``
                for a frozen application, the ``companion4soloplayer/plugins``
                package otherwise.
        """
        self.plugins_dir = Path(plugins_dir) if plugins_dir else _default_plugins_dir()
        self.loaded_plugins: dict[str, GamePlugin] = {}
        #: Last load failure per plugin name (``"ErrorType: message"``).
        #: The released application runs without a console, so this is
        #: how callers (MainWindow) surface the real reason of a failure.
        self.last_errors: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _iter_plugin_dirs(self) -> list[Path]:
        """Return plugin directories containing a ``plugin.yaml`` manifest."""
        if not self.plugins_dir.is_dir():
            return []
        return sorted(
            item for item in self.plugins_dir.iterdir() if item.is_dir() and _has_manifest(item)
        )

    def discover_plugins(self) -> list[str]:
        """Discover available plugins.

        Both compiled libraries (``demo.pyd``) and source packages
        (``demo_plugin``) are recognized.

        Returns:
            List of plugin names
        """
        plugins = []
        for item in self._iter_plugin_dirs():
            # A directory only qualifies as a plugin when its code is
            # available: either a compiled library next to the manifest or
            # an importable source package.
            if (
                self._find_extension(item.name.replace(_PLUGIN_PACKAGE_SUFFIX, ""), item.parent)
                or importlib.util.find_spec(f"companion4soloplayer.plugins.{item.name}") is not None
            ):
                plugins.append(item.name.replace(_PLUGIN_PACKAGE_SUFFIX, ""))
        return plugins

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @staticmethod
    def _find_extension(plugin_name: str, directory: Path) -> Path | None:
        """Locate a compiled plugin library (``<name>.pyd``) in a directory."""
        for suffix in _EXTENSION_SUFFIXES:
            candidate = directory / f"{plugin_name}{suffix}"
            if candidate.is_file():
                return candidate
        return None

    def _load_compiled(self, plugin_name: str, library_path: Path) -> GamePlugin | None:
        """Load a compiled plugin library and instantiate its Plugin class."""
        spec = importlib.util.spec_from_file_location(
            f"companion4soloplayer.plugins.{plugin_name}",
            library_path,
            loader=importlib.machinery.ExtensionFileLoader(
                f"companion4soloplayer.plugins.{plugin_name}", str(library_path)
            ),
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create import spec for {library_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
            plugin = cast(GamePlugin, module.Plugin())
        except Exception:
            # Never leave a half-initialized module registered.
            sys.modules.pop(spec.name, None)
            raise
        self.loaded_plugins[plugin_name] = plugin
        return plugin

    def _load_source(self, plugin_name: str) -> GamePlugin | None:
        """Load a source plugin package and instantiate its Plugin class."""
        module = importlib.import_module(
            f"companion4soloplayer.plugins.{plugin_name}{_PLUGIN_PACKAGE_SUFFIX}"
        )
        plugin = cast(GamePlugin, module.Plugin())
        self.loaded_plugins[plugin_name] = plugin
        return plugin

    def load_plugin(self, plugin_name: str) -> GamePlugin | None:
        """Load a plugin on demand by name.

        Compiled libraries (``<name>.pyd`` in the plugins directory) are
        preferred; in development the ``<name>_plugin`` source package is
        used as a fallback.

        Args:
            plugin_name: Plugin name (without the ``_plugin`` suffix)

        Returns:
            Loaded plugin or None if not found
        """
        if plugin_name in self.loaded_plugins:
            return self.loaded_plugins[plugin_name]

        try:
            library_path = self._find_extension(plugin_name, self.plugins_dir)
            if library_path is not None:
                plugin = self._load_compiled(plugin_name, library_path)
            elif (
                importlib.util.find_spec(
                    f"companion4soloplayer.plugins.{plugin_name}{_PLUGIN_PACKAGE_SUFFIX}"
                )
                is not None
            ):
                plugin = self._load_source(plugin_name)
            else:
                print(f"Plugin {plugin_name} not found in {self.plugins_dir}")
                self.last_errors[plugin_name] = f"plugin library not found in {self.plugins_dir}"
                return None
        except Exception as e:
            self.last_errors[plugin_name] = f"{type(e).__name__}: {e}"
            print(f"Error loading plugin {plugin_name}: {e}")
            return None
        self.last_errors.pop(plugin_name, None)
        return plugin

    def get_plugin(self, plugin_name: str) -> GamePlugin | None:
        """Get a loaded plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            Plugin or None if not loaded
        """
        return self.loaded_plugins.get(plugin_name)

    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin.

        Also drops the dynamically registered module (compiled libraries)
        so a subsequent load re-imports it from disk.

        Args:
            plugin_name: Plugin name

        Returns:
            True if plugin was unloaded, False if not found
        """
        if plugin_name in self.loaded_plugins:
            del self.loaded_plugins[plugin_name]
            sys.modules.pop(f"companion4soloplayer.plugins.{plugin_name}", None)
            return True
        return False
''',
    )


# ---------------------------------------------------------------------------
def _create_core_rule_engine() -> None:
    # core/rule_engine.py
    create_file(
        "core/rule_engine.py",
        '''"""
Hybrid rule engine module.

Game rules are described *declaratively* in YAML (``rules.yaml``) and may
bind Python rule elements (character creation, combat, loot, magic,
oracle, ...) through ``!pyclass`` references. This module fuses both
worlds:

- the YAML part stays pure data (loaded with the safe loader);
- the Python part is resolved and instantiated lazily by
  :class:`RuleEngine`, only when a rule element is actually requested.

Security model:

- parsing never imports anything (see
  :mod:`companion4soloplayer.core.yaml_loader`);
- absolute imports are restricted to an allow-list of module prefixes
  (:data:`DEFAULT_ALLOWED_MODULES`);
- ``local:`` references resolve inside the module that declared the rules
  (the plugin module), which keeps them valid both in development and in
  the compiled ``.pyd`` build, where the plugin ships as a single module.
"""

from __future__ import annotations

import importlib
import types
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from companion4soloplayer.core.yaml_loader import PyClassRef, load_yaml_file

#: Standard rule element kinds understood by the application.
RULE_KINDS: tuple[str, ...] = (
    "character_creation",
    "combat",
    "loot",
    "magic",
    "oracle",
    "special",
)

#: Modules that may be imported through an absolute ``!pyclass`` reference.
DEFAULT_ALLOWED_MODULES: tuple[str, ...] = ("companion4soloplayer",)

#: Key of the ``rules.yaml`` mapping declaring the rule implementations.
IMPLEMENTATIONS_KEY = "implementations"


class RuleEngineError(Exception):
    """Base class for rule engine errors."""


class UnknownRuleKindError(RuleEngineError):
    """Raised when a rule kind is not declared in ``implementations``."""


class ImplementationError(RuleEngineError):
    """Raised when a rule reference cannot be resolved or instantiated."""


class ImplementationNotAllowedError(ImplementationError):
    """Raised when a rule reference targets a module outside the allow-list."""


class RuleEngine:
    """Resolves and caches the Python components declared in YAML rules.

    Args:
        rules: Parsed ``rules.yaml`` document.
        base_module: Module used to resolve ``local:`` references, either
            the module object itself or its dotted name. Required as soon
            as the document contains a ``local:`` reference.
        allowed_modules: Module prefixes accepted for absolute references.

    Raises:
        RuleEngineError: If ``rules`` is not a mapping.
    """

    def __init__(
        self,
        rules: Mapping[str, Any],
        *,
        base_module: str | types.ModuleType | None = None,
        allowed_modules: Sequence[str] = DEFAULT_ALLOWED_MODULES,
    ) -> None:
        if not isinstance(rules, Mapping):
            raise RuleEngineError(f"Rules document must be a mapping, got {type(rules).__name__}")
        self._rules = dict(rules)
        self._base_module = base_module
        self._allowed_modules = tuple(allowed_modules)
        self._components: dict[str, Any] = {}

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        *,
        base_module: str | types.ModuleType | None = None,
        allowed_modules: Sequence[str] = DEFAULT_ALLOWED_MODULES,
    ) -> RuleEngine:
        """Load a rules document from a YAML file.

        Args:
            path: Path of the rules file (typically ``rules.yaml``).
            base_module: Module used to resolve ``local:`` references.
            allowed_modules: Module prefixes accepted for absolute references.

        Returns:
            The initialized rule engine.

        Raises:
            YamlLoadError: If the file is not valid YAML.
            RuleEngineError: If the file is empty or not a mapping.
        """
        data = load_yaml_file(path)
        if data is None:
            raise RuleEngineError(f"Rules document {path} is empty")
        return cls(data, base_module=base_module, allowed_modules=allowed_modules)

    # ------------------------------------------------------------------
    # Declarative side
    # ------------------------------------------------------------------

    @property
    def rules(self) -> dict[str, Any]:
        """Return a copy of the declarative rules document."""
        return dict(self._rules)

    def get(self, key: str, default: Any = None) -> Any:
        """Return a top-level section of the rules document.

        Args:
            key: Top-level key (``combat``, ``movement``, ...).
            default: Value returned when the key is absent.

        Returns:
            The section content.
        """
        return self._rules.get(key, default)

    @property
    def implementations(self) -> dict[str, PyClassRef]:
        """Return the declared rule implementations (kind -> reference).

        Raises:
            RuleEngineError: If ``implementations`` is not a mapping or
                contains a value that is neither a string nor a
                :class:`PyClassRef`.
        """
        raw = self._rules.get(IMPLEMENTATIONS_KEY, {})
        if not isinstance(raw, Mapping):
            raise RuleEngineError(
                f"'{IMPLEMENTATIONS_KEY}' must be a mapping, got {type(raw).__name__}"
            )
        result: dict[str, PyClassRef] = {}
        for kind, value in raw.items():
            if isinstance(value, PyClassRef):
                result[str(kind)] = value
            elif isinstance(value, str):
                result[str(kind)] = PyClassRef.parse(value)
            else:
                raise RuleEngineError(
                    f"Implementation for rule kind {kind!r} must be a !pyclass "
                    f"reference, got {type(value).__name__}"
                )
        return result

    @property
    def kinds(self) -> list[str]:
        """Return the sorted list of declared rule kinds."""
        return sorted(self.implementations)

    # ------------------------------------------------------------------
    # Hybrid side: resolution and instantiation
    # ------------------------------------------------------------------

    def resolve(self, ref: PyClassRef | str) -> Any:
        """Resolve a class reference to the referenced object (no instantiation).

        Args:
            ref: The reference, as a :class:`PyClassRef` or as a
                ``module:Class`` / ``local:Class`` string.

        Returns:
            The object referenced by ``ref``.

        Raises:
            YamlTagError: If a string reference is malformed.
            ImplementationNotAllowedError: If an absolute reference targets a
                module outside the allow-list.
            ImplementationError: If the module or attribute cannot be resolved,
                or if a ``local:`` reference is used without ``base_module``.
        """
        ref = PyClassRef.parse(ref) if isinstance(ref, str) else ref
        if ref.is_local:
            module = self._resolve_base_module()
        else:
            module = self._import_allowed_module(ref.module)
        try:
            return getattr(module, ref.attr)
        except AttributeError as exc:
            raise ImplementationError(
                f"Module {ref.module!r} has no attribute {ref.attr!r}"
            ) from exc

    def component(self, kind: str) -> Any:
        """Instantiate (and cache) the rule component declared for ``kind``.

        Args:
            kind: Rule kind key inside the ``implementations`` mapping.

        Returns:
            The component instance, created with the ``params`` declared
            in the YAML reference.

        Raises:
            UnknownRuleKindError: If ``kind`` is not declared.
            ImplementationNotAllowedError: If an absolute reference targets a
                module outside the allow-list.
            ImplementationError: If the reference cannot be resolved or the
                referenced object cannot be instantiated.
        """
        if kind in self._components:
            return self._components[kind]

        implementations = self.implementations
        if kind not in implementations:
            raise UnknownRuleKindError(
                f"Rule kind {kind!r} is not declared in '{IMPLEMENTATIONS_KEY}' "
                f"(available: {', '.join(sorted(implementations)) or 'none'})"
            )

        ref = implementations[kind]
        target = self.resolve(ref)
        if not callable(target):
            raise ImplementationError(
                f"Reference {ref.path!r} for rule kind {kind!r} is not callable"
            )
        try:
            instance = target(**dict(ref.params))
        except Exception as exc:
            raise ImplementationError(
                f"Cannot instantiate {ref.path!r} for rule kind {kind!r} "
                f"with params {dict(ref.params)!r}: {exc}"
            ) from exc

        self._components[kind] = instance
        return instance

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_base_module(self) -> types.ModuleType:
        """Return the module used for ``local:`` references.

        Raises:
            ImplementationError: If the module is unknown or cannot be imported.
        """
        base = self._base_module
        if base is None:
            raise ImplementationError(
                "A 'local:' reference requires base_module= to be set on the rule engine"
            )
        if isinstance(base, types.ModuleType):
            return base
        try:
            return importlib.import_module(base)
        except ImportError as exc:
            raise ImplementationError(f"Cannot import base module {base!r}: {exc}") from exc

    def _import_allowed_module(self, module_name: str) -> types.ModuleType:
        """Import ``module_name`` after checking it against the allow-list.

        Raises:
            ImplementationNotAllowedError: If the module is outside the allow-list.
            ImplementationError: If the module cannot be imported.
        """
        if not any(
            module_name == prefix or module_name.startswith(f"{prefix}.")
            for prefix in self._allowed_modules
        ):
            raise ImplementationNotAllowedError(
                f"Module {module_name!r} is outside the allowed prefixes "
                f"{self._allowed_modules!r}"
            )
        try:
            return importlib.import_module(module_name)
        except ImportError as exc:
            raise ImplementationError(f"Cannot import module {module_name!r}: {exc}") from exc

''',
    )


# ---------------------------------------------------------------------------
def _create_core_yaml_loader() -> None:
    # core/yaml_loader.py
    create_file(
        "core/yaml_loader.py",
        '''"""
YAML data loading module for plugin and rule data.

The loader builds on :class:`yaml.SafeLoader`, so only plain YAML data
(mappings, sequences and scalars) can be constructed: arbitrary Python
object instantiation (``!!python/...`` tags) is rejected by the parser.
On top of that hardened baseline, a small set of custom tags adds typed
values on purpose:

- ``!pyclass`` declares a Python class to instantiate later (hybrid
  YAML/Python rule architecture). It is parsed into a :class:`PyClassRef`
  value; **no import happens during parsing**.
- ``!dice`` declares a dice expression (``2d6``, ``1d20+3``, ``d6-1``...)
  and is parsed into a :class:`DiceExpression` value.

Additional tags can be registered with :func:`register_tag` before any
document is loaded, which lets plugins extend the vocabulary without
touching the core loader.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode

from companion4soloplayer.core.dice_roller import DiceRoller


class YamlLoadError(ValueError):
    """Raised when a YAML document cannot be parsed."""


class YamlTagError(ValueError):
    """Raised when the payload of a custom tag is invalid."""


# Accepts "2d6", "d20", "1d20+3", "4d6-2" (case-insensitive).
_DICE_PATTERN = re.compile(r"^(?P<count>\\d*)[dD](?P<sides>\\d+)(?P<modifier>[+-]\\d+)?$")


@dataclass(frozen=True)
class DiceExpression:
    """A parsed dice expression such as ``2d6`` or ``1d20+3``.

    Attributes:
        count: Number of dice to roll (at least 1).
        sides: Number of sides per die (at least 2).
        modifier: Value added to (or subtracted from) the dice total.
    """

    count: int
    sides: int
    modifier: int = 0

    @classmethod
    def parse(cls, value: DiceExpression | str) -> DiceExpression:
        """Parse a dice notation string (already-parsed values pass through).

        Args:
            value: Dice notation such as ``2d6``, ``d20``, ``1d20+3``.

        Returns:
            The parsed :class:`DiceExpression`.

        Raises:
            YamlTagError: If the notation is invalid.
        """
        if isinstance(value, DiceExpression):
            return value
        match = _DICE_PATTERN.match(value.strip())
        if match is None:
            raise YamlTagError(
                f"Invalid dice notation {value!r}: expected '<count>d<sides>[+/-<modifier>]'"
            )
        count = int(match.group("count")) if match.group("count") else 1
        sides = int(match.group("sides"))
        if count < 1 or sides < 2:
            raise YamlTagError(
                f"Invalid dice notation {value!r}: count >= 1 and sides >= 2 required"
            )
        modifier = int(match.group("modifier")) if match.group("modifier") else 0
        return cls(count=count, sides=sides, modifier=modifier)

    @property
    def notation(self) -> str:
        """Return the canonical notation (``2d6+1``)."""
        modifier = f"{self.modifier:+d}" if self.modifier else ""
        return f"{self.count}d{self.sides}{modifier}"

    def __str__(self) -> str:
        """Return the canonical notation."""
        return self.notation

    def roll(self, roller: DiceRoller | None = None) -> int:
        """Roll the expression and return the total, modifier included.

        Args:
            roller: Optional dice roller; a fresh one is created when omitted.

        Returns:
            Sum of the dice results plus the modifier.
        """
        _, total = self.roll_detail(roller)
        return total

    def roll_detail(self, roller: DiceRoller | None = None) -> tuple[list[int], int]:
        """Roll the expression and return both the dice results and the total.

        Args:
            roller: Optional dice roller; a fresh one is created when omitted.

        Returns:
            Tuple ``(dice results, total including modifier)``.
        """
        roller = roller or DiceRoller()
        results = roller.roll_dice(self.count, self.sides)
        return results, sum(results) + self.modifier


# --------------------------------------------------------------------------
# !pyclass -> PyClassRef
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PyClassRef:
    """A reference to a Python class declared in YAML.

    The reference is *data*: it is never imported while parsing. The core
    rule engine resolves and instantiates it on demand, after checking a
    module allow-list.

    Attributes:
        path: Either ``"module.path:ClassName"`` (absolute import) or
            ``"local:ClassName"`` / ``":ClassName"`` (class living in the
            module that declared the rules, valid in development and in
            the compiled ``.pyd`` build).
        params: Keyword arguments passed to the constructor.
    """

    path: str
    params: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, value: str) -> PyClassRef:
        """Parse a ``module:Class`` / ``local:Class`` reference string.

        Args:
            value: The reference string.

        Returns:
            The parsed :class:`PyClassRef`.

        Raises:
            YamlTagError: If the reference format is invalid.
        """
        module_name, separator, attr = value.partition(":")
        if not separator or not attr or "." in attr:
            raise YamlTagError(
                f"Invalid class reference {value!r}: expected 'module.path:ClassName' "
                "or 'local:ClassName'"
            )
        if module_name in ("", "local"):
            return cls(path=f"local:{attr}")
        if not all(part.isidentifier() for part in module_name.split(".")):
            raise YamlTagError(f"Invalid class reference {value!r}")
        if not attr.isidentifier():
            raise YamlTagError(f"Invalid class reference {value!r}")
        return cls(path=f"{module_name}:{attr}")

    @property
    def module(self) -> str:
        """Return the module part (``"local"`` for plugin-local references)."""
        return self.path.partition(":")[0]

    @property
    def attr(self) -> str:
        """Return the class/attribute part of the reference."""
        return self.path.partition(":")[2]

    @property
    def is_local(self) -> bool:
        """Return True when the reference targets the declaring module."""
        return self.module == "local"


# --------------------------------------------------------------------------
# Loader with the C4SP custom tags
# --------------------------------------------------------------------------

#: Signature of a custom tag constructor.
TagConstructor = Callable[[Any, Node], Any]


class C4SPSafeLoader(yaml.SafeLoader):
    """``yaml.SafeLoader`` extended with the C4SP custom tags.

    The class only *adds* constructors; the unsafe ``yaml.Loader`` /
    ``yaml.FullLoader`` classes are never used, so ``!!python/...`` tags
    keep raising a :class:`yaml.constructor.ConstructorError`.
    """


def _construct_pyclass(loader: C4SPSafeLoader, node: Node) -> PyClassRef:
    """Construct a ``!pyclass`` node (scalar or mapping form)."""
    if isinstance(node, ScalarNode):
        return PyClassRef.parse(str(loader.construct_scalar(node)))
    if isinstance(node, MappingNode):
        data = loader.construct_mapping(node, deep=True)
        unknown = set(data) - {"path", "params"}
        if unknown:
            raise YamlTagError(f"!pyclass got unknown keys: {sorted(unknown, key=str)}")
        path = data.get("path")
        if not isinstance(path, str):
            raise YamlTagError("!pyclass mapping form requires a string 'path' entry")
        params = data.get("params", {})
        if not isinstance(params, Mapping):
            raise YamlTagError("!pyclass 'params' must be a mapping")
        return PyClassRef(path=path, params=dict(params))
    raise YamlTagError("!pyclass expects a 'module:Class' scalar or a {path, params} mapping")


def _construct_dice(loader: C4SPSafeLoader, node: Node) -> DiceExpression:
    """Construct a ``!dice`` scalar node."""
    if not isinstance(node, ScalarNode):
        raise YamlTagError("!dice expects a scalar notation such as '2d6'")
    return DiceExpression.parse(str(loader.construct_scalar(node)))


C4SPSafeLoader.add_constructor("!pyclass", _construct_pyclass)
C4SPSafeLoader.add_constructor("!dice", _construct_dice)


def register_tag(tag: str, constructor: TagConstructor) -> None:
    """Register an additional custom tag on the C4SP safe loader.

    Registration must happen before any document is loaded with
    :func:`load_yaml` / :func:`load_yaml_file`. Only safe constructors are
    accepted: they receive the loader and the YAML node and must return
    plain data or lightweight value objects.

    Args:
        tag: Tag name, starting with ``!`` (e.g. ``!table``).
        constructor: ``(loader, node) -> value`` callable.

    Raises:
        ValueError: If the tag name does not start with ``!``.
    """
    if not tag.startswith("!"):
        raise ValueError(f"YAML tag names must start with '!': {tag!r}")
    C4SPSafeLoader.add_constructor(tag, constructor)


def load_yaml(source: str | bytes) -> Any:
    """Parse YAML text with the C4SP safe loader.

    Args:
        source: YAML document as text or bytes (UTF-8).

    Returns:
        The parsed document (mapping, sequence or scalar).

    Raises:
        yaml.YAMLError: If the document is invalid or uses an unknown tag.
        YamlTagError: If a custom tag payload is invalid.
    """
    # C4SPSafeLoader derives from yaml.SafeLoader and only registers safe
    # constructors, so no arbitrary object can be instantiated.
    return yaml.load(source, Loader=C4SPSafeLoader)  # noqa: S506


def load_yaml_file(path: str | Path) -> Any:
    """Load and parse a YAML file with the C4SP safe loader.

    Args:
        path: Path of the YAML file (read as UTF-8).

    Returns:
        The parsed document (mapping, sequence or scalar).

    Raises:
        OSError: If the file cannot be read.
        YamlLoadError: If the file content is not valid YAML; the message
            includes the file path and the underlying parser error.
        YamlTagError: If a custom tag payload is invalid.
    """
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    try:
        # Safe loader (see load_yaml): parsing never instantiates objects.
        return yaml.load(text, Loader=C4SPSafeLoader)  # noqa: S506
    except yaml.YAMLError as exc:
        raise YamlLoadError(f"Invalid YAML in {file_path}: {exc}") from exc
''',
    )


# ---------------------------------------------------------------------------
def _create_core_rules_package_init() -> None:
    # core/rules/__init__.py
    create_file(
        "core/rules/__init__.py",
        '''"""Shared rule elements available to every game plugin.

This package hosts rule element classes that are identical across
plugins (the game masters of the solo catalog share a common rule
book). Plugin-specific rule elements stay inside their own plugin
package under ``<plugin>/rules/``.

Rule elements declared in a plugin ``rules.yaml`` can reference the
classes of this package with an absolute ``!pyclass`` reference (for
example ``companion4soloplayer.core.rules:OracleRule``); the core rule
engine resolves them through its module allow-list.
"""

from companion4soloplayer.core.rules.oracle_rule import OracleRule

__all__ = ["OracleRule"]
''',
    )


# ---------------------------------------------------------------------------
def _create_core_rules_oracle_rule() -> None:
    # core/rules/oracle_rule.py
    create_file(
        "core/rules/oracle_rule.py",
        '''"""Shared yes/no oracle rule element.

The oracle is a generic solo decision aid: it rolls a die and maps the
result to a "no"/"yes" outcome with optional narrative twists. The
class is identical for every plugin, so it lives in the core package
and is referenced from each plugin ``rules.yaml`` with::

    oracle: !pyclass companion4soloplayer.core.rules:OracleRule
"""

from __future__ import annotations

from companion4soloplayer.core.dice_roller import DiceRoller
from companion4soloplayer.core.yaml_loader import DiceExpression


class OracleRule:
    """Simple yes/no oracle for solo decision making (1d6)."""

    OUTCOMES = {
        1: "no, and complications arise",
        2: "no",
        3: "no",
        4: "yes",
        5: "yes",
        6: "yes, and an extra opportunity arises",
    }

    def __init__(self, *, dice: DiceExpression | str = "1d6") -> None:
        """Initialize the rule.

        Args:
            dice: Dice notation drawn for the oracle answer.
        """
        self.dice = DiceExpression.parse(dice)

    def ask(self, roller: DiceRoller | None = None) -> str:
        """Draw an oracle answer.

        Args:
            roller: Optional dice roller.

        Returns:
            The outcome text for the rolled value.
        """
        roller = roller or DiceRoller()
        total = self.dice.roll(roller)
        return self.OUTCOMES[min(6, max(1, total))]
''',
    )


# ---------------------------------------------------------------------------
# Plugin module files
# ---------------------------------------------------------------------------
def create_plugin_files() -> None:
    """Create the plugin files."""
    _print_step(" Creating plugin files ")

    _create_plugin_package_init()

    # =========================================================================
    # Example demo plugin
    # =========================================================================
    _create_plugin_demo_package_init()
    _create_plugin_demo_manifest()
    _create_plugin_demo_data()
    _create_plugin_demo_plugin()
    _create_plugin_demo_classes_yaml()
    _create_plugin_demo_monsters_yaml()
    _create_plugin_demo_items_yaml()
    _create_plugin_demo_rules_yaml()
    _create_plugin_demo_plugin_yaml()
    _create_plugin_demo_readme()
    _create_plugin_demo_rules_package_init()
    _create_plugin_demo_rules_character_creation_rule()
    _create_plugin_demo_rules_combat_rule()
    _create_plugin_demo_rules_loot_rule()
    _create_plugin_demo_rules_magic_rule()


    _print_success(" Plugin demo_plugin created! ")

    _print_success(" All plugins created! ")


# ---------------------------------------------------------------------------
def _create_plugin_package_init() -> None:
    create_file(
        "plugins/__init__.py",
        '''"""
Plugins module for Companion4SoloPlayer.
Contains game-specific plugins.
"""
''',
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_package_init() -> None:
    create_file(
        "plugins/demo_plugin/__init__.py",
        '''"""Game System Demo Plugin.
Provided as a generic example for creating new plugins and how to use them.

Game data ships as commented YAML files in the ``datas/`` directory
(plugin.yaml, classes.yaml, rules.yaml, ...). Rule elements bound with
``!pyclass local:...`` are implemented by the classes re-exported here
(defined one file per class under ``rules/``) and instantiated on
demand by the core rule engine. The shared yes/no oracle lives in
``companion4soloplayer.core.rules``.

This package facade keeps the public surface of the plugin: the core
plugin loader instantiates :class:`Plugin`, and the ``local:``
references of ``datas/rules.yaml`` resolve against this module.
"""

from __future__ import annotations

from .manifest import PluginMetadata
from .plugin import Plugin
from .rules import CharacterCreationRule, CombatRule, LootRule, MagicRule

__all__ = [
    "CharacterCreationRule",
    "CombatRule",
    "LootRule",
    "MagicRule",
    "Plugin",
    "PluginMetadata",
]
''',
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_manifest() -> None:
    create_file(
        "plugins/demo_plugin/manifest.py",
        '''"""Plugin manifest (``datas/plugin.yaml``) schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PluginMetadata(BaseModel):
    """Plugin manifest (``plugin.yaml``) contents."""

    name: str
    version: str
    description: str
    author: str | None = None
    license: str | None = None
    compatible_games: list[str] = Field(default_factory=list)
    disclaimer: str = ""
    dependencies: dict[str, str] = Field(default_factory=dict)
''',
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_data() -> None:
    create_file(
        "plugins/demo_plugin/data.py",
        '''"""Data files shipped with the demo plugin.

Game data lives as commented YAML documents in the ``datas/``
sub-directory of the plugin package. In development the data directory
is ``src/companion4soloplayer/plugins/demo_plugin/datas``. When
the plugin is compiled (Nuitka -> demo.pyd), ``__file__`` points
inside ``internal/plugins/demo/`` and the data files sit in the
sibling ``datas/`` directory of that same folder.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from companion4soloplayer.core.yaml_loader import load_yaml_file

# Data files (plugin.yaml, classes.yaml, ...) location.
DATA_DIR = Path(__file__).parent / "datas"
if not (DATA_DIR / "plugin.yaml").is_file():
    # Compiled build fallback: __file__ points at the plugin folder
    # itself, data files are kept in the sibling <name>/datas directory.
    DATA_DIR = Path(__file__).parent / "demo" / "datas"


def load_data(filename: str) -> Any:
    """Load a YAML data file shipped with the plugin.

    Args:
        filename: File name relative to the plugin data directory.

    Returns:
        Parsed document (mapping, sequence or scalar).

    Raises:
        YamlLoadError: If the file is not valid YAML.
    """
    return load_yaml_file(DATA_DIR / filename)


def get_stat(entity: Mapping[str, Any], keys: str | list[str]) -> int:
    """Return the first matching stat value of an entity.

    Stats may live at the top level of the entity or under the nested
    ``stats`` / ``base_stats`` mappings, depending on the data file.

    Args:
        entity: Character or monster record.
        keys: Stat name, or ordered list of fallback stat names.

    Returns:
        The stat value, or 0 when none of the keys is present.
    """
    names = [keys] if isinstance(keys, str) else list(keys)
    for name in names:
        for source in (entity, entity.get("stats", {}), entity.get("base_stats", {})):
            if isinstance(source, Mapping) and isinstance(source.get(name), (int, float)):
                return int(source[name])
    return 0
''',
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_plugin() -> None:
    create_file(
        "plugins/demo_plugin/plugin.py",
        '''"""Plugin facade: the ``Plugin`` class loaded by the core plugin loader.

The facade exposes the :class:`GamePlugin` protocol API, serves the
YAML data documents from the ``datas/`` directory and binds the hybrid
rule engine (declarative ``rules.yaml`` + Python rule elements).
"""

from __future__ import annotations

from typing import Any

from companion4soloplayer.core.rule_engine import RuleEngine

from .data import DATA_DIR, load_data
from .manifest import PluginMetadata


class Plugin:
    """Game System Demo Plugin implementation."""

    def __init__(self) -> None:
        """Initialize the plugin and load its manifest."""
        self._metadata = PluginMetadata(**load_data("plugin.yaml"))
        self._engine: RuleEngine | None = None

    @property
    def name(self) -> str:
        """Plugin name."""
        return self._metadata.name

    @property
    def version(self) -> str:
        """Plugin version."""
        return self._metadata.version

    @property
    def description(self) -> str:
        """Plugin description."""
        return self._metadata.description

    def get_classes(self) -> list[dict]:
        """Get character classes."""
        return list(load_data("classes.yaml"))

    def get_monsters(self) -> list[dict]:
        """Get monsters."""
        return list(load_data("monsters.yaml"))

    def get_items(self) -> list[dict]:
        """Get items."""
        return list(load_data("items.yaml"))

    def get_rules(self) -> dict:
        """Get game rules (declarative YAML document)."""
        return dict(self.get_rule_engine().rules)

    def get_rule_engine(self) -> RuleEngine:
        """Get the hybrid rule engine bound to this plugin package."""
        if self._engine is None:
            self._engine = RuleEngine.from_yaml(
                DATA_DIR / "rules.yaml",
                base_module=__package__,
            )
        return self._engine

    def create_component(self, kind: str) -> Any:
        """Instantiate a rule component declared in ``rules.yaml``.

        Args:
            kind: Rule kind (see ``core.rule_engine.RULE_KINDS``).

        Returns:
            The instantiated component (cached by the rule engine).
        """
        return self.get_rule_engine().component(kind)

    def generate_dungeon(self, config: dict) -> dict:
        """Generate a dungeon."""
        return {
            "rooms": [],
            "config": config,
        }
''',
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_classes_yaml() -> None:
    create_file(
        "plugins/demo_plugin/datas/classes.yaml",
        """# Character classes ----------------------------------------------------
# Original descriptions built on generic fantasy archetypes only.

- name: Adventurer
  description: A generic adventurer exploring the dungeon
  base_stats:
    combat: 3
    exploration: 3
    survival: 3
  abilities:
    - Basic Attack
    - Search

- name: Scout
  description: A keen-eyed explorer with cartographic skills
  base_stats:
    combat: 2
    exploration: 5
    survival: 3
  abilities:
    - Mapping
    - Detect Trap

- name: Bruiser
  description: A heavy-hitting warrior built for front lines
  base_stats:
    combat: 5
    exploration: 2
    survival: 3
  abilities:
    - Heavy Strike
    - Intimidate

- name: Scholar
  description: A learned individual versed in ancient lore
  base_stats:
    combat: 2
    exploration: 4
    survival: 4
  abilities:
    - Identify
    - Decipher

- name: Wizard
  description: A master of the arcane arts
  base_stats:
    body: 4
    mind: 6
  special_abilities:
    - Fireball
    - Heal
    - Teleport

- name: Archer
  description: A graceful archer from the forests
  base_stats:
    body: 5
    mind: 5
  special_abilities:
    - Precision Shot
    - Archery's Expert
""",
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_monsters_yaml() -> None:
    create_file(
        "plugins/demo_plugin/datas/monsters.yaml",
        """# Monsters -------------------------------------------------------------
# Original descriptions; generic dungeon fauna and constructs.

- name: Dungeon Crawler
  description: A small skittering creature lurking in shadows
  stats:
    combat: 1
    hp: 3

- name: Stone Golem
  description: An ancient construct of animated stone
  stats:
    combat: 4
    hp: 12

- name: Cave Bat Swarm
  description: A cloud of screeching bats filling the corridor
  stats:
    combat: 2
    hp: 6

- name: Goblin
  description: A small but cunning creature
  stats:
    hp: 3
    combat: 2
  abilities:
    - Sneak Attack

- name: Orc
  description: A brutal warrior of the wastes
  stats:
    hp: 5
    combat: 3
  abilities:
    - Berserker Rage

""",
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_items_yaml() -> None:
    create_file(
        "plugins/demo_plugin/datas/items.yaml",
        """# Items and equipment --------------------------------------------------
# Prices are in coins; quest items may be priceless (price 0).

- name: Iron Mace
  description: A sturdy blunt weapon
  type: weapon
  damage: 2
  price: 35

- name: Studded Leather
  description: Leather armor reinforced with metal studs
  type: armor
  defense: 1
  price: 45

- name: Map Fragment
  description: A torn piece of an old dungeon map
  type: quest
  effect: reveal_room   # uncovers one room on the current level
  price: 0

- name: Short Sword
  description: A simple but effective blade
  type: weapon
  damage: 1
  price: 25

- name: Leather Armor
  description: Basic protection made of hardened leather
  type: armor
  defense: 1
  price: 30

- name: Health Potion
  description: A magical potion that restores vitality
  type: consumable
  effect: heal_4     # restores 4 HP when consumed
  price: 50

- name: Torch
  description: Provides light in dark places
  type: tool
  duration: 10      # rounds of light
  price: 5
""",
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_rules_yaml() -> None:
    create_file(
        "plugins/demo_plugin/datas/rules.yaml",
        """# Rewritten rules ------------------------------------------------------
# The mechanics are re-expressed in our own words (see README.md for the
# legal disclaimer). Declarative data stays pure YAML; Python rule
# elements are bound through custom tags.

# Rule element implementations (hybrid YAML/Python architecture).
# `local:` references resolve inside this plugin's own package (classes
# re-exported by its `__init__.py`), keeping the names valid in
# development and in the compiled (.pyd) build. The oracle is a shared
# core rule element referenced through its absolute path.
# Parsing never imports anything: the core RuleEngine resolves and
# instantiates the classes on demand, enforcing a module allow-list.
implementations:
  character_creation: !pyclass local:CharacterCreationRule
  combat: !pyclass
    path: local:CombatRule
    params:
      attack_dice: !dice 2d6        # the classic 2d6 contest roll
      defense_dice: null            # the defender's stat is static
      attack_stat: [combat]
      defense_stat: [combat]
      base_damage: 1
      max_damage: 3
  loot: !pyclass
    path: local:LootRule
    params:
      rolls: 1                      # items drawn per loot action
  magic: !pyclass
    path: local:MagicRule
    params:
      dice: !dice 1d6
      difficulty: 4                 # target total for a casting check
      mana_cost: 1
  oracle: !pyclass companion4soloplayer.core.rules:OracleRule

# Dungeons are mapped on graph paper while they are explored.
cartography:
  description: Dungeons are mapped on a grid as they are explored.
  rules:
    - Roll 2d6 to determine room type
    - Draw room on grid paper
    - Mark doors, corridors, and features
    - Continue exploring until dungeon is complete

# Room type table: roll 2d6 and look up the range.
room_types:
  - roll: "2-3"
    type: corridor
    description: A narrow passage
  - roll: "4-6"
    type: small_room
    description: A small chamber
  - roll: "7-9"
    type: large_room
    description: A spacious hall
  - roll: "10-11"
    type: special_room
    description: A unique room
  - roll: "12"
    type: stairs
    description: Stairs to next level

# Combat: roll 2d6, add the combat stat, compare to the monster's
# combat value; equal or higher means the monster is defeated.
combat:
  description: Roll 2d6 and add combat stat. Compare to monster combat value.
  attack_dice: !dice 2d6
  steps:
    - Roll 2d6
    - Add combat stat
    - Compare to monster combat value
    - If equal or higher, monster is defeated

# Characters move a number of spaces equal to their movement each turn.
movement:
  description: Characters can move a number of spaces equal to their movement stat per turn.
  base_movement: 10

# Searching a room takes time and may reveal treasure or secret doors.
search:
  description: Characters can search rooms for treasure and secret doors.
  search_time: 1

""",
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_plugin_yaml() -> None:
    create_file(
        "plugins/demo_plugin/datas/plugin.yaml",
        """# Plugin manifest ------------------------------------------------------
# Read by the plugin loader; all fields are original wording (nominative
# fair use only when naming compatible games, see README.md disclaimer).

name: Demo Plugin
version: "1.0.0"          # semver
description: Plugin provided as a generic example
author: ultra-sonic-28
license: MIT

# Descriptive compatibility information only, never an endorsement.
compatible_games:
  - None or All :)

disclaimer: >-
  This plugin is neither affiliated with nor endorsed by DR Games.

dependencies:
  core_version: ">=0.1.0"
""",
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_rules_package_init() -> None:
    create_file(
        "plugins/demo_plugin/rules/__init__.py",
        '''"""Rule elements implemented by the demo plugin.

Each rule class lives in its own module, named after the class. The
classes are re-exported by the plugin package ``__init__`` so the
``local:`` references of ``datas/rules.yaml`` resolve against the
declaring package in development and in the compiled build alike.
"""

from .character_creation_rule import CharacterCreationRule
from .combat_rule import CombatRule
from .loot_rule import LootRule
from .magic_rule import MagicRule

__all__ = ["CharacterCreationRule", "CombatRule", "LootRule", "MagicRule"]
''',
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_rules_character_creation_rule() -> None:
    create_file(
        "plugins/demo_plugin/rules/character_creation_rule.py",
        '''"""Character creation rule element (class catalog in classes.yaml)."""

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
''',
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_rules_combat_rule() -> None:
    create_file(
        "plugins/demo_plugin/rules/combat_rule.py",
        '''"""Opposed-roll combat rule element (see the ``combat`` rule section)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from companion4soloplayer.core.dice_roller import DiceRoller
from companion4soloplayer.core.yaml_loader import DiceExpression

from ..data import get_stat


class CombatRule:
    """Opposed-roll combat resolution (see the ``combat`` rule section).

    The attacker rolls ``attack_dice`` plus their attack stat; the
    defender rolls ``defense_dice`` (when set) plus their defense stat.
    A non-negative margin deals ``base_damage`` plus the margin, capped
    at ``max_damage``; a negative margin deals no damage.
    """

    def __init__(
        self,
        *,
        attack_dice: DiceExpression | str | None = None,
        defense_dice: DiceExpression | str | None = None,
        attack_stat: str | list[str] = "attack",
        defense_stat: str | list[str] = "defense",
        base_damage: int = 1,
        max_damage: int = 3,
    ) -> None:
        """Initialize the rule (parameters come from ``rules.yaml``).

        Args:
            attack_dice: Dice notation rolled by the attacker.
            defense_dice: Dice notation rolled by the defender, or None
                when the defense value is static.
            attack_stat: Attacker stat name or ordered fallback list.
            defense_stat: Defender stat name or ordered fallback list.
            base_damage: Damage dealt on any successful attack.
            max_damage: Upper bound of the damage per attack.
        """
        self.attack_dice = DiceExpression.parse(attack_dice or "1d6")
        self.defense_dice = DiceExpression.parse(defense_dice) if defense_dice else None
        self.attack_stat = attack_stat
        self.defense_stat = defense_stat
        self.base_damage = base_damage
        self.max_damage = max_damage

    def resolve(
        self,
        attacker: Mapping[str, Any],
        defender: Mapping[str, Any],
        roller: DiceRoller | None = None,
    ) -> dict:
        """Resolve one attack of ``attacker`` against ``defender``.

        Args:
            attacker: Attacking character or monster record.
            defender: Defending character or monster record.
            roller: Optional dice roller (a fresh one when omitted).

        Returns:
            Result record with ``attack``, ``defense``, ``net``,
            ``success`` and ``damage`` entries.
        """
        roller = roller or DiceRoller()
        attack_score = self.attack_dice.roll(roller) + get_stat(attacker, self.attack_stat)
        defense_score = get_stat(defender, self.defense_stat)
        if self.defense_dice is not None:
            defense_score += self.defense_dice.roll(roller)
        net = attack_score - defense_score
        success = net >= 0
        damage = min(self.max_damage, self.base_damage + max(0, net)) if success else 0
        return {
            "attack": attack_score,
            "defense": defense_score,
            "net": net,
            "success": success,
            "damage": damage,
        }
''',
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_rules_loot_rule() -> None:
    create_file(
        "plugins/demo_plugin/rules/loot_rule.py",
        '''"""Loot rule element (random draw from the item catalog in items.yaml)."""

from __future__ import annotations

import random

from ..data import load_data


class LootRule:
    """Random loot drawn from the item catalog (items.yaml)."""

    def __init__(self, *, catalog: str = "items.yaml", rolls: int = 1) -> None:
        """Initialize the rule.

        Args:
            catalog: YAML file holding the item catalog.
            rolls: Number of items drawn by a default loot action.
        """
        self.catalog = catalog
        self.rolls = rolls

    def roll(self, count: int | None = None) -> list[dict]:
        """Draw random loot entries from the catalog.

        Args:
            count: Number of draws; defaults to the ``rolls`` parameter.

        Returns:
            The drawn item records.
        """
        items = list(load_data(self.catalog))
        draws = self.rolls if count is None else count
        if not items or draws <= 0:
            return []
        return [random.choice(items) for _ in range(draws)]
''',
    )


# ---------------------------------------------------------------------------
def _create_plugin_demo_rules_magic_rule() -> None:
    create_file(
        "plugins/demo_plugin/rules/magic_rule.py",
        '''"""Magic rule element (arcane casting check based on the mind stat)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from companion4soloplayer.core.dice_roller import DiceRoller
from companion4soloplayer.core.yaml_loader import DiceExpression

from ..data import get_stat


class MagicRule:
    """Arcane casting check based on the caster's mind stat."""

    def __init__(
        self,
        *,
        dice: DiceExpression | str = "1d6",
        difficulty: int = 4,
        mana_cost: int = 1,
        stat: str = "mind",
    ) -> None:
        """Initialize the rule (parameters come from ``rules.yaml``).

        Args:
            dice: Dice notation rolled for the casting check.
            difficulty: Target total needed for success.
            mana_cost: Mana spent on a casting attempt.
            stat: Caster stat added to the roll.
        """
        self.dice = DiceExpression.parse(dice)
        self.difficulty = difficulty
        self.mana_cost = mana_cost
        self.stat = stat

    def cast(
        self,
        spell: str,
        caster: Mapping[str, Any],
        roller: DiceRoller | None = None,
    ) -> dict:
        """Attempt to cast a spell.

        Args:
            spell: Spell or ability name.
            caster: Casting character record.
            roller: Optional dice roller.

        Returns:
            Result record with ``spell``, ``total``, ``difficulty``,
            ``success`` and ``mana_cost`` entries.
        """
        roller = roller or DiceRoller()
        total = self.dice.roll(roller) + get_stat(caster, self.stat)
        return {
            "spell": spell,
            "total": total,
            "difficulty": self.difficulty,
            "success": total >= self.difficulty,
            "mana_cost": self.mana_cost,
        }
''',
    )



# ---------------------------------------------------------------------------
def _create_plugin_demo_readme() -> None:
    create_file(
        "plugins/demo_plugin/README.md",
        """# Demo Plugin

Game System Demo Plugin.

## Disclaimer

The mechanics implemented are generic board game concepts that are not protected by copyright.

## Features

- Grid-based dungeon mapping
- 2d6 room generation
- Simple character progression
- Exploration mechanics

## Usage

This plugin is automatically loaded by Companion4SoloPlayer when selected in the application.
""",
    )


# ---------------------------------------------------------------------------
# User Interface module files
# ---------------------------------------------------------------------------
def create_ui_files() -> None:
    """Create the user interface files."""
    _print_step(" Creating UI files ")

    _create_ui_package_init()
    _create_ui_asset_utils()
    _create_ui_main_window()
    _create_ui_dialogs_package_init()
    _create_ui_dialogs_about_dialog()
    _create_ui_dialogs_quest_wizard()
    _create_ui_dialogs_settings_dialog()

    _print_success(" UI files created! ")


# ---------------------------------------------------------------------------
def _create_ui_package_init() -> None:
    # ui/__init__.py
    # NOTE: no version here - the version lives in the package metadata
    # (pyproject.toml) and is exposed by companion4soloplayer/__init__.py
    create_file(
        "ui/__init__.py",
        '''"""
User interface module for Companion4SoloPlayer.
"""
''',
    )


# ---------------------------------------------------------------------------
def _create_ui_asset_utils() -> None:
    # ui/asset_utils.py
    # Shared asset path resolution (source / installed / packaged modes)
    create_file(
        "ui/asset_utils.py",
        '''"""
Asset path resolution for Companion4SoloPlayer.

Locates the application assets in source, installed and packaged
(PyInstaller one-dir) modes.
"""

import sys
from pathlib import Path

LOGO_PATH = Path("assets") / "icons" / "logo-512x512.png"


def resolve_asset_path(relative_path: Path) -> Path:
    """Locate an asset file in source, installed and packaged modes.

    Args:
        relative_path: Asset path relative to the project root
            (e.g. "assets/icons/logo-512x512.png")

    Returns:
        Path to the asset file (may not exist if the asset is missing)
    """
    candidates: list[Path] = []

    # Packaged build: PyInstaller unpacks data files under sys._MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        candidates.append(Path(meipass) / relative_path)
    # Source run: project root sits three levels above this module
    # (asset_utils.py -> ui -> companion4soloplayer -> src)
    candidates.append(Path(__file__).resolve().parents[3] / relative_path)
    # Installed run (tests, pip-installed package): fall back to the
    # current working directory (project root in development)
    candidates.append(Path.cwd() / relative_path)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[-1]
''',
    )


# ---------------------------------------------------------------------------
def _create_ui_main_window() -> None:
    # ui/main_window.py
    create_file(
        "ui/main_window.py",
        '''"""
Main window module.
Contains the primary application window.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from companion4soloplayer.core.plugin_loader import PluginLoader
from companion4soloplayer.ui.asset_utils import LOGO_PATH, resolve_asset_path
from companion4soloplayer.ui.dialogs.about_dialog import AboutDialog
from companion4soloplayer.ui.dialogs.quest_wizard import QuestWizard
from companion4soloplayer.ui.dialogs.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        """Initialize the main window."""
        super().__init__()
        self.setWindowTitle("Companion4SoloPlayer")
        self.setMinimumSize(1200, 800)
        self.setWindowIcon(QIcon(str(resolve_asset_path(LOGO_PATH))))

        self._plugin_loader = PluginLoader()
        self._plugin_rows: dict[str, tuple[QPushButton, QLabel]] = {}
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_status_bar()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Header
        header = QLabel("Companion4SoloPlayer")
        header.setStyleSheet("font-size: 24px; font-weight: bold; padding: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Add tabs
        self._add_character_tab()
        self._add_quest_tab()
        self._add_dungeon_tab()
        self._add_plugins_tab()

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        new_action = QAction("&New Game", self)
        new_action.setShortcut("Ctrl+N")
        file_menu.addAction(new_action)

        open_action = QAction("&Open Game", self)
        open_action.setShortcut("Ctrl+O")
        file_menu.addAction(open_action)

        close_action = QAction("&Close Game", self)
        close_action.setEnabled(False)
        file_menu.addAction(close_action)

        save_action = QAction("&Save Game", self)
        save_action.setEnabled(False)
        save_action.setShortcut("Ctrl+S")
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Manage menu
        manage_menu = menu_bar.addMenu("&Manage")

        plugin_action = QAction("&Plugins", self)
        manage_menu.addAction(plugin_action)

        quest_action = QAction("&Quests", self)
        quest_action.triggered.connect(self._show_quest)
        manage_menu.addAction(quest_action)

        manage_menu.addSeparator()

        settings_action = QAction("&Settings", self)
        settings_action.triggered.connect(self._show_settings)
        manage_menu.addAction(settings_action)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        legal_action = QAction("&Legal Information", self)
        help_menu.addAction(legal_action)

    def _add_character_tab(self) -> None:
        """Add the character management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        label = QLabel("Character Management")
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)

        info = QLabel(
            "Manage your party of characters here.\\n"
            "Create, edit, and track stats, inventory, and equipment."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

        self.tab_widget.addTab(tab, "Characters")

    def _add_quest_tab(self) -> None:
        """Add the quest management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        label = QLabel("Quest Management")
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)

        info = QLabel(
            "Track your current quest objectives here.\\n"
            "Create custom quests or load community-made content."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

        self.tab_widget.addTab(tab, "Quests")

    def _add_dungeon_tab(self) -> None:
        """Add the dungeon generation tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        label = QLabel("Dungeon Generation")
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)

        info = QLabel(
            "Generate procedural dungeons or load existing ones.\\n"
            "Visualize rooms, corridors, and encounters on a grid."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

        self.tab_widget.addTab(tab, "Dungeon")

    def _add_plugins_tab(self) -> None:
        """Add the plugins management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        label = QLabel("Plugins")
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)

        info = QLabel(
            "Manage game plugins here.\\n"
            "Load a plugin on demand to make its content available."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # One row per discovered plugin with a Load/Unload button and a
        # status label showing the plugin version once loaded.
        for plugin_name in self._plugin_loader.discover_plugins():
            row = QHBoxLayout()
            name_label = QLabel(plugin_name)
            row.addWidget(name_label, stretch=1)

            status_label = QLabel("Not loaded")
            row.addWidget(status_label)

            button = QPushButton("Load")
            button.clicked.connect(
                lambda checked=False, name=plugin_name, btn=button, status=status_label: self._toggle_plugin(
                    name, btn, status
                )
            )
            row.addWidget(button)

            layout.addLayout(row)
            self._plugin_rows[plugin_name] = (button, status_label)

        layout.addStretch()

        self.tab_widget.addTab(tab, "Plugins")

    def _toggle_plugin(self, plugin_name: str, button: QPushButton, status_label: QLabel) -> None:
        """Load or unload a plugin on demand from the Plugins tab."""
        plugin = self._plugin_loader.get_plugin(plugin_name)
        if plugin is None:
            plugin = self._plugin_loader.load_plugin(plugin_name)
            if plugin is None:
                # Surface the underlying error: the released app has no
                # console, so prints from the loader are invisible.
                message = f"Failed to load plugin '{plugin_name}'."
                reason = self._plugin_loader.last_errors.get(plugin_name)
                if reason:
                    message = f"{message} {reason}"
                QMessageBox.warning(
                    self,
                    "Plugins",
                    message,
                )
                return
            status_label.setText(f"v{plugin.version} loaded")
            button.setText("Unload")
            self.status_bar.showMessage(f"Plugin '{plugin_name}' loaded")
        else:
            self._plugin_loader.unload_plugin(plugin_name)
            status_label.setText("Not loaded")
            button.setText("Load")
            self.status_bar.showMessage(f"Plugin '{plugin_name}' unloaded")

    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _show_about(self) -> None:
        """Show the About dialog."""
        dialog = AboutDialog(self)
        dialog.exec()

    def _show_settings(self) -> None:
        """Show the Settings wizard."""
        dialog = SettingsDialog(self)
        dialog.exec()

    def _show_quest(self) -> None:
        """Show the Quest wizard."""
        dialog = QuestWizard(self)
        dialog.exec()

''',
    )


# ---------------------------------------------------------------------------
def _create_ui_dialogs_package_init() -> None:
    # ui/dialogs/__init__.py
    create_file(
        "ui/dialogs/__init__.py",
        '''"""
Dialog windows for Companion4SoloPlayer.
"""
''',
    )


# ---------------------------------------------------------------------------
def _create_ui_dialogs_about_dialog() -> None:
    # ui/dialogs/about_dialog.py
    create_file(
        "ui/dialogs/about_dialog.py",
        '''"""
About dialog for Companion4SoloPlayer.

Shows the application logo on the left and the application name,
description, version and build datetime on the right, with a Close
button centered below.
"""

from importlib.metadata import PackageNotFoundError, metadata

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from companion4soloplayer import __version__
from companion4soloplayer.ui.asset_utils import LOGO_PATH, resolve_asset_path

try:
    from companion4soloplayer.build_info import BUILD_DATETIME
except ImportError:
    # build_info.py is written by the nox 'release' session; a fresh
    # source checkout may not have it yet.
    BUILD_DATETIME = "unknown"

try:
    DESCRIPTION = str(metadata("companion4soloplayer")["Summary"])
except PackageNotFoundError:
    # Package not installed (running from sources without pip install):
    # fall back to the static project description.
    DESCRIPTION = (
        "Open-source companion application for dungeon crawler style board games"
    )

APP_NAME = "Companion4SoloPlayer"
LOGO_SIZE = 128


class AboutDialog(QDialog):
    """About dialog: logo on the left, application info on the right."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the about dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("About " + APP_NAME)
        self.setWindowIcon(QIcon(str(resolve_asset_path(LOGO_PATH))))

        self._setup_ui()

        self.setFixedSize(400, 200)

    def _setup_ui(self) -> None:
        """Set up the two-column layout and the centered Close button."""
        layout = QVBoxLayout(self)

        columns_layout = QHBoxLayout()

        # Left column: application logo scaled to 128x128 pixels
        self.logo_label = QLabel()
        pixmap = QPixmap(str(resolve_asset_path(LOGO_PATH)))
        if not pixmap.isNull():
            pixmap = pixmap.scaled(
                LOGO_SIZE,
                LOGO_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_label.setPixmap(pixmap)
            self.logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        columns_layout.addWidget(self.logo_label)

        # Right column: application name, description, version and build
        # datetime (HTML for the name/version/date, plain text description)
        info_layout = QVBoxLayout()

        name_label = QLabel(f"<h2>{APP_NAME}</h2>")
        description_label = QLabel(DESCRIPTION)
        description_label.setWordWrap(True)
        version_label = QLabel(f"<b>Version:</b> {__version__}")
        build_date_label = QLabel(f"<b>Compiled at:</b> {BUILD_DATETIME}")
        info_layout.addWidget(name_label)
        info_layout.addWidget(description_label)
        info_layout.addWidget(version_label)
        info_layout.addWidget(build_date_label)
        info_layout.addStretch()

        columns_layout.addLayout(info_layout)
        layout.addLayout(columns_layout)

        # Close button centered below the two columns
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignHCenter)
''',
    )


# ---------------------------------------------------------------------------
def _create_ui_dialogs_quest_wizard() -> None:
    # ui/dialogs/quest_wizard.py
    create_file(
        "ui/dialogs/quest_wizard.py",
        '''"""
Quest creation wizard dialog.
Guides users through creating a new quest.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class QuestWizard(QDialog):
    """Wizard dialog for creating a new quest."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the quest wizard.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Create New Quest")
        self.setMinimumSize(600, 500)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the wizard interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Quest Creation Wizard")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Quest details group
        details_group = QGroupBox("Quest Details")
        details_layout = QFormLayout(details_group)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter quest name")
        details_layout.addRow("Name:", self.name_input)

        self.template_combo = QComboBox()
        self.template_combo.addItems([
            "Blank Quest",
            "Rescue Mission",
            "Boss Hunt",
            "Treasure Recovery",
            "Survival Challenge"
        ])
        details_layout.addRow("Template:", self.template_combo)

        layout.addWidget(details_group)

        # Description
        desc_group = QGroupBox("Description")
        desc_layout = QVBoxLayout(desc_group)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Enter quest description and objectives..."
        )
        desc_layout.addWidget(self.description_input)

        layout.addWidget(desc_group)

        # Parameters
        params_group = QGroupBox("Parameters")
        params_layout = QFormLayout(params_group)

        self.num_rooms_spin = QSpinBox()
        self.num_rooms_spin.setRange(5, 50)
        self.num_rooms_spin.setValue(10)
        params_layout.addRow("Number of rooms:", self.num_rooms_spin)

        self.difficulty_spin = QSpinBox()
        self.difficulty_spin.setRange(1, 10)
        self.difficulty_spin.setValue(1)
        params_layout.addRow("Difficulty level:", self.difficulty_spin)

        layout.addWidget(params_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.create_button = QPushButton("Create Quest")
        self.create_button.clicked.connect(self.accept)
        button_layout.addWidget(self.create_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def get_quest_data(self) -> dict:
        """Get the quest data entered by the user.

        Returns:
            Dictionary containing quest data
        """
        return {
            'name': self.name_input.text(),
            'template': self.template_combo.currentText(),
            'description': self.description_input.toPlainText(),
            'num_rooms': self.num_rooms_spin.value(),
            'difficulty': self.difficulty_spin.value()
        }
''',
    )


# ---------------------------------------------------------------------------
def _create_ui_dialogs_settings_dialog() -> None:
    # ui/dialogs/settings_dialog.py
    create_file(
        "ui/dialogs/settings_dialog.py",
        '''"""
Settings dialog for Companion4SoloPlayer.
Allows users to configure application preferences.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    """Settings dialog for application preferences."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the settings dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 400)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the settings interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Application Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Appearance group
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark", "System"])
        appearance_layout.addRow("Theme:", self.theme_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(12)
        appearance_layout.addRow("Font size:", self.font_size_spin)

        layout.addWidget(appearance_group)

        # Gameplay group
        gameplay_group = QGroupBox("Gameplay")
        gameplay_layout = QVBoxLayout(gameplay_group)

        self.auto_save_check = QCheckBox("Enable auto-save")
        self.auto_save_check.setChecked(True)
        gameplay_layout.addWidget(self.auto_save_check)

        self.sound_check = QCheckBox("Enable sound effects")
        self.sound_check.setChecked(True)
        gameplay_layout.addWidget(self.sound_check)

        self.animations_check = QCheckBox("Enable animations")
        self.animations_check.setChecked(True)
        gameplay_layout.addWidget(self.animations_check)

        layout.addWidget(gameplay_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.accept)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def get_settings(self) -> dict:
        """Get the current settings.

        Returns:
            Dictionary containing settings
        """
        return {
            'theme': self.theme_combo.currentText(),
            'font_size': self.font_size_spin.value(),
            'auto_save': self.auto_save_check.isChecked(),
            'sound': self.sound_check.isChecked(),
            'animations': self.animations_check.isChecked()
        }
''',
    )


# ---------------------------------------------------------------------------
# Unit test files
# ---------------------------------------------------------------------------
def create_unittest_files() -> None:
    """Create the unit test files."""
    _print_step(" Creating unit test files ")

    # Core unit tests
    _create_unittest_core_smoke_test()
    _create_unittest_core_oracle_rule()
    _create_unittest_core_rule_engine()
    _create_unittest_core_yaml_loader()

    # Plugins unit tests
    _create_unittest_plugins()

    _print_success(" Unit test files created! ")


# ---------------------------------------------------------------------------
def _create_unittest_core_smoke_test() -> None:
    # Smoke unit test for core
    smoke_core_unit_test = """
import importlib


# Only testing program import
def test_project_imports() -> None:
    importlib.import_module("companion4soloplayer")

# Only testing core import
def test_core_imports() -> None:
    importlib.import_module("companion4soloplayer.core")
"""
    create_file("tests_core/test_core_smoke.py", smoke_core_unit_test)


# ---------------------------------------------------------------------------
def _create_unittest_core_oracle_rule() -> None:
    # Tests for the shared oracle rule element
    content = '''"""Tests for the shared oracle rule element (``core.rules``)."""

from companion4soloplayer.core.dice_roller import DiceRoller
from companion4soloplayer.core.rules import OracleRule
from companion4soloplayer.core.rules.oracle_rule import OracleRule as OracleRuleImpl


def test_oracle_exported_by_core_rules_is_the_implementation() -> None:
    """``core.rules.OracleRule`` re-exports the class of its own module."""
    assert OracleRule is OracleRuleImpl


def test_oracle_answers_a_known_outcome() -> None:
    """The default 1d6 oracle answers one of the documented outcomes."""
    oracle = OracleRule()
    assert oracle.ask() in set(OracleRule.OUTCOMES.values())


def test_oracle_accepts_dice_notation() -> None:
    """The oracle accepts any dice expression (kept within 1..6 outcomes)."""
    oracle = OracleRule(dice="2d6")
    answer = oracle.ask(DiceRoller())
    assert answer in set(OracleRule.OUTCOMES.values())


def test_oracle_outcome_table_is_complete() -> None:
    """Every face of the die maps to an outcome with a yes/no answer."""
    assert sorted(OracleRule.OUTCOMES) == [1, 2, 3, 4, 5, 6]
    assert all(outcome.startswith(("yes", "no")) for outcome in OracleRule.OUTCOMES.values())
'''
    create_file("tests_core/test_oracle_rule.py", content)


# ---------------------------------------------------------------------------
def _create_unittest_core_rule_engine() -> None:
    # Tests for the hybrid rule engine (YAML declarations + Python classes)
    content = '''"""Tests for the hybrid rule engine (YAML declarations + Python classes)."""

from pathlib import Path

import pytest

from companion4soloplayer.core.dice_roller import DiceRoller
from companion4soloplayer.core.rule_engine import (
    RULE_KINDS,
    ImplementationError,
    ImplementationNotAllowedError,
    RuleEngine,
    RuleEngineError,
    UnknownRuleKindError,
)
from companion4soloplayer.core.yaml_loader import PyClassRef, load_yaml


class Widget:
    """Test component accepting constructor parameters."""

    def __init__(self, size: int = 1) -> None:
        self.size = size


def test_standard_rule_kinds() -> None:
    """The standard kinds cover the expected rule elements."""
    assert set(RULE_KINDS) >= {"character_creation", "combat", "loot", "magic", "oracle"}


def test_component_from_local_reference() -> None:
    """'local:' references resolve inside the declaring module."""
    engine = RuleEngine(
        load_yaml("""implementations:
  widget: !pyclass local:Widget
"""),
        base_module=__name__,
    )
    widget = engine.component("widget")
    assert isinstance(widget, Widget)
    assert widget.size == 1


def test_component_is_cached() -> None:
    """A rule kind is instantiated only once."""
    engine = RuleEngine({"implementations": {"widget": "local:Widget"}}, base_module=__name__)
    assert engine.component("widget") is engine.component("widget")


def test_component_params_from_yaml() -> None:
    """Constructor params declared in YAML are forwarded to the class."""
    engine = RuleEngine(
        load_yaml("""
            implementations:
              widget: !pyclass
                path: local:Widget
                params:
                  size: 5
            """),
        base_module=__name__,
    )
    assert engine.component("widget").size == 5


def test_absolute_reference_within_allow_list() -> None:
    """Absolute references to allowed modules are imported on demand."""
    engine = RuleEngine(
        {"implementations": {"roller": "companion4soloplayer.core.dice_roller:DiceRoller"}}
    )
    assert isinstance(engine.component("roller"), DiceRoller)


def test_reference_outside_allow_list_is_rejected() -> None:
    """Modules outside the allow-list are refused before any import."""
    engine = RuleEngine({"implementations": {"bad": PyClassRef(path="os:system")}})
    with pytest.raises(ImplementationNotAllowedError):
        engine.component("bad")


def test_unknown_rule_kind_raises() -> None:
    """Undeclared kinds raise an explicit error listing what exists."""
    engine = RuleEngine({"implementations": {"widget": "local:Widget"}}, base_module=__name__)
    with pytest.raises(UnknownRuleKindError):
        engine.component("combat")


def test_local_reference_without_base_module_raises() -> None:
    """A 'local:' reference requires the declaring module."""
    engine = RuleEngine({"implementations": {"widget": "local:Widget"}})
    with pytest.raises(ImplementationError):
        engine.component("widget")


def test_non_callable_reference_raises() -> None:
    """References must resolve to something instantiable."""
    engine = RuleEngine(
        {"implementations": {"bad": "companion4soloplayer.core.rule_engine:RULE_KINDS"}}
    )
    with pytest.raises(ImplementationError):
        engine.component("bad")


def test_non_mapping_rules_rejected() -> None:
    """The rules document must be a mapping."""
    with pytest.raises(RuleEngineError):
        RuleEngine([])  # type: ignore[arg-type]


def test_implementations_must_be_references() -> None:
    """Non-reference implementation values raise an explicit error."""
    engine = RuleEngine({"implementations": {"bad": 42}})
    with pytest.raises(RuleEngineError):
        _ = engine.implementations


def test_rules_property_returns_a_copy() -> None:
    """Callers cannot corrupt the engine by mutating the returned dict."""
    engine = RuleEngine({"combat": {"steps": []}}, base_module=__name__)
    rules = engine.rules
    rules["combat"] = None
    assert engine.get("combat") == {"steps": []}


def test_kinds_are_sorted() -> None:
    """The kinds property lists declared kinds alphabetically."""
    engine = RuleEngine(
        {"implementations": {"widget": "local:Widget", "oracle": "local:Widget"}},
        base_module=__name__,
    )
    assert engine.kinds == ["oracle", "widget"]


def test_from_yaml(tmp_path: Path) -> None:
    """The engine can be built directly from a rules file."""
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        "implementations:\\n  widget: !pyclass\\n    path: local:Widget\\n"
        "    params:\\n      size: 7\\n",
        encoding="utf-8",
    )
    engine = RuleEngine.from_yaml(rules, base_module=__name__)
    assert engine.component("widget").size == 7


def test_from_yaml_empty_file(tmp_path: Path) -> None:
    """An empty rules file raises an explicit error."""
    rules = tmp_path / "rules.yaml"
    rules.write_text("# nothing here\\n", encoding="utf-8")
    with pytest.raises(RuleEngineError):
        RuleEngine.from_yaml(rules, base_module=__name__)
'''
    create_file("tests_core/test_rule_engine.py", content)


# ---------------------------------------------------------------------------
def _create_unittest_core_yaml_loader() -> None:
    # Tests for the core YAML loader and its custom tags
    content = '''"""Tests for the core YAML loader and its custom tags."""

from pathlib import Path

import pytest
import yaml

from companion4soloplayer.core.dice_roller import DiceRoller
from companion4soloplayer.core.yaml_loader import (
    C4SPSafeLoader,
    DiceExpression,
    PyClassRef,
    YamlLoadError,
    YamlTagError,
    load_yaml,
    load_yaml_file,
    register_tag,
)


def test_load_basic_document_with_comments() -> None:
    """Comments are ignored and plain data is typed natively."""
    doc = load_yaml("""
        # leading comment
        name: test
        count: 3
        enabled: true
        items: [a, b]
        """)
    assert doc == {"name": "test", "count": 3, "enabled": True, "items": ["a", "b"]}


def test_pyclass_scalar_form() -> None:
    """The scalar form parses 'module:Class' without importing anything."""
    ref = load_yaml("impl: !pyclass companion4soloplayer.core.dice_roller:DiceRoller")["impl"]
    assert isinstance(ref, PyClassRef)
    assert ref.module == "companion4soloplayer.core.dice_roller"
    assert ref.attr == "DiceRoller"
    assert not ref.is_local


@pytest.mark.parametrize("path", ["local:Thing", ":Thing"])
def test_pyclass_local_forms(path: str) -> None:
    """'local:Class' and ':Class' both target the declaring module."""
    ref = PyClassRef.parse(path)
    assert ref.is_local
    assert ref.module == "local"
    assert ref.attr == "Thing"


def test_pyclass_mapping_form_with_nested_params() -> None:
    """The mapping form carries constructor params, including !dice."""
    doc = load_yaml("""
        impl: !pyclass
          path: local:CombatRule
          params:
            attack_dice: !dice 2d6
            base_damage: 2
        """)
    ref = doc["impl"]
    assert isinstance(ref, PyClassRef)
    assert ref.path == "local:CombatRule"
    assert isinstance(ref.params["attack_dice"], DiceExpression)
    assert (ref.params["attack_dice"].count, ref.params["attack_dice"].sides) == (2, 6)
    assert ref.params["base_damage"] == 2


def test_pyclass_rejects_unknown_keys() -> None:
    """Unknown keys in the mapping form raise an explicit error."""
    with pytest.raises(YamlTagError):
        load_yaml("impl: !pyclass {path: local:A, oops: 1}")


def test_pyclass_rejects_invalid_reference() -> None:
    """Malformed references raise an explicit error."""
    with pytest.raises(YamlTagError):
        load_yaml("impl: !pyclass not_a_reference")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2d6", DiceExpression(2, 6, 0)),
        ("1d20+3", DiceExpression(1, 20, 3)),
        ("d6-1", DiceExpression(1, 6, -1)),
    ],
)
def test_dice_parse_notations(text: str, expected: DiceExpression) -> None:
    """Dice notations are parsed into typed values."""
    assert DiceExpression.parse(text) == expected


def test_dice_parse_rejects_invalid_notation() -> None:
    """Invalid dice notations raise an explicit error."""
    with pytest.raises(YamlTagError):
        DiceExpression.parse("2x6")


def test_dice_tag_and_roll() -> None:
    """The !dice tag yields a rollable expression."""
    expr = load_yaml("pool: !dice 2d6")["pool"]
    assert isinstance(expr, DiceExpression)
    results, total = expr.roll_detail(DiceRoller())
    assert len(results) == 2
    assert sum(results) == total
    assert expr.notation == "2d6"


def test_unsafe_python_tags_are_rejected() -> None:
    """!!python tags stay forbidden with the safe loader."""
    with pytest.raises(yaml.YAMLError):
        load_yaml("!!python/object/apply:os.system ['echo pwned']")


def test_unknown_custom_tag_is_rejected() -> None:
    """Tags without a registered constructor raise a parser error."""
    with pytest.raises(yaml.YAMLError):
        load_yaml("value: !unknown_tag 42")


def test_load_yaml_file_reports_path(tmp_path: Path) -> None:
    """Parse errors include the offending file path."""
    broken = tmp_path / "broken.yaml"
    broken.write_text("key: [unclosed", encoding="utf-8")
    with pytest.raises(YamlLoadError) as excinfo:
        load_yaml_file(broken)
    assert str(broken) in str(excinfo.value)


def test_load_yaml_file_missing_file(tmp_path: Path) -> None:
    """A missing file raises OSError."""
    with pytest.raises(FileNotFoundError):
        load_yaml_file(tmp_path / "does_not_exist.yaml")


def test_load_yaml_file_success(tmp_path: Path) -> None:
    """A valid file is parsed like its inline counterpart."""
    path = tmp_path / "data.yaml"
    path.write_text("# comment\\nvalue: 42\\n", encoding="utf-8")
    assert load_yaml_file(path) == {"value": 42}


def test_register_tag_extends_the_loader() -> None:
    """Plugins may register additional safe tags."""
    try:
        register_tag("!test_tag", lambda loader, node: f"custom:{loader.construct_scalar(node)}")
        assert load_yaml("v: !test_tag hello")["v"] == "custom:hello"
    finally:
        C4SPSafeLoader.yaml_constructors.pop("!test_tag", None)


def test_register_tag_requires_bang_prefix() -> None:
    """Tag names must start with '!'; the loader registry stays untouched."""
    with pytest.raises(ValueError, match="start with"):
        register_tag("no_bang", lambda loader, node: None)
'''
    create_file("tests_core/test_yaml_loader.py", content)


# ---------------------------------------------------------------------------
def _create_unittest_plugins() -> None:
    # Smoke unit test for plugins
    smoke_plugins_unit_test = '''"""Tests for the dynamic plugin loader."""

import ast
import shutil
from pathlib import Path

import pytest

from companion4soloplayer.core.plugin_loader import PluginLoader
from companion4soloplayer.core.rule_engine import RULE_KINDS
from companion4soloplayer.core.rules import OracleRule

PLUGINS_SRC = Path(__file__).resolve().parents[2] / "src" / "companion4soloplayer" / "plugins"
EXPECTED_PLUGINS = {"demo"}


@pytest.fixture
def loader() -> PluginLoader:
    """Return a plugin loader pointing at the source plugins."""
    return PluginLoader(plugins_dir=str(PLUGINS_SRC))


def test_discover_plugins_finds_all_source_plugins(loader: PluginLoader) -> None:
    names = set(loader.discover_plugins())
    assert names >= EXPECTED_PLUGINS


def test_load_plugin_from_source(loader: PluginLoader) -> None:
    plugin = loader.load_plugin("demo")
    assert plugin is not None
    assert plugin.name
    assert plugin.version
    assert plugin.description
    assert loader.get_plugin("demo") is plugin


def test_load_unknown_plugin_returns_none(loader: PluginLoader) -> None:
    assert loader.load_plugin("does_not_exist") is None


def test_last_error_records_the_failure_reason(loader: PluginLoader) -> None:
    """A failed load stores a readable reason (releases have no console)."""
    assert loader.load_plugin("does_not_exist") is None
    reason = loader.last_errors["does_not_exist"]
    assert "not found" in reason


def test_last_error_is_dropped_after_a_successful_load(loader: PluginLoader) -> None:
    """A successful load clears any stale error recorded for the plugin."""
    assert loader.load_plugin("does_not_exist") is None
    assert "does_not_exist" in loader.last_errors
    plugin = loader.load_plugin("demo")
    assert plugin is not None
    assert "demo" not in loader.last_errors


def test_load_plugin_is_cached(loader: PluginLoader) -> None:
    first = loader.load_plugin("demo")
    second = loader.load_plugin("demo")
    assert first is second


def test_unload_plugin(loader: PluginLoader) -> None:
    loader.load_plugin("demo")
    assert loader.unload_plugin("demo") is True
    assert loader.get_plugin("demo") is None
    assert loader.unload_plugin("demo") is False


def test_plugin_exposes_gameplugin_api(loader: PluginLoader) -> None:
    plugin = loader.load_plugin("demo")
    assert plugin is not None
    assert isinstance(plugin.get_classes(), list)
    assert isinstance(plugin.get_monsters(), list)
    assert isinstance(plugin.get_items(), list)
    assert isinstance(plugin.get_rules(), dict)
    assert plugin.generate_dungeon({"size": 5})["config"] == {"size": 5}


def test_load_compiled_plugin_extension(tmp_path: Path) -> None:
    """A compiled .pyd placed next to a plugin data dir is loaded directly."""
    import importlib.machinery

    pytest.importorskip("setuptools")
    suffix = importlib.machinery.EXTENSION_SUFFIXES[0]
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()

    # Compile a tiny standalone extension module exposing Plugin.
    ext_src = tmp_path / "fake_plugin.c"
    ext_src.write_text(
        """
#include <Python.h>

static PyObject *Plugin_get_name(PyObject *self, PyObject *args) {
    return PyUnicode_FromString("fake");
}

static PyMethodDef plugin_methods[] = {
    {"get_name", Plugin_get_name, METH_NOARGS, NULL},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT, "fake", NULL, -1, plugin_methods
};

PyMODINIT_FUNC PyInit_fake(void) {
    return PyModule_Create(&moduledef);
}
""",
        encoding="utf-8",
    )
    from setuptools import Extension, setup
    from setuptools._distutils.errors import CompileError, DistutilsError  # type: ignore

    try:
        setup(
            name="fake",
            ext_modules=[Extension("fake", [str(ext_src)])],
            script_args=[
                "build_ext",
                f"--build-lib={tmp_path / 'lib'}",
                f"--build-temp={tmp_path / 'tmp'}",
            ],
        )
    except (CompileError, DistutilsError, OSError, SystemExit):
        pytest.skip("No C compiler available on this machine")
    built = next((tmp_path / "lib").rglob(f"fake_plugin{suffix}"))

    plugin_dir = plugins_dir / "fake"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.yaml").write_text("name: fake\\n", encoding="utf-8")
    shutil.copy2(built, plugins_dir / f"fake{suffix}")

    loader = PluginLoader(plugins_dir=str(plugins_dir))
    assert loader.discover_plugins() == ["fake"]

    plugin = loader.load_plugin("fake")
    assert plugin is not None
    assert loader.get_plugin("fake") is plugin


# ----------------------------------------------------------------------
# Hybrid YAML/Python rule engine
# ----------------------------------------------------------------------

PLUGIN_RULE_KINDS = {
    "demo": {"character_creation", "combat", "loot", "oracle", "magic"},
}


@pytest.mark.parametrize("name", sorted(PLUGIN_RULE_KINDS))
def test_plugin_rule_engine_declares_standard_kinds(loader: PluginLoader, name: str) -> None:
    """Every plugin declares its rule elements using standard kinds."""
    plugin = loader.load_plugin(name)
    assert plugin is not None
    kinds = set(plugin.get_rule_engine().kinds)
    assert kinds == PLUGIN_RULE_KINDS[name]
    assert kinds <= set(RULE_KINDS)


@pytest.mark.parametrize("name", sorted(PLUGIN_RULE_KINDS))
def test_character_creation_component(loader: PluginLoader, name: str) -> None:
    """The character creation rule builds a character from the catalog."""
    plugin = loader.load_plugin(name)
    assert plugin is not None
    creator = plugin.create_component("character_creation")
    first_class = plugin.get_classes()[0]
    character = creator.create(first_class["name"], "Test Hero")
    assert character["name"] == "Test Hero"
    assert character["class"] == first_class["name"]
    assert character["stats"] == first_class["base_stats"]
    assert character["abilities"]
    # Components are cached by the rule engine.
    assert plugin.create_component("character_creation") is creator


def test_combat_component_resolves_attack(loader: PluginLoader) -> None:
    """The combat rule resolves an attack with the documented keys."""
    plugin = loader.load_plugin("demo")
    assert plugin is not None
    combat = plugin.create_component("combat")
    result = combat.resolve({"body": 8}, {"body": 4})
    assert {"attack", "defense", "net", "success", "damage"} <= set(result)
    assert result["success"] is (result["net"] >= 0)
    assert isinstance(result["damage"], int)
    assert 0 <= result["damage"] <= combat.max_damage


def test_magic_component_casts_spell(loader: PluginLoader) -> None:
    """The magic rule resolves a casting check for demo plugin."""
    plugin = loader.load_plugin("demo")
    assert plugin is not None
    magic = plugin.create_component("magic")
    result = magic.cast("Fireball", {"mind": 6})
    assert result["spell"] == "Fireball"
    assert isinstance(result["success"], bool)
    assert result["difficulty"] == 4


@pytest.mark.parametrize("name", sorted(PLUGIN_RULE_KINDS))
def test_loot_component_draws_items(loader: PluginLoader, name: str) -> None:
    """The loot rule draws entries from the item catalog."""
    plugin = loader.load_plugin(name)
    assert plugin is not None
    items = plugin.create_component("loot").roll(2)
    assert len(items) == 2
    assert all(item in plugin.get_items() for item in items)


@pytest.mark.parametrize("name", sorted(PLUGIN_RULE_KINDS))
def test_oracle_component_answers(loader: PluginLoader, name: str) -> None:
    """The oracle is the shared core rule element and answers a known outcome."""
    plugin = loader.load_plugin(name)
    assert plugin is not None
    oracle = plugin.create_component("oracle")
    assert type(oracle) is OracleRule
    assert oracle.ask() in set(oracle.OUTCOMES.values())


@pytest.mark.parametrize("name", sorted(PLUGIN_RULE_KINDS))
def test_get_rules_returns_declarative_document(loader: PluginLoader, name: str) -> None:
    """The declarative rules expose the combat section alongside tags."""
    plugin = loader.load_plugin(name)
    assert plugin is not None
    rules = plugin.get_rules()
    assert "combat" in rules
    assert "implementations" in rules
    assert rules["combat"]["steps"]


# ----------------------------------------------------------------------
# Source layout: one file per class, YAML data in datas/, rules in rules/
# ----------------------------------------------------------------------


def test_datas_directory_holds_the_yaml_files() -> None:
    """Every YAML data file lives in the plugin ``datas/`` sub-directory."""
    for name in sorted(PLUGIN_RULE_KINDS):
        package_dir = PLUGINS_SRC / f"{name}_plugin"
        assert list(package_dir.glob("*.yaml")) == []
        assert (package_dir / "datas" / "plugin.yaml").is_file()
        assert (package_dir / "datas" / "rules.yaml").is_file()


def test_package_init_declares_no_class() -> None:
    """The plugin ``__init__.py`` is a facade: classes live in their own modules."""
    for name in sorted(PLUGIN_RULE_KINDS):
        init_path = PLUGINS_SRC / f"{name}_plugin" / "__init__.py"
        tree = ast.parse(init_path.read_text(encoding="utf-8"))
        defined = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        assert defined == [], f"classes still defined in {init_path}: {defined}"


@pytest.mark.parametrize("name", sorted(PLUGIN_RULE_KINDS))
def test_local_rules_live_in_the_rules_subpackage(loader: PluginLoader, name: str) -> None:
    """'local:' components are classes of the plugin ``rules/`` sub-package."""
    plugin = loader.load_plugin(name)
    assert plugin is not None
    creator = plugin.create_component("character_creation")
    expected = f"companion4soloplayer.plugins.{name}_plugin.rules"
    assert creator.__class__.__module__.startswith(expected)


def test_oracle_is_shared_by_every_plugin(loader: PluginLoader) -> None:
    """The three plugins share the very same core OracleRule class."""
    oracle_classes = set()
    for name in sorted(PLUGIN_RULE_KINDS):
        plugin = loader.load_plugin(name)
        assert plugin is not None
        oracle_classes.add(type(plugin.create_component("oracle")))
    assert oracle_classes == {OracleRule}

'''
    create_file("tests_plugins/test_plugins_smoke.py", smoke_plugins_unit_test)


# ---------------------------------------------------------------------------
# UI test files
# ---------------------------------------------------------------------------
def create_uitest_files() -> None:
    """Create the UI test files."""
    _print_step(" Creating UI test files ")

    _create_uitest_conftest()
    _create_uitest_main_window()
    _create_uitest_about_dialog()

    _print_success(" UI test files created! ")


# ---------------------------------------------------------------------------
def _create_uitest_conftest() -> None:
    # conftest.py for UI testing
    conftest_py = '''
"""
Pytest configuration for UI tests.

Forces Qt to use the "offscreen" platform plugin so the GUI tests run
headless and deterministically, even in CI environments without a display.
Must be set before PySide6 is imported by any test module.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

'''
    create_file("tests_ui/conftest.py", conftest_py)


# ---------------------------------------------------------------------------
def _create_uitest_main_window() -> None:
    # Main window
    main_window_uitest_py = '''
"""
Smoke tests for the Qt GUI.

Verifies that the application launches (main window shown) and exits
cleanly. More advanced interaction tests will be added later.
"""

import sys

import pytest
from PySide6.QtGui import QAction
from pytestqt.qtbot import QtBot

from companion4soloplayer import __version__
from companion4soloplayer import main as main_module
from companion4soloplayer.ui.main_window import MainWindow


class _StubApplication:
    """
    Minimal stand-in for QApplication used to test the main() entry point.

    pytest-qt already owns the real QApplication singleton, and PySide6
    forbids creating a second one. Substituting the QApplication symbol in
    the main module lets main() run its launch/exit flow against the
    existing event-loop-less test context.
    """

    def __init__(self, argv: list[str]) -> None:
        """Store the arguments and default attributes."""
        self.argv = argv
        self.application_name: str | None = None
        self.application_version: str | None = None

    def setApplicationName(self, name: str) -> None:  # noqa: N802
        """Record the application name (Qt naming convention kept)."""
        self.application_name = name

    def setApplicationVersion(self, version: str) -> None:  # noqa: N802
        """Record the application version (Qt naming convention kept)."""
        self.application_version = version

    def exec(self) -> int:
        """Return immediately, as if the event loop exited normally."""
        return 0


def test_main_window_launches(qtbot: QtBot) -> None:
    """The main window is created, shown and correctly initialized."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    assert window.isVisible()
    assert window.windowTitle() == "Companion4SoloPlayer"
    assert not window.windowIcon().isNull()
    # The four expected tabs are present: Characters, Quests, Dungeon, Plugins
    assert window.tab_widget.count() == 4
    assert window.status_bar.currentMessage() == "Ready"


def test_main_window_closes_cleanly(qtbot: QtBot) -> None:
    """Closing the main window hides it without error (no deferred crash)."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    assert window.isVisible()

    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)

    assert not window.isVisible()


def test_exit_action_closes_application(qtbot: QtBot) -> None:
    """The File > Exit menu action closes the main window."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    # The Exit action was created with the window as parent, so it is
    # reachable among the window's child actions (Qt naming: "E&xit").
    exit_actions = [
        action
        for action in window.findChildren(QAction)
        if action.text() == "E&xit"
    ]
    assert len(exit_actions) == 1

    exit_actions[0].trigger()
    assert not window.isVisible()


def test_main_entry_point_launches_and_exits(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The main() entry point starts the application and exits cleanly.

    QApplication is replaced by a stub because pytest-qt already created
    the real singleton. The stub's exec() returns immediately, simulating
    a normal application exit.
    """
    created: list[_StubApplication] = []

    def application_factory(argv: list[str]) -> _StubApplication:
        """Build a stub application and keep track of it."""
        app = _StubApplication(argv)
        created.append(app)
        return app

    monkeypatch.setattr(main_module, "QApplication", application_factory)
    monkeypatch.setattr(sys, "exit", lambda code=0: (_ for _ in ()).throw(SystemExit(code)))

    with pytest.raises(SystemExit) as excinfo:
        main_module.main()

    # Normal exit code, application name/version applied, window shown
    assert excinfo.value.code == 0
    assert len(created) == 1
    assert created[0].application_name == "Companion4SoloPlayer"
    assert created[0].application_version == __version__

'''
    create_file("tests_ui/test_main_window.py", main_window_uitest_py)


# ---------------------------------------------------------------------------
def _create_uitest_about_dialog() -> None:
    # AboutDialog
    about_dialog_uitest_py = '''
"""
Tests for the About dialog and its wiring in the main window.
"""

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from companion4soloplayer import __version__
from companion4soloplayer.ui.dialogs.about_dialog import (
    DESCRIPTION,
    LOGO_SIZE,
    AboutDialog,
)
from companion4soloplayer.ui.main_window import MainWindow


def test_about_dialog_shows(qtbot: QtBot) -> None:
    """The About dialog shows the logo and the four info lines."""
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    assert not dialog.windowIcon().isNull()

    texts = [label.text() for label in dialog.findChildren(QLabel) if label.text()]
    assert any("Companion4SoloPlayer" in text for text in texts)
    assert DESCRIPTION in texts
    assert any(
        text.startswith("<b>Version:</b>") and __version__ in text for text in texts
    )
    assert any(text.startswith("<b>Compiled at:</b>") for text in texts)

    pixmap = dialog.logo_label.pixmap()
    assert pixmap is not None
    assert pixmap.size().width() == LOGO_SIZE
    assert pixmap.size().height() == LOGO_SIZE

    # Close button present below the two columns
    assert dialog.close_button.text() == "Close"


def test_close_button_closes_dialog(qtbot: QtBot) -> None:
    """Clicking the centered Close button closes the dialog."""
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    dialog.close_button.click()
    qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=5000)

    assert not dialog.isVisible()


def test_about_action_opens_dialog(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Help > About menu action opens the About dialog."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    calls: list[int] = []
    monkeypatch.setattr(AboutDialog, "exec", lambda self: calls.append(1))

    about_actions = [
        action for action in window.findChildren(QAction) if action.text() == "&About"
    ]
    assert len(about_actions) == 1
    about_actions[0].trigger()

    assert calls == [1]
'''
    create_file("tests_ui/test_about_dialog.py", about_dialog_uitest_py)


# ---------------------------------------------------------------------------
# Main project files
# ---------------------------------------------------------------------------
def create_project_files() -> None:
    """Create the main project files."""
    _print_step(" Creating project files ")

    _create_project_readme()
    _create_project_license()
    _create_project_gitignore()
    _print_success(" README.md, LICENSE and .gitignore created! ")

    _create_project_pyproject()
    _create_project_build_info()
    _print_success(" Project configuration files created! ")

    _create_project_mkdocs_yml()
    _create_project_mkdocs_mdfiles()
    _create_project_mkdocs_index()
    _create_project_mkdocs_features()
    _create_project_mkdocs_custom_css()
    _create_project_mkdocs_custom_js()
    _print_success(" Documentation configuration files created! ")

    _create_project_package_init()
    _create_project_main()
    _print_success(" Main project files created! ")


# ---------------------------------------------------------------------------
def _create_project_mkdocs_yml() -> None:
    mkdocs_yml = """# Companion4SoloPlayer documentation configuration
site_name: Companion4SoloPlayer
site_description: Companion4SoloPlayer Technical Documentation
site_author: ultra-sonic-28

docs_dir: docs
site_dir: site
dev_addr: 127.0.0.1:8001

theme:
  name: material
  language: fr
  logo: assets/logo-64x64.png
  features:
    - navigation.tabs
    - navigation.tabs.sticky
    - navigation.sections
    - navigation.expand
    - navigation.path
    - navigation.top
    - content.code.annotate
    - content.tabs.link
    - content.action.edit
  palette:
    scheme: default
    primary: deep orange
    accent: deep orange

extra_css:
  - assets/custom.css

extra_javascript:
  - assets/custom.js

plugins:
  - search
  - mermaid2:
      version: 10.9.0
  - mkdocstrings:
      handlers:
        python:
          paths: [".", "scripts", "src/companion4soloplayer"]
          options:
            filters: []
            docstring_style: google
            show_source: true
            show_root_heading: true
            show_category_heading: true
            show_if_no_docstring: true
            show_docstring_attributes: true
            show_docstring_functions: true
            show_docstring_classes: true
            show_docstring_type_aliases: true
            show_docstring_modules: true
            show_docstring_description: true
            show_docstring_examples: true
            show_docstring_other_parameters: true
            show_docstring_parameters: true
            show_docstring_raises: true
            show_docstring_returns: true
            show_docstring_type_parameters: true
            show_docstring_warns: true
            show_docstring_yields: true
            annotations_path: brief
            modernize_annotations: true
            line_length: 60
            separate_signature: true
            show_signature_annotations: true
            show_signature_type_parameters: false
            show_attribute_values: true
            show_overloads: true
            show_inheritance_diagram: true
            inheritance_diagram_direction: TD

markdown_extensions:
  - admonition
  - footnotes
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
nav:
  - Accueil: index.md
  - 'User Guide':
    - Features: 'features.md'
    - 'Build Toolchain' : 'noxfile.md'
    - Scripts:
      - 'Plugins Compilation': 'scripts/compile_plugins.md'
      - 'Icon Generation': 'scripts/make_icon.md'
      - 'Logo Resize': 'scripts/resize_logo.md'
  - Companion4SoloPlayer:
    - companion4soloplayer: 'companion4soloplayer/companion4soloplayer.md'
    - main:
      - main: 'companion4soloplayer/main.md'
    - Core:
      - 'Character Tracker': 'companion4soloplayer/core/character_tracker.md'
      - 'Combat Resolver': 'companion4soloplayer/core/combat_resolver.md'
      - 'Dice Roller': 'companion4soloplayer/core/dice_roller.md'
      - 'Plugin Loader': 'companion4soloplayer/core/plugin_loader.md'
      - 'Procedural Generator': 'companion4soloplayer/core/procedural_generator.md'
      - 'Quest Manager': 'companion4soloplayer/core/quest_manager.md'
      - 'YAML Loader': 'companion4soloplayer/core/yaml_loader.md'
      - 'Rule Engine': 'companion4soloplayer/core/rule_engine.md'
      - 'Oracle Rule': 'companion4soloplayer/core/rules/oracle_rule.md'
    - Plugins:
      - 'Demo': 'companion4soloplayer/plugins/demo_plugin/plugin.md'
    - UI:
        - 'MainWindow': 'companion4soloplayer/ui/main_window.md'
        - Dialogs:
            - 'AboutDialog': 'companion4soloplayer/ui/dialogs/about_dialog.md'
            - 'SettingsDialog': 'companion4soloplayer/ui/dialogs/settings_dialog.md'
            - 'QuestWizard': 'companion4soloplayer/ui/dialogs/quest_wizard.md'
"""

    create_file("mkdocs.yml", mkdocs_yml)


# ---------------------------------------------------------------------------
def _create_project_mkdocs_custom_css() -> None:
    create_file(
        "docs/assets/custom.css",
        """/* Custom CSS for Companion4SoloPlayer */
/* Ensure that the content takes up at least the full height of the screen. */
body {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
}

/* Main content */
.main-content {
    flex: 1;
}

/* Main container */
.md-grid {
    max-width: 100%;
}

/* Sticky footer */
footer {
    position: sticky;
    bottom: 0;
}

/* Color of the text for the name and version number of the application in the footer */
.c-white {
    color: white;
}

/* Specific styles for printing / PDF */
@media print {
    * {
      animation: none !important;
      transition: none !important;
    }

    /* Adjust margins/font size if necessary */
    body {
      font-size: 12pt;
      margin: 0;
    }
}

"""
    )


# ---------------------------------------------------------------------------
def _create_project_mkdocs_custom_js() -> None:
    create_file(
        "docs/assets/custom.js",
        """/* Custom JavaScript for Companion4SoloPlayer */
document.addEventListener('DOMContentLoaded', function() {
    const footer = document.querySelector('footer');
    footer.innerHTML = `
    <div class="md-footer-meta md-typeset">
        <div class="md-footer-meta__inner md-grid">
            <div class="md-copyright">
                Made with
                <a href="https://squidfunk.github.io/mkdocs-material/" target="_blank" rel="noopener">
                    Material for MkDocs
                </a>
                and
                <a href="https://mkdocstrings.github.io/" target="_blank" rel="noopener">
                mkdocstrings
                </a>
            </div>
            <span class="md-copyright c-white">Companion4SoloPlayer <i>v0.1.0</i></span>
        </div>
    </div>
`;
});
"""
    )


# ---------------------------------------------------------------------------
def _create_project_mkdocs_mdfiles() -> None:
    create_file(
        "docs/companion4soloplayer/companion4soloplayer.md",
        """Technical documentation for Companion 4 Solo Player modules, classes, and functions.
"""
    )

    create_file("docs/companion4soloplayer/main.md", "::: main")

    # Build Toolchain
    create_file("docs/noxfile.md", "::: noxfile")

    # Scripts
    _create_project_mkdocs_compile_plugins()
    create_file("docs/scripts/make_icon.md", "::: make_icon")
    create_file("docs/scripts/resize_logo.md", "::: resize_logo")

    # Core files
    create_file("docs/companion4soloplayer/core/character_tracker.md", "::: core.character_tracker")
    create_file("docs/companion4soloplayer/core/combat_resolver.md", "::: core.combat_resolver")
    create_file("docs/companion4soloplayer/core/dice_roller.md", "::: core.dice_roller")
    create_file("docs/companion4soloplayer/core/plugin_loader.md", "::: core.plugin_loader")
    create_file("docs/companion4soloplayer/core/procedural_generator.md", "::: core.procedural_generator")
    create_file("docs/companion4soloplayer/core/quest_manager.md", "::: core.quest_manager")
    create_file("docs/companion4soloplayer/core/rule_engine.md", "::: core.rule_engine")
    create_file("docs/companion4soloplayer/core/rules/oracle_rule.md", "::: core.rules.oracle_rule")
    create_file("docs/companion4soloplayer/core/yaml_loader.md", "::: core.yaml_loader")

    # Plugins files
    create_file("docs/companion4soloplayer/plugins/demo_plugin/plugin.md", "::: plugins.demo_plugin")

    # UI files
    create_file("docs/companion4soloplayer/ui/main_window.md", "::: ui.main_window")
    create_file("docs/companion4soloplayer/ui/dialogs/about_dialog.md", "::: ui.dialogs.about_dialog")
    create_file("docs/companion4soloplayer/ui/dialogs/settings_dialog.md", "::: ui.dialogs.settings_dialog")
    create_file("docs/companion4soloplayer/ui/dialogs/quest_wizard.md", "::: ui.dialogs.quest_wizard")


# ---------------------------------------------------------------------------
def _create_project_mkdocs_compile_plugins() -> None:
    create_file(
        "docs/scripts/compile_plugins.md",
        """# Plugin Compilation

This page describes how Companion4SoloPlayer compiles game plugins into
extension modules (`.pyd`) using Nuitka and the Zig compiler.

## Overview

Each plugin package under `src/companion4soloplayer/plugins` is compiled
with Nuitka (module mode) into a standalone extension library. The C
compilation backend is the Zig compiler shipped in `.bintools/`.

```
demo_plugin           ->  build/plugins/demo.pyd
```

**Toolchain:** Python → Nuitka (`--module --zig`) → `zig cc` (clang).

## Process Flow

The script `scripts/compile_plugins.py` orchestrates the entire build.
Plugins are recompiled only when needed: if any source file (`__init__.py`
or data file) is newer than the compiled `.pyd`, the plugin is rebuilt;
otherwise the existing library is kept. Pass `--force` to rebuild every
plugin regardless of timestamps.

```mermaid
flowchart TD
    classDef startEnd fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,color:#000
    classDef process fill:#e1f5fe,stroke:#01579b,stroke-width:1px,color:#000
    classDef decision fill:#fff3e0,stroke:#e65100,stroke-width:1px,color:#000
    classDef tool fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#000
    classDef file fill:#fce4ec,stroke:#880e4f,stroke-width:1px,color:#000

    Start([Start: python scripts/compile_plugins.py]):::startEnd
    Start --> ParseArgs[Parse arguments\n--output-dir, --force]:::process
    ParseArgs --> Discover[Discover plugins\nin src/.../plugins/*_plugin/]:::process

    Discover --> Loop{For each\nplugin package}:::decision

    Loop --> CheckForce{--force flag\nused?}:::decision
    CheckForce -- Yes --> PrepareBuild
    CheckForce -- No --> CheckTimestamps{Recompilation needed?\n.pyd missing or\nsource is newer}:::decision

    CheckTimestamps -- No --> SkipCompile[Skip compilation\nRefresh data files only]:::process
    CheckTimestamps -- Yes --> PrepareBuild

    subgraph Build [Compilation Phase]
        direction TB
        PrepareBuild[Create temp dir\nMirror package as name\nstrip _plugin suffix]:::process
        PrepareBuild --> SetupEnv[Setup environment\nPATH += .bintools/zig\nPYTHONPATH += temp\nNUITKA_CACHE_DIR = temp]:::process
        SetupEnv --> RunNuitka[Run Nuitka\npython -m nuitka --module --zig]:::tool
        RunNuitka --> ZigCC[Nuitka calls zig cc\nCompile C backend]:::tool
        ZigCC --> GenPyd[Generates name.cp3xx.pyd]:::file
        GenPyd --> CopyPyd[Copy .pyd to\noutput_dir/name.pyd]:::file
    end

    SkipCompile --> CopyData
    CopyPyd --> CopyData[Copy .json and .md to\noutput_dir/name/]:::file

    CopyData --> Next{More plugins?}:::decision
    Next -- Yes --> Loop
    Next -- No --> Summary[Print summary\nPlugins compiled / skipped]:::process
    Summary --> End([End of script]):::startEnd
```

## Compilation Toolchain

The following sequence diagram details how the script interacts with the
file system, Nuitka, and the Zig compiler during the actual compilation
of a single plugin.

```mermaid
sequenceDiagram
    participant Script as compile_plugins.py
    participant FS as File System
    participant Nuitka as Nuitka
    participant Zig as Zig (zig cc)

    Script->>FS: Read src/.../plugin/__init__.py and .json
    Script->>FS: Check timestamps (.pyd vs sources)

    alt Recompilation needed
        Script->>FS: Create temp dir, copy __init__.py as <name>
        Note over Script,FS: The '_plugin' suffix is stripped<br/>(e.g. demo_plugin → demo)

        Script->>Nuitka: Run `nuitka --module --zig <name>`
        Note over Script,Nuitka: PATH includes .bintools/zig<br/>PYTHONUTF8=1

        Nuitka->>Zig: Invoke `zig cc` to compile C
        Zig-->>Nuitka: Returns compiled object / .pyd

        Nuitka-->>Script: Success, .pyd generated in temp/out
        Script->>FS: Copy .pyd to build/plugins/<name>.pyd
    else Up to date
        Script->>FS: Skip compilation
    end

    Script->>FS: Copy .yaml/.md to build/plugins/<name>/
    Note over Script,FS: Data files are always synced<br/>even if the .pyd is not recompiled.
```

## Output Layout

The YAML data files of each plugin are copied into
`build/plugins/<plugin_name>/` next to the compiled library, so the
released application layout is:

```
internal/plugins/
    demo.pyd
    demo/
        plugin.yaml, classes.yaml, ...
        ...
```

## Usage

```bash
python scripts/compile_plugins.py [--output-dir build/plugins] [--force]
```

| Argument | Default | Description |
|---|---|---|
| `--output-dir` | `build/plugins` | Directory receiving the compiled plugins |
| `--force` | *(off)* | Recompile every plugin, ignoring timestamps |

## API Reference

::: compile_plugins
"""
    )

# ---------------------------------------------------------------------------
def _create_project_mkdocs_index() -> None:
    create_file(
        "docs/index.md",
        """# ![Logo Companion4SoloPlayer](assets/logo-64x64.png) Welcome to the Companion4SoloPlayer Technical Documentation

Welcome to the technical documentation for **Companion4SoloPlayer** (C4SP), an open-source, modular companion desktop application designed to streamline and enhance tabletop dungeon crawler board game sessions.

This site provides comprehensive technical documentation detailing the architecture, modules, classes, and APIs of the Companion4SoloPlayer application.

---

## Context & Vision

Companion4SoloPlayer is an independent, non-profit companion application created for players and Game Masters of dungeon crawler style board games and solo/co-op tabletop role-playing games.

The application assists players at the game table by managing:

- Character statistics, inventory, and health tracking.
- Combat resolution and damage calculation.
- Flexible dice rolling mechanics (standard polyhedrals, modifiers, roll histories).
- Quest objectives and scenario progression tracking.
- Procedural dungeon, room, and encounter generation.
- Game system expansion via an extensible, decoupled plugin architecture.

This documentation site is aimed at **developers, contributors, and technical enthusiasts** who wish to understand the inner workings of Companion4SoloPlayer, build and package the desktop application, develop custom game plugins, or contribute new features and bug fixes.

For a functional, user-oriented walkthrough of every capability provided by the application, please explore the [Features](features.md) guide.

---

## Goals of this Documentation

1. **Architecture & Design Principles**: Explain how Companion4SoloPlayer separates pure-Python, deterministic game logic (`core`) from the desktop graphical user interface (`ui`), and how dynamic plugin loading works at runtime.
2. **Complete API Reference**: Provide structured, automatically generated reference pages powered by [mkdocstrings](https://mkdocstrings.github.io/) for all public modules, classes, methods, and functions.
3. **Plugin Developer Onboarding**: Offer clear insights into the `GamePlugin` interface, YAML data formats, and plugin lifecycle to empower developers to create new system adaptations.
4. **Developer Enablement**: Document local environment setup, build workflows (PyInstaller / Nuitka / Nox), automated test suites, and documentation contribution processes.

---

## Documentation Structure

The documentation follows the architectural layout of the source repository and is divided into several main areas:

### 1. User & Functional Guides
- **[Features](features.md)**: A complete, granular breakdown of every functional capability in Companion4SoloPlayer, organized by subsystem (Character Tracking, Combat Resolution, Dice Rolling, Quest Management, Procedural Dungeon Generation, Plugin System, and UI).

### 2. Application Entry Points (`companion4soloplayer`)
- **[Package Root](companion4soloplayer/companion4soloplayer.md)**: Overview of the root package, metadata, build information, and version stamping.
- **[Main Entry Point](companion4soloplayer/main.md)**: Application bootstrap, Qt application initialization, and CLI argument handling.

### 3. Core Engine (`core`)
The `core` package contains pure-Python game mechanics, completely independent of any UI framework:

- **[Character Tracker](companion4soloplayer/core/character_tracker.md)**: Pydantic-based data models (`Character`) and multi-member party tracking logic (`CharacterTracker`).
- **[Combat Resolver](companion4soloplayer/core/combat_resolver.md)**: Attack calculations, strength modifiers, armor mitigation, and automated health updates (`CombatResolver`).
- **[Dice Roller](companion4soloplayer/core/dice_roller.md)**: Polyhedral dice rolling engine (`DiceRoller`), supporting single dice, multi-dice pools, and static modifiers.
- **[Plugin Loader](companion4soloplayer/core/plugin_loader.md)**: Dynamic plugin discovery, abstract contract definition (`GamePlugin`), compiled extension loading (`.pyd`), and fallback source loading.
- **[Procedural Generator](companion4soloplayer/core/procedural_generator.md)**: Seeded random generation for dungeon layouts, room dimensions, corridors, intersections, and level-scaled difficulty (`ProceduralGenerator`).
- **[Quest Manager](companion4soloplayer/core/quest_manager.md)**: Quest definition, multi-step objective tracking, completion states, and reward distribution (`QuestManager`, `Quest`, `Objective`, `QuestStatus`).
- **[Oracle Rule](companion4soloplayer/core/rules/oracle_rule.md)**: Shared yes/no oracle rule element (`OracleRule`) used by every plugin through an absolute `!pyclass` reference.

### 4. Game Plugins (`plugins`)
Companion4SoloPlayer includes built-in game plugins demonstrating how game-specific rules, classes, monsters, and items plug into the core engine:

- **[Demo Plugin](companion4soloplayer/plugins/demo_plugin/plugin.md)**: Generic game system demo plugin integration.

### 5. User Interface (`ui`)
Desktop front-end built on **PySide6 (Qt for Python)**:

- **[Main Window](companion4soloplayer/ui/main_window.md)**: Multi-tab desktop application interface (Characters, Quests, Dungeon, Plugins), menu bars, and status updates.
- **Dialogs**:
	- **[About Dialog](companion4soloplayer/ui/dialogs/about_dialog.md)**: Application branding, version information, compilation timestamp, and legal notices.
	- **[Settings Dialog](companion4soloplayer/ui/dialogs/settings_dialog.md)**: Preferences for UI themes (Light/Dark/System), font sizing, auto-save, sound effects, and animations.
	- **[Quest Wizard](companion4soloplayer/ui/dialogs/quest_wizard.md)**: Interactive modal dialog guiding users through creating customized quests with room counts and difficulty levels.

---

## Building and Browsing the Documentation Locally

The documentation is authored in Markdown and rendered using **MkDocs** with the **Material for MkDocs** theme and **mkdocstrings**.

### Local Live-Reload Server

To preview the documentation locally with automatic hot-reloading upon file edits:

```bash
nox -s docs-live
```

Once started, open [http://127.0.0.1:8001](http://127.0.0.1:8001) in your browser.

### Building Static Documentation

To build the static HTML site (output to the `site/` directory):

```bash
nox -s docs
```

The static site can be inspected locally or hosted on any static web hosting platform (such as GitHub Pages).

---

## Conventions & Documentation Standards

- **Google-Style Docstrings**: All Python modules, classes, and methods use Google-style docstring conventions. Type annotations are directly extracted from Python type hints.
- **Cross-Referencing**: Hyperlinks between symbols and modules are resolved automatically by `mkdocstrings`.
- **Legal Compliance**: Technical documentation adheres strictly to project guidelines (no copyrighted text, trademarked terms used strictly under nominative fair use or rewritten using generic equivalents).

"""
    )


# ---------------------------------------------------------------------------
def _create_project_mkdocs_features() -> None:
    create_file(
        "docs/features.md",
        """# Features

**Companion4SoloPlayer (C4SP)** is a modular, open-source desktop companion application designed for tabletop dungeon crawler board games and solo/co-op tabletop role-playing games (TTRPGs). It assists players and Game Masters alike by automating tedious bookkeeping, generating dynamic dungeon scenarios, rolling dice, tracking quest progression, resolving combat encounters, and supporting multiple game systems through a clean plugin architecture.

This document details every feature provided by Companion4SoloPlayer, organized by subsystem.

---

## Table of Contents

- [Overview and Key Strengths](#overview-and-key-strengths)
- [Character Management](#character-management)
  - [Character Data Model](#character-data-model)
  - [Party Tracking and Multi-Character Support](#party-tracking-and-multi-character-support)
  - [Hit Points and Status Management](#hit-points-and-status-management)
  - [Inventory and Equipment](#inventory-and-equipment)
  - [Customizable Statistics](#customizable-statistics)
- [Combat Resolution System](#combat-resolution-system)
  - [Damage Calculation Engine](#damage-calculation-engine)
  - [Damage Application and Health Modification](#damage-application-and-health-modification)
  - [Turn and Encounter Assistance](#turn-and-encounter-assistance)
- [Dice Rolling Engine](#dice-rolling-engine)
  - [Standard Polyhedral and Custom Sided Dice](#standard-polyhedral-and-custom-sided-dice)
  - [Multi-Dice Rolls](#multi-dice-rolls)
  - [Static Modifiers and Calculated Totals](#static-modifiers-and-calculated-totals)
  - [Cryptographic and Pseudo-Random Generation](#cryptographic-and-pseudo-random-generation)
- [Quest and Objective Tracking](#quest-and-objective-tracking)
  - [Quest Lifecycle and Status States](#quest-lifecycle-and-status-states)
  - [Granular Objectives](#granular-objectives)
  - [Active Quest Management](#active-quest-management)
  - [Quest Creation Wizard](#quest-creation-wizard)
  - [Scenario Rewards](#scenario-rewards)
- [Procedural Dungeon Generation](#procedural-dungeon-generation)
  - [Randomized Architecture](#randomized-architecture)
  - [Room Types and Geometric Variety](#room-types-and-geometric-variety)
  - [Level-Scaled Difficulty Modifiers](#level-scaled-difficulty-modifiers)
  - [Seeded Generation for Reproducibility](#seeded-generation-for-reproducibility)
- [Plugin Architecture and Multi-Game Systems](#plugin-architecture-and-multi-game-systems)
  - [Dynamic Plugin Discovery and Loading](#dynamic-plugin-discovery-and-loading)
  - [Compiled C-Extension (.pyd) Support](#compiled-c-extension-pyd-support)
  - [Standardized GamePlugin Contract](#standardized-gameplugin-contract)
  - [Built-In Plugins](#built-in-plugins)
    - [Demo Plugin](#demo-plugin)
  - [Legal Protection and Clean-Room Decoupling](#legal-protection-and-clean-room-decoupling)
- [User Interface (PySide6 and Qt)](#user-interface-pyside6-and-qt)
  - [Multi-Tab Desktop Experience](#multi-tab-desktop-experience)
  - [Interactive Character Panel](#interactive-character-panel)
  - [Quest and Adventure Tracker Panel](#quest-and-adventure-tracker-panel)
  - [Dungeon Exploration and Generation Panel](#dungeon-exploration-and-generation-panel)
  - [Plugin Manager Panel](#plugin-manager-panel)
  - [Settings Dialog](#settings-dialog)
  - [About and Licensing Dialog](#about-and-licensing-dialog)
- [Build, Packaging and Standalone Distribution](#build-packaging-and-standalone-distribution)

---

## Overview and Key Strengths

Companion4SoloPlayer provides a unified, distraction-free companion experience at the table. Rather than replacing the tactile joy of miniature movement and physical tokens, C4SP removes administrative friction:

1. **System Agnostic Core**: Core mechanics (dice, health, basic combat math, procedural layouts, quests) operate independently of any specific rulebook.
2. **Pluggable Game Rules**: Game-specific items, monsters, special abilities, and room tables are loaded dynamically via plugins.
3. **Pure Desktop Independence**: No cloud account, no telemetry, no mandatory internet connection. Everything runs locally on Windows.
4. **Fast and Lightweight**: Implemented with Python 3.13 and PySide6, packaged into an optimized standalone binary via PyInstaller or Nuitka.

---

## Character Management

The character management system is driven by `companion4soloplayer.core.character_tracker`, providing strict validation and state handling via Pydantic models.

### Character Data Model
Each character is represented as a strongly-typed `Character` record comprising:

- **Identity**: Character `name` (unique identifier within party) and `character_class` (e.g., Barbarian, Wizard, Dwarf, Cleric).
- **Vitality**: `max_hp` (derived or configured maximum health points) and `current_hp` (real-time health during an encounter).
- **Statistics Block**: A flexible dictionary mapping arbitrary stat identifiers to integer values (e.g., `body`, `mind`, `strength`, `defense`, `speed`).
- **Inventory**: A list of items, consumables, treasure tokens, and gear currently held in the hero's backpack.
- **Equipment**: Equipped weapons, armor, shields, and rings actively modifying attributes or usable in combat.

### Party Tracking and Multi-Character Support
The `CharacterTracker` engine coordinates party management:

- **Party Registry**: Store and manipulate multiple active adventurers simultaneously.
- **Creation Factory**: `create_character(name, character_class, stats)` validates uniqueness and computes initial maximum health based on system conventions (e.g., defaulting to the `body` stat or standard baseline).
- **Instant Retrieval**: Quick lookup by name (`get_character(name)`) for combat, inventory, or UI updates.
- **Party Maintenance**: Safe character removal (`remove_character(name)`) when characters retire or perish.

### Hit Points and Status Management
- Automatic clamping: Current hit points cannot drop below zero or exceed the character's maximum health pool.
- Visual feedback: In-app health displays and color-coded status indicators in the user interface.

### Inventory and Equipment
- Equipment slots can be adjusted during town or camp phases.
- Real-time inventory tracking for loot collected during dungeon runs (gold sacks, gems, potions, quest artifacts).

### Customizable Statistics
- Supports differing attribute systems across board games:
	- *Classic dungeon crawlers*: Body points, Mind points, Attack dice, Defend dice.
	- *Pen-and-paper crawlers*: Level, Life points, Attack bonus, Defense bonus, Gold.
	- *Cartographic games*: Agility, Brawn, Awareness, Discipline, Hit points.

---

## Combat Resolution System

The combat engine is implemented in `companion4soloplayer.core.combat_resolver` via `CombatResolver`, orchestrating encounters between players and adversaries.

### Damage Calculation Engine
- **`calculate_damage(attacker, defender, weapon_damage)`**:
	- Extracts the attacker's offensive modifiers (e.g., `strength` attribute or attack bonus).
	- Calculates base output: `base_damage = weapon_damage + attacker_strength`.
	- Determines defender mitigation based on active defense (e.g., `armor`, shield, or defense stat).
	- Yields final net damage: `max(0, base_damage - defense)`.
	- Guarantees non-negative damage values to prevent inadvertent healing from defense over-matching.

### Damage Application and Health Modification
- **`apply_damage(character, damage)`**:
	- Deducts the computed damage amount directly from the target character's `current_hp`.
	- Automatically bounds the remaining hit points at a minimum of `0`.
	- Returns the post-damage remaining HP, triggering UI death/downed alerts if vitality reaches zero.

### Turn and Encounter Assistance
- Provides automated arithmetic so players can resolve complex attack vs. defense rolls without manual table consultations.
- Easily customizable by plugins to incorporate system-specific mechanics (such as exploding dice or armor-piercing strikes).

---

## Dice Rolling Engine

The dice subsystem in `companion4soloplayer.core.dice_roller` handles all randomized dice requirements.

### Standard Polyhedral and Custom Sided Dice
- **Arbitrary Sides**: Simulates any polyhedral die size: d4, d6, d8, d10, d12, d20, d100, or any arbitrary custom integer value `sides >= 1`.
- Input validation safeguards against invalid parameters (e.g., 0-sided or negative dice counts).

### Multi-Dice Rolls
- **`roll_dice(count, sides)`**: Rolls an arbitrary number of dice (`count >= 1`) and returns the complete list of individual die rolls.
- Preserves individual dice values for game rules that require checking matching pairs, critical successes, or individual dice thresholds (such as skull/shield combat dice).

### Static Modifiers and Calculated Totals
- **`roll_with_modifier(count, sides, modifier)`**:
	- Rolls `count` dice of `sides`.
	- Returns a tuple `(results, total)` containing both the individual roll list and the total including positive or negative modifiers.
- **`roll_single(sides)`**: Convenience method for quick single-die checks, saving throws, or wandering monster tables.

### Cryptographic and Pseudo-Random Generation
- Uses Python's uniform random generation distribution (`random.randint`), guaranteeing statistically unbiased roll spreads across thousands of iterations.

---

## Quest and Objective Tracking

Implemented in `companion4soloplayer.core.quest_manager`, the quest manager tracks campaign arcs, scenario conditions, and mission progression.

### Quest Lifecycle and Status States
Each scenario is monitored through explicit states defined in `QuestStatus`:

- `NOT_STARTED`: The quest is planned or loaded, but party has not entered the dungeon.
- `IN_PROGRESS`: The heroes are actively pursuing objectives within the dungeon.
- `COMPLETED`: All primary objectives have been successfully fulfilled.
- `FAILED`: Failure conditions have been met (e.g., party wipe or turn counter expired).

### Granular Objectives
- Quests contain multiple structured `Objective` objects.
- Each objective tracks its description and a boolean `completed` state.
- **`complete_objective(quest_name, objective_index)`**:
	- Marks an objective completed.
	- Automatically inspects the remaining objectives: when the final objective is fulfilled, the quest status automatically transitions to `COMPLETED`.

### Active Quest Management
- **`start_quest(name)`**: Marks the specified quest as `IN_PROGRESS` and sets it as the currently active scenario in the companion context.
- **`get_active_quest()`**: Fast reference to the current scenario for UI status bars and quick lookups.

### Quest Creation Wizard
- User interface modal (`QuestWizard`) allowing players to quickly design adventures:
	- Scenario Title and Story Description.
	- Quest Template selection (e.g., "Dungeon Crawl", "Rescue", "Assassination", "Artifact Retrieval").
	- Target dungeon room count.
	- Difficulty rating (1–10).

### Scenario Rewards
- Quests support reward dictionaries (e.g., gold bounties, bonus experience, artifact codes) automatically granted upon completion.

---

## Procedural Dungeon Generation

The procedural layout engine (`companion4soloplayer.core.procedural_generator`) creates dynamic, non-repetitive dungeon layouts for solo exploration or randomized Game Master sessions.

### Randomized Architecture
- **`generate_dungeon(num_rooms, level)`**: Generates an ordered series of connected architectural spaces tailored to the target party experience level.
- Assigns sequential unique IDs, room classifications, and atmospheric flavor text.

### Room Types and Geometric Variety
- Supports distinct architectural categories generated via `generate_room(room_type, level)`:
	- **Corridors**: Narrow passages with varying lengths and widths (e.g., 1x5, 1x8, 2x6).
	- **Chambers / Rooms**: Square and rectangular combat spaces (4x4 small chambers, 5x5 medium halls, 6x8 grand halls).
	- **Intersections**: 3x3 crossroads and 4x4 four-way junctions creating branching path choices.
	- **Stairs**: Passages leading downward to deeper dungeon tiers.

### Level-Scaled Difficulty Modifiers
- Generates a difficulty coefficient scaled by dungeon tier: `difficulty = level / 10`.
- Enables plugins and combat engines to adjust trap hazards, monster spawns, and chest quality based on procedural room depth.

### Seeded Generation for Reproducibility
- Accepts an optional `seed` parameter upon initialization: `ProceduralGenerator(seed=12345)`.
- Guarantees identical dungeon layouts across sessions, enabling tournament play, shared seeds among community players, and bug-free save states.

---

## Plugin Architecture and Multi-Game Systems

The modular core uses `companion4soloplayer.core.plugin_loader` to support different board game systems without touching the core codebase.

### Dynamic Plugin Discovery and Loading
- Scans user directories, application directories, and built-in folders for compatible game extensions.
- Transparently discovers plugins packaged as either source packages or compiled libraries.

### Compiled C-Extension (.pyd) Support
- Fully compatible with compiled C-extensions (`.pyd`) generated by **Nuitka**.
- High performance, protected distribution, and instant loading via `importlib.machinery.ExtensionFileLoader`.
- Graceful development fallback: loads standard Python source packages (`*_plugin`) when running in development environments.

### Standardized GamePlugin Contract
Every plugin adheres to the abstract `GamePlugin` interface:

- **`name` / `version` / `description`**: Metadata properties describing the game system.
- **`get_classes()`**: Returns character classes available in the game, including starting attributes, starting equipment, and archetype traits.
- **`get_monsters()`**: Returns bestiary data (monster statistics, attack dice, body points, special rules).
- **`get_items()`**: Returns armory and equipment catalogs (weapons, armor, tools, prices, modifiers).
- **`get_rules()`**: Structured rulebook summaries, action limits, movement rules, and turn flow.
- **`generate_dungeon(config)`**: Custom dungeon layout and table-rolling logic customized for the specific game system.

### Built-In Plugins
Companion4SoloPlayer includes one example plugin:

#### Demo Plugin
- Illustrates the plugin architecture with a simple generic game system implementation.

### Legal Protection and Clean-Room Decoupling
- Strictly enforces clean-room design and legal safety:
	- No copyrighted rulebook verbatim texts or protected artwork.
	- No trademarked proper nouns; generic terms and nominative fair use compatibility indicators only.
	- System-specific plugins isolate proprietary rule concepts from the MIT-licensed core codebase.

---

## User Interface (PySide6 and Qt)

Companion4SoloPlayer features a desktop user interface built with **PySide6** (`src/companion4soloplayer/ui/`).

### Multi-Tab Desktop Experience
The `MainWindow` centralizes session management across four intuitive functional tabs:

1. **Characters Tab**: Inspect the active adventuring party, view current health gauges, review inventories, and create or recruit new characters.
2. **Quests Tab**: Browse active objectives, track completion milestones, and initiate new adventures.
3. **Dungeon Tab**: Procedurally roll and visualize new rooms, track corridors, and manage dungeon levels.
4. **Plugins Tab**: View all installed game system plugins, toggle plugins on/off dynamically at runtime, and check system versions.

### Interactive Character Panel
- Live hit point modification buttons (+ / - damage).
- Form inputs for creating new characters on the fly.
- Real-time updates synchronized across all UI views.

### Quest and Adventure Tracker Panel
- Interactive objective checklists where players click to complete steps.
- Visual completion badges when a scenario objective concludes.
- Direct invocation of the **Quest Creation Wizard**.

### Dungeon Exploration and Generation Panel
- One-click procedural generation of rooms, corridors, and stairs.
- Real-time display of dimensions, descriptions, and danger ratings.

### Plugin Manager Panel
- Discovers installed plugins and renders them in a list with checkboxes.
- Toggling a plugin enables or disables its rules and content in real-time without restarting the desktop application.

### Settings Dialog
The `SettingsDialog` lets players personalize their desktop experience:

- **Appearance**: Toggle between **Light**, **Dark**, and **System** themes; customize font size (8 pt to 24 pt) for high-DPI displays or projector usage.
- **Gameplay Options**:
	- Toggle automatic background game saves.
	- Toggle sound effect cues for dice rolls and events.
	- Toggle UI animations.

### About and Licensing Dialog
The `AboutDialog` displays:

- Application logo (128x128 high-DPI asset).
- Version number, build number and build timestamp (`BUILD_DATETIME`).
- Project description and direct link to licensing/legal documentation.

---

## Build, Packaging and Standalone Distribution

Companion4SoloPlayer is equipped with automated developer tooling for testing and standalone packaging:

- **PyInstaller Bundling**: Packages the application into a standalone Windows executable (`dist/companion4soloplayer/companion4soloplayer.exe`) with all dependencies embedded.
- **Nuitka Compilation**: Compiles the core and plugins into high-performance native machine code binaries.
- **Nox Automation**: Orchestrates setup, formatting, linting, unit tests, coverage reporting, documentation generation, and release packaging with single commands:
	- `nox -s setup-dev`: Configures a complete virtual development environment.
	- `nox -s lint`: Run QoL checks: black, ruff, mypy.
	- `nox -s test-unit`: Executes the full unit test suite with coverage thresholds.
	- `nox -s test-ui`: Executes the full ui test suite with coverage thresholds.
	- `nox -s compile-plugins`: Compile every game plugin into a .pyd extension (build/plugins/).
	- `nox -s release`: Automatically increments build numbers, builds the executable, and generates release archives with SHA-256 checksums.
	- `nox -s check-venv`: Check if a virtual environment is active.
	- `nox -s docs`: Create technical documentation, static build
	- `nox -s docs-live`: Create technical documentation, live reloading server
	- `nox -s stats`: Compute code statistics (lines of code, etc.).
"""
    )


# ---------------------------------------------------------------------------
def _create_project_readme() -> None:
    # README.md - Part 1
    readme_part1 = """# Companion4SoloPlayer (C4SP)

Open-source companion application for dungeon crawler style board games.

## Description

**Companion4SoloPlayer** is a free, non-profit tool designed to make it easy to manage dungeon crawler style board game sessions. The application is modular and can support several games through a plugin system.

## Legal Disclaimer

**Companion4SoloPlayer** is an independent, free, non-profit, open-source tool designed to make it easy to manage dungeon crawler style board game sessions.

This application is **neither affiliated with, nor endorsed by, nor sponsored by** Hasbro, Games Workshop, Ganesha Games, DR Games, BlackOath Entertainment, Nuts! Publishing, or any other rights holder related to the supported games.

All trademarks mentioned are the property of their respective owners.

This application does not reproduce any text, artwork, logo, or copyrighted element belonging to the official publishers. The implemented game mechanics are generic tabletop and role-playing game concepts that are not protectable by copyright.

Community plugins are used with the explicit permission of their respective authors or contain only rewritten generic terms.

All visual assets are either created specifically for this project or distributed under CC0 license (public domain) or compatible free licenses.

## Features

- Full character management (stats, HP, inventory)
- Dice rolling system (d6, d10, d100, custom dice)
- Procedural dungeon generation
- Combat resolution
- Quest and objective tracking
- Multi-game support via plugins
- Modern and responsive user interface

"""

    create_file("README.md", readme_part1)

    # README.md - Part 2 (append to existing file)
    readme_part2 = """## Installation

### Prerequisites

- Python 3.13 or higher
- Windows 10/11

### Installation from sources

Open a terminal and run the following commands:

    # Clone the repository
    git clone https://github.com/your-username/companion4soloplayer.git
    cd companion4soloplayer

    # Create a virtual environment
    python -m venv .venv
    .venv\\Scripts\\activate

    # Install development dependencies
    nox -s setup-dev

    # Start coding
    # using your favorite code editor

    # Run the application
    c4sp

### Windows Build

    # Install the build dependencies (PyInstaller)
    # Build the executable, the release zip and its SHA256 checksum
    nox -s release

The build script:
- increments the build counter stored in pyproject.toml
  ([tool.companion4soloplayer] build = N),
- stamps it into src/companion4soloplayer/build_info.py,
- runs PyInstaller on companion4soloplayer.spec,
- packages dist/companion4soloplayer/ (a minimal companion4soloplayer.exe
  plus its _internal/ runtime folder) into a release archive
  (zip + SHA256 checksum) in dist/.

## Usage

1. Launch the application
2. Select a game plugin from the menu
3. Create your characters
4. Generate a dungeon or load a quest
5. Play!

"""

    with open("README.md", "a", encoding="utf-8") as f:
        f.write(readme_part2)

    # README.md - Part 3 (append to existing file)
    readme_part3 = """## Development

See the [CONTEXT.md](CONTEXT.md) file for the complete development guide.

### Project structure

    companion4soloplayer/
    ├── src/companion4soloplayer/   # Python sources (importable package)
    │   ├── main.py
    │   ├── core/       # Generic engine
    │   ├── plugins/    # Game plugins
    │   └── ui/         # User interface
    ├── assets/         # Assets (CC0)
    ├── tests/          # Unit tests
    └── docs/           # Documentation

### Tests

    # Run tests
    pytest

    # With coverage (terminal + HTML report generated in htmlcov/)
    pytest --cov=companion4soloplayer.core --cov=companion4soloplayer.plugins

    # Open the HTML coverage report
    start htmlcov/index.html

## Contributing

Contributions are welcome! Please see the development guide in [CONTEXT.md](CONTEXT.md).

## License

This project is licensed under the MIT license. See the [LICENSE](LICENSE) file for more details.

## Resources

- [Legal documentation](docs/legal_guidelines.md)
- [Plugin development guide](docs/plugin_development.md)
- [User guide](docs/user_guide.md)

---

**Last updated**: 2026-09-11
"""

    with open("README.md", "a", encoding="utf-8") as f:
        f.write(readme_part3)


# ---------------------------------------------------------------------------
def _create_project_license() -> None:
    # LICENSE
    license_content = """MIT License

Copyright (c) 2026 ultra-sonic-28

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

    create_file("LICENSE", license_content)


# ---------------------------------------------------------------------------
def _create_project_gitignore() -> None:
    # .gitignore
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
.venv/
venv/
ENV/
env/

# IDE
.vscode/
*.code-workspace
.idea/
*.swp
*.swo
*~

# Type checking / linting caches
.mypy_cache/
.ruff_cache/
.pytype/

# Testing
.pytest_cache/
.coverage
.coverage.*
htmlcov/
*.cover

# Distribution
*.spec

# OS
.DS_Store
Thumbs.db
Desktop.ini

# Logs
*.log

# Database
*.db
*.sqlite

# Temporary files
*.tmp
*.temp

# Local configuration
.env
.env.*
companion4soloplayer.log

# Others
.bintools/
.tmp/
site/
stats.txt
"""

    create_file(".gitignore", gitignore_content)


# ---------------------------------------------------------------------------
def _create_project_pyproject() -> None:
    # pyproject.toml
    # Centralized dependency dictionary (key = identifier, value = dependency with version)
    deps = {
        "setuptools": "setuptools>=84.0.0",
        "pyside6": "PySide6>=6.11.2",
        "types_pyside6": "types-PySide6>=6.10.3.0",
        "pydantic": "pydantic>=2.13.5",
        "pillow": "pillow>=12.3.0",
        "pyyaml": "PyYAML>=6.0.3",
        "pytest": "pytest>=9.1.1",
        "pytest_cov": "pytest-cov>=7.1.0",
        "pytest_qt": "pytest-qt>=4.5.0",
        "black": "black>=26.5.1",
        "ruff": "ruff>=0.16.10",
        "mypy": "mypy>=2.4.0",
        "types_pyyaml": "types-PyYAML>=6.0.12",
        "pyinstaller": "pyinstaller>=6.22.3",
        "nuitka": "nuitka>=4.2.2",
        "mkdocs": "mkdocs>=1.6.1",
        "mkdocs_material": "mkdocs-material>=9.7.7",
        "mkdocstrings_python": "mkdocstrings-python>=2.0.8",
        "mkdocs_mermaid2_plugin": "mkdocs-mermaid2-plugin>=1.2.3",
        "pymdown_extensions": "pymdown-extensions>=12.1",
    }

    pyproject_content = Template("""# Definition of the build, metadata, and dependency management for the Companion4SoloPlayer application.
[build-system]
requires = ["$setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "companion4soloplayer"
version = "0.1.0"
description = "Open-source companion application for dungeon crawler style board games and other role-playing games"
readme = "README.md"
license = {text = "MIT"}
authors = [
    {name = "ultra-sonic-28", email = "your.email@example.com"}
]
maintainers = [
    {name = "ultra-sonic-28", email = "your.email@example.com"}
]
keywords = [
    "board-game",
    "dungeon-crawler",
    "companion-app",
    "tabletop",
    "rpg",
    "role-playing",
    "solo-rpg"
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: Microsoft :: Windows :: Windows 10",
    "Operating System :: Microsoft :: Windows :: Windows 11",
    "Programming Language :: Python :: 3.13",
    "Topic :: Games/Entertainment :: Board Games",
    "Topic :: Games/Entertainment :: Role-Playing",
]
requires-python = ">=3.13"
dependencies = [
    "$pyside6",
    "$types_pyside6",
    "$pydantic",
    "$pillow",
    "$pyyaml",
]

[project.optional-dependencies]
# Development dependencies (for contributors)
dev = [
    "$pytest",
    "$pytest_cov",
    "$pytest_qt",
    "$black",
    "$ruff",
    "$mypy",
    "$types_pyyaml",
]

# Lint dependencies
lint = [
    "$black",
    "$ruff",
    "$mypy",
    "$types_pyyaml",
]

# Test dependencies
test = [
    "$pytest",
    "$pytest_cov",
    "$pytest_qt",
]

# Release build dependencies
build = [
    "$pyinstaller",
    "$nuitka",
]

# Documentation build dependencies
docs = [
    "$mkdocs",
    "$mkdocs_material",
    "$mkdocstrings_python",
    "$mkdocs_mermaid2_plugin",
    "$pymdown_extensions",
    "$black",
]

[project.urls]
Homepage = "https://github.com/ultra-sonic-28/companion4soloplayer"
Documentation = "https://github.com/ultra-sonic-28/companion4soloplayer/wiki"
Repository = "https://github.com/ultra-sonic-28/companion4soloplayer"
Issues = "https://github.com/ultra-sonic-28/companion4soloplayer/issues"

[project.scripts]
c4sp = "companion4soloplayer.main:main"

[tool.setuptools.packages.find]
where = ["src"]
include = ["companion4soloplayer*"]

[tool.setuptools.package-data]
"companion4soloplayer.plugins" = ["**/*.json", "**/*.yaml", "**/*.yml", "**/*.md"]

[tool.black]
line-length = 100
target-version = ["py313"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "PT", "RET", "SIM"]
ignore = ["S101", "S311", "E501", "RET504"]

[tool.mypy]
python_version = "3.13"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
mypy_path = "src"
files = ["src/companion4soloplayer", "tests"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --cov=companion4soloplayer.core --cov=companion4soloplayer.plugins --cov-report=term-missing --cov-report=html"

# Numeric counter incremented by nox release session on every
# generated executable; displayed in the CLI banner after the
# version (e.g. "companion4soloplayer v0.1.0 build 12").
#
# Kept in a [tool.*] table on purpose: PEP 621 reserves the keys of
# [project], and setuptools rejects any custom entry found there.
[tool.companion4soloplayer]
build = 1
""").substitute(deps)

    create_file("pyproject.toml", pyproject_content)


# ---------------------------------------------------------------------------
def _create_project_build_info() -> None:
    # companion4soloplayer/build_info.py
    # Rewritten by the nox 'release' session on every executable build.
    # Created from the start so UI code can import it safely; the values
    # are placeholders until the first release is generated.
    build_info_initial = '''"""
Runtime build information for Companion4SoloPlayer.

Rewritten on every 'release' generation by the nox session; source-only
runs therefore always see the last generated values.
"""

BUILD_NUMBER = 0
BUILD_DATETIME = "unknown"
'''

    create_file("companion4soloplayer/build_info.py", build_info_initial)


# ---------------------------------------------------------------------------
def _create_project_package_init() -> None:
    # companion4soloplayer/__init__.py
    # Single source of truth for the version: the package metadata defined
    # in pyproject.toml. Expose it as __version__ via importlib.metadata.
    package_init = '''"""
Companion4SoloPlayer - companion application for tabletop board games.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("companion4soloplayer")
except PackageNotFoundError:
    # Package not installed (running from sources without pip install -e .)
    __version__ = "0.0.0+unknown"
'''

    create_file("companion4soloplayer/__init__.py", package_init)


# ---------------------------------------------------------------------------
def _create_project_main() -> None:
    # main.py
    main_content = '''#!/usr/bin/env python3
"""
Main entry point for Companion4SoloPlayer.
"""

import sys

from PySide6.QtWidgets import QApplication

from companion4soloplayer import __version__
from companion4soloplayer.ui.main_window import MainWindow


def main() -> None:
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("Companion4SoloPlayer")
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
'''

    create_file("main.py", main_content)


# ---------------------------------------------------------------------------
# Script files
# ---------------------------------------------------------------------------
def create_script_files() -> None:
    """Create the script files."""
    _print_step(" Creating script files ")

    _create_script_make_icon()
    _create_script_resize_logo()
    _create_script_compile_plugins()
    _print_success(" Script files created! ")

    _create_script_pyinstaller_recipe()
    _print_success(" Build environment configuration files created! ")


# ---------------------------------------------------------------------------
def _create_script_make_icon() -> None:
    # Create make_icon.py
    make_icon_content = '''# Companion4SoloPlayer (C4SP) - Icon Creator script
from pathlib import Path

from PIL import Image

SRC = Path("./assets/icons/logo-512x512.png")
DST = Path("./assets/icons/icon.ico")

sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]

def generate_icon() -> None:
    img = Image.open(SRC)
    img.save(DST, format='ICO', sizes=sizes)
    print(f"[OK] {DST} generated.")

def main() -> None:
    # Si icon.ico n'existe pas → générer
    if not DST.exists():
        print(f"[INFO] {DST} does not exist → generating.")
        generate_icon()
        return

    # Vérifier les dates de modification
    src_mtime = SRC.stat().st_mtime
    dst_mtime = DST.stat().st_mtime

    if src_mtime > dst_mtime:
        print(f"[INFO] Source ICO is newer → regenerating {DST}.")
        generate_icon()
    else:
        print(f"[SKIP] {DST} is up to date → nothing to do.")

if __name__ == "__main__":
    main()

'''
    create_file("make_icon.py", make_icon_content)


# ---------------------------------------------------------------------------
def _create_script_resize_logo() -> None:
    # Create resize_logo.py
    resize_logo_content = '''# Companion4SoloPlayer (C4SP) - Logo Resizer script
# scripts/resize_logo.py
from pathlib import Path
from PIL import Image

SRC = Path("./assets/icons/logo-512x512.png")
DST = Path("./docs/assets/logo-64x64.png")
size = (64, 64)

def generate_logo() -> None:
    img = Image.open(SRC)
    img = img.resize(size)
    img.save(DST, format='PNG')
    print(f"[OK] {DST} generated.")

def main():

    if not DST.exists():
        print(f"[INFO] {DST} does not exist → generating.")
        generate_logo()
        return

    # Vérifier les dates de modification
    src_mtime = SRC.stat().st_mtime
    dst_mtime = DST.stat().st_mtime

    if src_mtime > dst_mtime:
        print(f"[INFO] Source PNG is newer → regenerating {DST}.")
        generate_logo()
    else:
        print(f"[SKIP] {DST} is up to date → nothing to do.")

if __name__ == "__main__":
    main()

'''

    create_file("resize_logo.py", resize_logo_content)


# ---------------------------------------------------------------------------
def _create_script_compile_plugins() -> None:
    # scripts/compile_plugins.py - plugin compiler (Nuitka/Zig -> .pyd)
    compile_plugins_content = '''"""Compile the game plugins into extension modules (``*.pyd``).

Each plugin package under ``src/companion4soloplayer/plugins`` is compiled
with Nuitka (package mode) into a standalone extension library named after
the plugin (without the ``_plugin`` package suffix). The whole source
package -- one module per rule class under ``rules/``, the facade modules
(``plugin.py``, ``manifest.py``, ``data.py``) and the package ``__init__``
-- is fused into that single extension library:

    demo_plugin           ->  build/plugins/demo.pyd

Toolchain: Python -> Nuitka (``--mode=package --zig``) -> ``zig cc`` (clang).
Nuitka locates the Zig binary on the PATH (see SconsInterface.py: with
``--zig``, a ``zig`` executable found in the PATH is preferred over the
pip ``ziglang`` download), so the ``.bintools`` Zig directory is prepended
to the child process PATH.

The YAML data files of each plugin (``datas/plugin.yaml``,
``datas/classes.yaml``, ``datas/rules.yaml``, ...) plus the Markdown files
are copied into ``build/plugins/<name>/`` next to the compiled library,
preserving their relative layout, so the released application layout is::

    internal/plugins/
        demo.pyd
        demo/
            datas/
                plugin.yaml, classes.yaml, ...
            README.md
            ...

Usage:  python scripts/compile_plugins.py `[--output-dir build/plugins]` `[--force]`

Plugins are recompiled only when needed: if any plugin source file
(``*.py`` anywhere in the package or data file) is newer than the compiled
``.pyd``, the plugin is rebuilt; otherwise the existing library is kept.
Pass ``--force`` to rebuild every plugin regardless of timestamps.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_SRC = ROOT / "src" / "companion4soloplayer" / "plugins"
PLUGIN_PACKAGE_SUFFIX = "_plugin"

# Zig compiler shipped with the project (see .bintools/, git-ignored).
ZIG_DIR = ROOT / ".bintools" / "zig-x86_64-windows-0.16.0"
ZIG_EXE = ZIG_DIR / "zig.exe"

# Data files copied next to each compiled library (.json kept for
# plugins not yet migrated to YAML). The layout inside the plugin
# package is preserved (datas/*.yaml, README.md at the package root).
DATA_EXTENSIONS = {".yaml", ".yml", ".md"}

# Plugin manifests: YAML is canonical (in the datas/ data directory),
# the root and JSON locations are legacy fallbacks.
MANIFEST_NAMES = ("datas/plugin.yaml", "plugin.yaml")

# Code files mirrored into the Nuitka work directory.
CODE_EXTENSIONS = {".py"}


def _has_manifest(directory: Path) -> bool:
    """Tell whether a directory contains a plugin manifest.

    Args:
        directory: Plugin package directory.

    Returns:
        True if ``plugin.yaml`` (or legacy ``plugin.json``) is present.
    """
    return any((directory / name).is_file() for name in MANIFEST_NAMES)


def discover_plugin_packages() -> list[Path]:
    """Return plugin source package directories (with plugin manifest)."""
    return sorted(item for item in PLUGINS_SRC.iterdir() if item.is_dir() and _has_manifest(item))


def _nuitka_env(work_dir: Path | None = None) -> dict[str, str]:
    """Return the environment for Nuitka child processes.

    The Zig directory from ``.bintools`` is prepended to the PATH so
    Nuitka's ``--zig`` mode picks up the project-pinned compiler instead
    of downloading the ``ziglang`` pip package. ``PYTHONUTF8`` avoids
    cp1252 decoding issues in Nuitka/SCons child processes on Windows.
    """
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    # Keep the scratch build tree (ccache, clcache, ...) inside the work
    # directory instead of the per-user AppData cache: it is wiped with the
    # temporary work directory and avoids cross-run cache drift in CI.
    if work_dir is not None:
        env["NUITKA_CACHE_DIR"] = str(Path(work_dir) / "nuitka-cache")

    if ZIG_EXE.is_file():
        env["PATH"] = f"{ZIG_DIR}{os.pathsep}{env.get('PATH', '')}"
    else:
        print(
            f"WARNING: Zig compiler not found at {ZIG_EXE}; "
            "Nuitka will fall back to its own ziglang download.",
            file=sys.stderr,
        )

    if work_dir is not None:
        # Make the mirrored, suffix-less plugin package importable for the
        # Nuitka module resolution.
        env["PYTHONPATH"] = (
            f"{work_dir}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else str(work_dir)
        )

    return env


def _source_files(package_dir: Path) -> list[Path]:
    """Return every input file of a plugin package (code + data), recursively."""
    return [
        item
        for item in package_dir.rglob("*")
        if item.is_file()
        and (item.suffix.lower() in CODE_EXTENSIONS or item.suffix.lower() in DATA_EXTENSIONS)
    ]


def _needs_recompile(package_dir: Path, library_path: Path) -> tuple[bool, str]:
    """Tell whether a plugin must be recompiled.

    A recompilation is required when the compiled library is missing, or
    when any plugin source file is newer than the library build time.

    Args:
        package_dir: Source package directory of the plugin.
        library_path: Existing compiled library (may not exist yet).

    Returns:
        Tuple ``(needs_recompile, reason)`` where ``reason`` explains the
        decision (for the console output).
    """
    if not library_path.is_file():
        return True, "no compiled library yet"

    library_mtime = library_path.stat().st_mtime
    for source in _source_files(package_dir):
        if source.stat().st_mtime > library_mtime:
            return True, f"{source.name} is newer than {library_path.name}"

    return False, f"{library_path.name} is up to date"


def compile_plugin(package_dir: Path, output_dir: Path, work_dir: Path) -> Path:
    """Compile one plugin package into ``<output_dir>/<name>.pyd``.

    Args:
        package_dir: Source package directory of the plugin.
        output_dir: Directory receiving the compiled library and data files.
        work_dir: Scratch directory for the intermediate build artifacts.

    Returns:
        Path of the generated extension library.
    """
    plugin_name = package_dir.name.removesuffix(PLUGIN_PACKAGE_SUFFIX)

    # Mirror the plugin package under the work directory with the flat,
    # suffix-less module name expected in the released application, then
    # compile that package with Nuitka (package mode). Every Python file
    # of the package is mirrored, preserving the sub-directory layout
    # (``rules/``, ...), so the compiled library keeps all rule classes.
    # The generated extension keeps runtime imports (pydantic, core, ...)
    # external: plugins share the application environment.
    package_work = work_dir / plugin_name
    package_work.mkdir(parents=True)
    for source in package_dir.rglob("*"):
        if source.is_file() and source.suffix.lower() in CODE_EXTENSIONS:
            target = package_work / source.relative_to(package_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    nuitka_output_dir = work_dir / "out"
    nuitka_output_dir.mkdir(parents=True)

    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--mode=package",
        f"--output-dir={nuitka_output_dir}",
        "--zig",
        "--no-progressbar",
        plugin_name,
    ]

    print(f"  Nuitka command: {' '.join(command)}")
    result = subprocess.run(  # noqa: S603 - command list built internally
        command,
        cwd=work_dir,
        env=_nuitka_env(work_dir),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Nuitka failed for plugin {plugin_name} (exit {result.returncode})")

    candidates = sorted(nuitka_output_dir.glob(f"{plugin_name}.*.pyd"))
    if not candidates:
        raise RuntimeError(f"No compiled library found for plugin {plugin_name}")

    target = output_dir / f"{plugin_name}{candidates[0].suffix}"
    shutil.copy2(candidates[0], target)

    # Copy the data files into the sibling <plugin_name>/ directory,
    # preserving their relative layout (datas/*.yaml, README.md, ...).
    _copy_data_files(package_dir, output_dir / plugin_name)

    return target


def _copy_data_files(package_dir: Path, data_dir: Path) -> None:
    """Copy the data files of a package into ``data_dir``.

    The relative layout of the package is preserved, so ``datas/rules.yaml``
    lands in ``<data_dir>/datas/rules.yaml``.

    Args:
        package_dir: Source package directory of the plugin.
        data_dir: Destination directory (``<output>/<plugin_name>``).
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    for data_file in _source_files(package_dir):
        if data_file.suffix.lower() in DATA_EXTENSIONS:
            target = data_dir / data_file.relative_to(package_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(data_file, target)


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "build" / "plugins"),
        help="Directory receiving the compiled plugins (default: build/plugins)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompile every plugin, ignoring timestamps",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    packages = discover_plugin_packages()
    if not packages:
        print("No plugin package found.", file=sys.stderr)
        return 1

    compiled = 0
    skipped = 0

    for package in packages:
        plugin_name = package.name.removesuffix(PLUGIN_PACKAGE_SUFFIX)
        library_path = output_dir / f"{plugin_name}.pyd"

        if not args.force:
            needs_recompile, reason = _needs_recompile(package, library_path)
            if not needs_recompile:
                print(f"Skipping plugin: {package.name} ({reason})")
                skipped += 1

                # Data files are cheap to refresh: keep them in sync even
                # when the compiled library is up to date.
                _copy_data_files(package, output_dir / plugin_name)
                continue
            print(f"Compiling plugin: {package.name} ({reason})")
        else:
            print(f"Compiling plugin: {package.name} (forced rebuild)")

        with tempfile.TemporaryDirectory(prefix="c4sp-plugins-") as tmp:
            library = compile_plugin(package, output_dir, Path(tmp))
        print(f"  -> {library}")
        compiled += 1

    print(f"Done. {compiled} plugin(s) compiled, {skipped} skipped " f"(output: {output_dir})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

'''
    create_file("compile_plugins.py", compile_plugins_content)


# ---------------------------------------------------------------------------
def _create_script_pyinstaller_recipe() -> None:
    # companion4soloplayer.spec - PyInstaller build recipe
    spec_content = '''
"""
PyInstaller spec for Companion4SoloPlayer.
Built by scripts/create_project.py

    python -m PyInstaller --clean --noconfirm companion4soloplayer.spec

Produces dist/companion4soloplayer/companion4soloplayer.exe (a minimal
executable) plus an _internal/ sub-folder holding every runtime
library, Python module and data file (one-dir mode).
"""

import os
import tomllib
from datetime import date
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

datas = [
    ("assets", "assets"),
]
# Skip empty source directories (fresh projects have no assets yet):
datas = [
    (source, destination)
    for source, destination in datas
    if os.path.isdir(source) and any(os.scandir(source))
]

# ---------------------------------------------------------------------------
# Compiled plugins (.pyd + YAML data), produced by scripts/compile_plugins.py
# (invoked by the nox 'release' session before PyInstaller). They are
# collected as binaries so PyInstaller places them in _internal/plugins/,
# next to the runtime libraries.
# ---------------------------------------------------------------------------
PLUGINS_BUILD_DIR = Path(SPECPATH) / "build" / "plugins"
if not PLUGINS_BUILD_DIR.is_dir():
    raise SystemExit(
        "Compiled plugins not found: run 'nox -s compile-plugins' "
        "(or scripts/compile_plugins.py) before building the executable."
    )

plugin_libraries = sorted(PLUGINS_BUILD_DIR.glob("*.pyd"))
plugin_datas = sorted(
    path
    for path in PLUGINS_BUILD_DIR.rglob("*")
    if path.is_file() and path.suffix != ".pyd"
)

# Plugin data files (plugin.yaml, classes.yaml, ...) keep the layout they
# have under build/plugins/, so the released layout mirrors it:
# _internal/plugins/<plugin_name>/datas/*.yaml
# The destination is the file's parent directory RELATIVE to the plugins
# build dir (not its bare name): using path.parent.name alone would flatten
# <plugin_name>/datas/ into plugins/datas/.
def _plugin_data_destination(path: Path) -> str:
    relative_parent = path.parent.relative_to(PLUGINS_BUILD_DIR)
    if relative_parent == Path("."):
        return "plugins"
    return "plugins/" + relative_parent.as_posix()


datas += [
    (str(path), _plugin_data_destination(path))
    for path in plugin_datas
]
binaries = [(str(path), "plugins") for path in plugin_libraries]

# ---------------------------------------------------------------------------
# Third-party imports of the compiled plugins.
# The .pyd libraries are opaque binaries: PyInstaller cannot follow the
# Python-level imports they perform at runtime (the demo plugin's manifest
# module does `from pydantic import BaseModel`, and pydantic is lazily
# loaded through __getattr__, so even a reachable package root would not
# pull its submodules in). The affected packages are force-collected so
# plugins can be loaded from the Plugins tab of the frozen application.
# A dependency used by a plugin must be listed here AND declared in the
# `dependencies` array of pyproject.toml.
# ---------------------------------------------------------------------------
PLUGIN_DEPENDENCIES = ("pydantic",)

hiddenimports: list[str] = []
for _package in PLUGIN_DEPENDENCIES:
    _package_datas, _package_binaries, _package_submodules = collect_all(_package)
    datas += _package_datas
    binaries += _package_binaries
    hiddenimports += _package_submodules

# ---------------------------------------------------------------------------
# Windows version metadata, sourced from pyproject.toml so the numbers can
# never drift from the package definition. scripts/build_exe.ps1 bumps the
# `build` entry BEFORE invoking PyInstaller, hence the freshly stamped value
# is the one read here.
# ---------------------------------------------------------------------------
# PEP 621 reserves the keys of [project] (setuptools rejects custom
# ones), so the build counter lives in the project's own tool table.
_pyproject = tomllib.loads(
    # PyInstaller exposes SPECPATH (the spec file's directory) instead
    # of __file__ when executing the recipe.
    (Path(SPECPATH) / "pyproject.toml").read_text(
        encoding="utf-8",
    ),
)

VERSION = _pyproject["project"]["version"]
BUILD_NUMBER = int(_pyproject["tool"]["companion4soloplayer"]["build"])

_file_version_tuple = (
    tuple(int(part) for part in VERSION.split(".")) + (BUILD_NUMBER,)
)
while len(_file_version_tuple) < 4:
    _file_version_tuple += (0,)

COPYRIGHT = f"© {date.today().year} ultra-sonic-28"

vs_version = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=_file_version_tuple[:4],
        prodvers=_file_version_tuple[:4],
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        VarFileInfo(
            # 1036 = French (France), 1200 = Unicode.
            [VarStruct("Translation", [1036, 1200])],
        ),
        StringFileInfo(
            [
                StringTable(
                    # Key = language id (040C) + charset id (04B0)
                    # hex-encoded: French (1036) + Unicode (1200).
                    "040C04B0",
                    [
                        StringStruct(
                            "FileDescription",
                            "Companion4SoloPlayer (C4SP) "
                            "Open-source companion application for "
                            "dungeon crawler style board games.",
                        ),
                        StringStruct(
                            "FileVersion",
                            f"{VERSION} build {BUILD_NUMBER}",
                        ),
                        StringStruct("InternalName", "companion4soloplayer"),
                        StringStruct("LegalCopyright", COPYRIGHT),
                        StringStruct(
                            "OriginalFilename",
                            "companion4soloplayer.exe",
                        ),
                        StringStruct("ProductName", "companion4soloplayer"),
                        StringStruct(
                            "ProductVersion",
                            f"{VERSION} build {BUILD_NUMBER}",
                        ),
                    ],
                ),
            ],
        ),
    ],
)

a = Analysis(
    ["src/companion4soloplayer/main.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc_data",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="companion4soloplayer",
    debug=False,
    console=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=vs_version,
    icon="assets/icons/icon.ico",
)

# One-dir bundle: keep the executable minimal and gather every runtime
# binary (Python DLLs, Qt libraries, ...) and data file into the
# _internal/ sub-folder next to it.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="companion4soloplayer",
)
'''
    create_file("companion4soloplayer.spec", spec_content)


# ---------------------------------------------------------------------------
# Nox configuration file
# ---------------------------------------------------------------------------
def create_nox_file() -> None:
    _print_step(" Creating nox file ")

    nox_content = '''
import hashlib
import os
import re
import shutil
import tempfile
import tomllib
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

import nox  # type: ignore
from nox.command import CommandFailed  # type: ignore

# Empty list = no default session
nox.options.sessions = []

# ---------------------------------------------------------------------------
# Get pyproject.toml declared dependencies
# ---------------------------------------------------------------------------
def _get_dev_deps() -> list[str]:
    """Read development dependencies from pyproject.toml."""
    pyproject = Path("pyproject.toml").read_bytes()
    data = tomllib.loads(pyproject.decode())
    return cast(list[str], data["project"]["optional-dependencies"]["dev"])

def _get_test_deps() -> list[str]:
    """Read test dependencies from pyproject.toml."""
    pyproject = Path("pyproject.toml").read_bytes()
    data = tomllib.loads(pyproject.decode())
    return cast(list[str], data["project"]["optional-dependencies"]["test"])

def _get_lint_deps() -> list[str]:
    """Read lint dependencies from pyproject.toml."""
    pyproject = Path("pyproject.toml").read_bytes()
    data = tomllib.loads(pyproject.decode())
    return cast(list[str], data["project"]["optional-dependencies"]["lint"])

def _get_build_deps() -> list[str]:
    """Read build dependencies from pyproject.toml."""
    pyproject = Path("pyproject.toml").read_bytes()
    data = tomllib.loads(pyproject.decode())
    return cast(list[str], data["project"]["optional-dependencies"]["build"])

def _get_docs_deps() -> list[str]:
    """Read documentation dependencies from pyproject.toml."""
    pyproject = Path("pyproject.toml").read_bytes()
    data = tomllib.loads(pyproject.decode())
    return cast(list[str], data["project"]["optional-dependencies"]["docs"])

def check_network_access(session: nox.Session, url: str = "https://pypi.org/", timeout: int = 5) -> bool:
    """
    Checks if the environment has network access and can reach a specific URL.

    Args:
        session: The nox session object.
        url: The URL to test (default is PyPI).
        timeout: Timeout in seconds.

    Returns:
        bool: True if accessible, False otherwise.
    """
    parsed_url = urlparse(url)
    if parsed_url.scheme not in ("http", "https"):
        session.log(f"Invalid URL scheme '{parsed_url.scheme}'. Only 'http' and 'https' are permitted.")
        return False

    session.log(f"Checking network connectivity to {url} ...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Nox-Connectivity-Check'})  # noqa: S310
        # Ruff S310 is explicitly suppressed here because we validated the scheme above.
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310
            session.log(f"Successfully connected to {url} (HTTP {response.status}).")
            session.log("Network access confirmed.")
            return True

    except urllib.error.URLError as e:
        reason = str(e.reason)
        session.log(f"Failed to connect to {url}.")

        if "getaddrinfo failed" in reason or "Name or service not known" in reason or "nodename nor servname provided" in reason:
            session.log(f"DNS resolution failed: {reason}")
            session.log("You might be offline or your DNS is blocked by a firewall.")
        else:
            session.log(f"URLError occurred: {reason}")
            session.log("Please check your internet connection, proxy, or firewall settings.")
        return False

    except TimeoutError:
        session.log(f"Connection to {url} timed out after {timeout} seconds.")
        session.log("You might be behind a strict firewall or experiencing network issues.")
        return False

    except Exception as e:
        session.log(f"An unexpected error occurred during connectivity check: {e}")
        return False

def _generate_docs(session: nox.Session, is_live: bool) -> None:
    """Internal helper to generate documentation (static or live)."""
    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    session.install(*_get_docs_deps())
    session.install(".")

    # Force UTF-8 for every child Python process: the default cp1252
    # console encoding on Windows crashes scripts printing non-ASCII
    # characters (e.g. make_icon.py prints an arrow "→").
    utf8_env = {"PYTHONUTF8": "1"}

    session.run("python", "scripts/resize_logo.py", env=utf8_env)

    root = Path(__file__).parent.resolve()
    pyproject_path = root / "pyproject.toml"

    # Read pyproject.toml
    pyproject_content = pyproject_path.read_text(encoding="utf-8")

    # Extract version from the (already updated) pyproject.toml
    version_match = re.search(r'(?m)^[ ]*version[ ]*=[ ]*"([^"]+)"[ ]*\\r?$', pyproject_content)

    # FIX MYPI: Use else block so mypy knows version_match is not None in the success path
    if version_match is None:
        session.error("Cannot locate the 'version' entry in pyproject.toml.")
    else:
        version = version_match.group(1)

    # Get the build counter in pyproject.toml
    build_match = re.search(r'(?m)^(?P<indent>[ ]*)build[ ]*=[ ]*(?P<number>\\d+)[ ]*\\r?$', pyproject_content)

    number = int(build_match.group("number")) if build_match else 1

    content =  f"""/* Custom JavaScript for Companion4SoloPlayer */
document.addEventListener('DOMContentLoaded', function() {{
    const footer = document.querySelector('footer');
    footer.innerHTML = `
    <div class="md-footer-meta md-typeset">
        <div class="md-footer-meta__inner md-grid">
            <div class="md-copyright">
                Made with
                <a href="https://squidfunk.github.io/mkdocs-material/" target="_blank" rel="noopener">
                    Material for MkDocs
                </a>
                and
                <a href="https://mkdocstrings.github.io/" target="_blank" rel="noopener">
                mkdocstrings
                </a>
            </div>
            <span class="md-copyright c-white">Companion4SoloPlayer <i>v{version} build {number}</i></span>
        </div>
    </div>
`;
}});
"""

    with open("docs/assets/custom.js", "w", encoding="utf-8") as f:
        f.write(content)

    session.log("Custom JavaScript for the documentation footer has been regenerated in docs/assets/custom.js")

    if is_live:
        session.log("Starting MkDocs live server...")
        session.run(
            "mkdocs",
            "serve",
            "--strict",
            env=utf8_env
        )
    else:
        session.log("Building static documentation...")
        session.run(
            "mkdocs",
            "build",
            "--clean",
            "--strict",
            env=utf8_env
        )
        session.log("Static documentation built successfully in the 'site/' directory.")


# ---------------------------------------------------------------------------
# lint session
# Run QoL checks: black, ruff, mypy.
# ---------------------------------------------------------------------------
@nox.session(name="lint")
def lint(session: nox.Session) -> None:
    """ Run QoL checks: black, ruff, mypy. """
    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    # Install the same packages and versions as in pyproject.toml
    session.install(*_get_lint_deps())
    session.install(*_get_test_deps())
    session.install(".")
    #session.run("black", "--check", ".")

    ruff_has_errors = False

    # Attempt the check, and if it fails, apply the fixes.
    try:
        session.run("ruff", "check", ".")
    except CommandFailed:
        ruff_has_errors = True
        session.log("Ruff found errors, attempting automatic correction...")
        session.run("ruff", "check", "--fix", ".")

    # Verify if there are any remaining errors that couldn't be auto-fixed
    if ruff_has_errors:
        ruff_has_errors = False

        try:
            session.run("ruff", "check", ".")
        except CommandFailed:
            ruff_has_errors = True
            session.log("⚠️ Ruff: non-autofixable errors persist.")

    # mypy always runs
    session.run("mypy", "src")

    # Session failure if Ruff still has errors.
    if ruff_has_errors:
        session.error("Ruff check failed")

# ---------------------------------------------------------------------------
# test-unit session
# Run unit tests.
# ---------------------------------------------------------------------------
@nox.session(name="test-unit")
def tests_unit(session: nox.Session) -> None:
    """Run unit tests."""
    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    session.install(*_get_test_deps())
    session.install(".")
    session.run("pytest", "tests/tests_core", "tests/tests_plugins")

# ---------------------------------------------------------------------------
# test-ui session
# Run user interface tests.
# ---------------------------------------------------------------------------
@nox.session(name="test-ui")
def tests_ui(session: nox.Session) -> None:
    """Run user interface tests."""
    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    session.install(*_get_test_deps())
    session.install(".")
    # The UI tests never import the covered modules (core/plugins):
    # disable coverage to avoid "no data collected" warnings.
    session.run("pytest", "tests/tests_ui", "--no-cov")

# ---------------------------------------------------------------------------
# setup-dev session
# Create and / or activate the Python development environment.
# ---------------------------------------------------------------------------
@nox.session(name="setup-dev", venv_backend="none")
def setup_dev(session: nox.Session) -> None:
    """
    Create or activate the Python development environment in .venv.

    Creates the virtual environment if it doesn't exist, then installs
    the project in editable mode with the development extras.
    """

    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    root = Path(__file__).parent.resolve()
    venv_dir = root / ".venv"

    # Verify we're in the project root (pyproject.toml must exist)
    if not (root / "pyproject.toml").exists():
        session.error("This session must be run from the project root (where pyproject.toml is located).")

    # Create venv if it doesn't exist
    if not venv_dir.exists():
        session.log("Creating virtual environment in .venv...")
        session.run("python", "-m", "venv", str(venv_dir), external=True)
    else:
        session.log(f"Virtual environment already exists: {venv_dir}")

    # Determine the python executable in the venv (cross-platform)
    if os.name == "nt":
        python_exe = venv_dir / "Scripts" / "python.exe"
        pip_exe = venv_dir / "Scripts" / "pip.exe"
    else:
        python_exe = venv_dir / "bin" / "python"
        pip_exe = venv_dir / "bin" / "pip"

    # Verify the venv is valid
    if not python_exe.exists():
        session.error(f"Virtual environment is corrupted: {python_exe} not found. Delete .venv and retry.")

    # Install the project in editable mode with dev extras
    session.log("Installing the project in editable mode with dev extras...")
    session.run(python_exe, "-m", "pip", "install", "-e", ".[dev]", external=True)

    session.log("=" * 60)
    session.log("Development environment ready.")
    session.log("=" * 60)
    session.log(f"Python executable: {python_exe}")
    session.log(f"Pip executable: {pip_exe}")
    session.log("To activate the virtual environment, run:")
    if os.name == "nt":
        session.log(r"  PowerShell: .\\.venv\\Scripts\\Activate.ps1")
        session.log(r"  CMD:        .venv\\Scripts\\activate.bat")
    else:
        session.log(r"  source .venv/bin/activate")
    session.log("Virtual environment is automatically activated in terminal windows in Visual Studio Code")

# ---------------------------------------------------------------------------
# compile-plugins session
# Compile every game plugin into a .pyd extension (build/plugins/).
# ---------------------------------------------------------------------------
@nox.session(name="compile-plugins")
def compile_plugins(session: nox.Session) -> None:
    """Compile every game plugin into a .pyd extension (build/plugins/)."""
    if os.name != "nt":
        session.skip("Plugin compilation targets Windows .pyd and should run on Windows.")

    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    session.install("nuitka>=4.2.2")
    session.run("python", "scripts/compile_plugins.py", env={"PYTHONUTF8": "1"})

# ---------------------------------------------------------------------------
# release session
# Build the standalone Windows executable.
# ---------------------------------------------------------------------------
@nox.session(name="release")
def release(session: nox.Session) -> None:
    """
    Build the standalone Windows executable, increment the build counter,
    stamp the build info, and package the release archive (zip + SHA256).
    """
    if os.name != "nt":
        session.skip("This session is designed to build a Windows executable and should run on Windows.")

    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    # Force UTF-8 for every child Python process: the default cp1252
    # console encoding on Windows crashes scripts printing non-ASCII
    # characters (e.g. make_icon.py prints an arrow "→").
    utf8_env = {"PYTHONUTF8": "1"}

    session.install(*_get_build_deps())
    session.install(".")
    session.run("python", "scripts/make_icon.py", env=utf8_env)

    # Compile the plugins into .pyd extensions before PyInstaller collects
    # them (the spec file raises if build/plugins/ is missing).
    session.install("nuitka>=4.2.2")
    session.run("python", "scripts/compile_plugins.py", env=utf8_env)

    root = Path(__file__).parent.resolve()
    pyproject_path = root / "pyproject.toml"
    build_info_path = root / "src" / "companion4soloplayer" / "build_info.py"
    dist_dir = root / "dist"

    # Install build dependencies
    session.install(*_get_build_deps())
    session.install(".")

    # Read pyproject.toml
    content = pyproject_path.read_text(encoding="utf-8")
    newline = "\\r\\n" if "\\r\\n" in content else "\\n"

    # Increment the build counter in pyproject.toml
    build_match = re.search(r'(?m)^(?P<indent>[ ]*)build[ ]*=[ ]*(?P<number>\\d+)[ ]*\\r?$', content)

    if build_match:
        number = int(build_match.group("number")) + 1
        indent = build_match.group("indent")
        new_line = f"{indent}build = {number}"
        content = content[:build_match.start()] + new_line + content[build_match.end():]
    else:
        # First generation ever: append the dedicated table at the end of the file
        number = 1
        section = f"""# Numeric counter incremented by nox session 'build-exe' on every
# generated executable; displayed in the CLI banner after the
# version (e.g., "companion4soloplayer v0.1.0 build 12").
#
# Kept in a [tool.*] table on purpose: PEP 621 reserves the keys of
# [project], and setuptools rejects any custom entry found there.
[tool.companion4soloplayer]
build = {number}"""
        content = content.rstrip() + newline + newline + section + newline

    # Write back UTF-8 without BOM
    pyproject_path.write_text(content, encoding="utf-8")

    # Stamp the runtime module read by the CLI banner
    build_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stamp = f\'\'\'"""Generated by nox session 'release' - do not edit by hand.

This module is rewritten on every executable generation. Source-only
runs therefore always see the last generated value.
"""

BUILD_NUMBER = {number}
BUILD_DATETIME = "{build_datetime}"
\'\'\'
    build_info_path.write_text(stamp, encoding="utf-8")
    session.log(f"Build number: {number}")
    session.log(f"Build datetime: {build_datetime}")

    # Generate the executable
    session.run(
        "python",
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "companion4soloplayer.spec",
        env=utf8_env,
    )

    # Extract version from the (already updated) pyproject.toml
    version_match = re.search(r'(?m)^[ ]*version[ ]*=[ ]*"([^"]+)"[ ]*\\r?$', content)

    # FIX MYPI: Use else block so mypy knows version_match is not None in the success path
    if version_match is None:
        session.error("Cannot locate the 'version' entry in pyproject.toml.")
    else:
        version = version_match.group(1)

    release_base_name = f"companion4soloplayer-win-x64-v{version}.{number}"
    zip_path = dist_dir / f"{release_base_name}.zip"
    sha_path = dist_dir / f"{release_base_name}.zip.sha256"

    # Stage the archive contents
    staging_dir = Path(tempfile.gettempdir()) / f"companion4soloplayer-release-{release_base_name}"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    # The one-dir build lives in dist/companion4soloplayer/: a minimal
    # executable next to an _internal/ folder with all runtime
    # libraries (Python DLLs, Qt, ...) and data files.
    app_dir = dist_dir / "companion4soloplayer"

    shutil.copy2(app_dir / "companion4soloplayer.exe", staging_dir / "companion4soloplayer.exe")
    shutil.copytree(app_dir / "_internal", staging_dir / "_internal")
    # TODO: Add future assets here (e.g., sample tilesets, docs)

    # Create fresh archive and SHA256
    if zip_path.exists():
        zip_path.unlink()
    if sha_path.exists():
        sha_path.unlink()

    # Create ZIP archive (recursive walk so the _internal/ folder is
    # fully included)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(staging_dir.rglob("*")):
            if file_path.is_dir():
                continue
            zf.write(file_path, arcname=file_path.relative_to(staging_dir))

    # Calculate SHA256 in "<HASH>  <FILENAME>" format (uppercase, standard Git)
    sha256_hash = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    hash_hex = sha256_hash.hexdigest().upper()
    sha_path.write_text(f"{hash_hex}  {release_base_name}.zip\\n", encoding="ascii")

    # Cleanup staging directory
    shutil.rmtree(staging_dir)

    # Output summary
    session.log("")
    session.log(f"Built: {app_dir / 'companion4soloplayer.exe'} (build {number})")
    session.log(f"Release: {zip_path.name}")
    session.log(f"SHA256:  {hash_hex}  ({sha_path.name})")

# ---------------------------------------------------------------------------
# check-venv session
# Check if a virtual environment is active.
# ---------------------------------------------------------------------------
@nox.session(name="check-venv", venv_backend="none")
def check_venv(session: nox.Session) -> None:
    """Check if a virtual environment is active."""
    import sys

    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.log(f"✓ Virtual environment is active: {venv}")
        session.log(f"  Python: {sys.executable}")
    else:
        session.log("✗ No virtual environment is active")
        session.log(r"  Run: .\\.venv\\Scripts\\Activate.ps1")

# ---------------------------------------------------------------------------
# docs session
# Create technical documentation, static build
# ---------------------------------------------------------------------------
@nox.session(name="docs")
def docs(session: nox.Session) -> None:
    """Create technical documentation, static build."""
    _generate_docs(session, is_live=False)

# ---------------------------------------------------------------------------
# docs-live session
# Create technical documentation, live reloading server
# ---------------------------------------------------------------------------
@nox.session(name="docs-live")
def docs_live(session: nox.Session) -> None:
    """Create technical documentation, live reloading server."""
    _generate_docs(session, is_live=True)

# ---------------------------------------------------------------------------
# stats session
# Compute code statistics
# ---------------------------------------------------------------------------
@nox.session(name="stats", venv_backend="none")
def stats(session: nox.Session) -> None:
    """Compute code statistics (lines of code, etc.)"""
    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    cloc_executable =  f"{os.getcwd()}/.bintools/cloc/cloc-2.06.exe"
    report_file = './stats.txt'

    # Force UTF-8 for every child Python process: the default cp1252
    # console encoding on Windows crashes scripts printing non-ASCII
    # characters (e.g. make_icon.py prints an arrow "→").
    utf8_env = {"PYTHONUTF8": "1"}

    retcode = session.run(
        cloc_executable,
        '--skip-uniqueness',
        '--quiet',
        '--exclude-ext=.pyc,".py,cover"',
        '--not-match-d=(.pytest_cache)',
        '--skip-archive=(zip|tar(.(gz|Z|bz2|xz|7z))?)',
        f'--report-file={report_file}',
        '--found=./.tmp/found.txt',
        '--ignored=./.tmp/ignored.txt',
        '--fmt=2',
        './src/',
        './tests/',
        './scripts/',
        env=utf8_env,
    )

    if retcode:
        # Display the content of the report file if cloc succeeded
        with open(report_file, encoding='utf-8') as file:
            content = file.read()
            print(content)
'''
    create_file("noxfile.py", nox_content)

    _print_success(" Nox file created! ")


# ---------------------------------------------------------------------------
# Visual Studio Code editor settings
# ---------------------------------------------------------------------------
def create_editor_files() -> None:
    """Create the Visual Studio Code editor and workspace files.

    Generates:
    - .vscode/settings.json: editor and workspace preferences
    - companion4soloplayer.code-workspace: workspace file (project root)
    """
    _print_step(" Creating editor settings ")

    _create_editor_settings()
    _create_editor_workspace()

    _print_success(" Editor settings files created! ")

# ---------------------------------------------------------------------------
def _create_editor_settings() -> None:
    # .vscode/settings.json - editor and workspace preferences
    # (JSONC: trailing commas are tolerated by Visual Studio Code)
    settings_content = """{
  "workbench.colorTheme": "Default Dark Modern",
  "window.zoomLevel": 1,
  "editor.fontSize": 12,
  "python.autoComplete.extraPaths": [
      "./src",
  ],
  "files.exclude": {
    "**/.wheels": true,
    "*.code-workspace": true,
    "**/__pycache__": true,
    "**/.pytest_cache": true,
    "**/.venv/": true,
    "**/*.egg-info/": true,
  },
  "ruff.importStrategy": "useBundled",
  "mypy-type-checker.importStrategy": "useBundled",
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/Scripts/python.exe",
  "python.terminal.activateEnvironment": true
}"""

    create_file(".vscode/settings.json", settings_content)


# ---------------------------------------------------------------------------
def _create_editor_workspace() -> None:
    # companion4soloplayer.code-workspace - VS Code workspace file
    # (indentation: tab characters, as written by Visual Studio Code)
    workspace_content = """{
\t"folders": [
\t\t{
\t\t\t"path": "."
\t\t}
\t],
\t"settings": {}
}"""

    create_file("companion4soloplayer.code-workspace", workspace_content)


# ---------------------------------------------------------------------------
# CONTEXT.md file (development guide)
# ---------------------------------------------------------------------------
def create_context_file() -> None:
    """Create the CONTEXT.md file (development guide)."""
    _print_step(" Creating CONTEXT.md file ")

    # CONTEXT.md
    context = """# Companion4SoloPlayer (C4SP) - Context File and Development Guide

## Overview

**Companion4SoloPlayer (C4SP)** is a free, non-profit, open-source companion application designed to make it easy to manage dungeon crawler style board game sessions. The application is modular and can support several games through a plugin system.

**GitHub repository**: [to be created]
**License**: MIT
**Language**: Python 3.13+
**Target platform**: Windows (standalone binary)
**Status**: Project in development

---

## LEGAL CONSTRAINTS (CRITICAL)

### 1. Fundamental principles

#### 1.1 What is FORBIDDEN

- ❌ Using registered trademark names in source code, file names, or variable names
  - Forbidden examples: "HeroQuest", "HQ", "Zargon", "Morcar", "Fimir", "Chaos Warrior"
  - Forbidden examples: "4 Against Darkness" (as a file/variable name)
  - Forbidden examples: "2D6 Dungeon" (as a file/variable name)

- ❌ Reproducing official quest, item, or rule texts
  - Never copy-paste text from official booklets
  - Always rewrite in your own words

- ❌ Using official artwork
  - No scans, no reproductions, no adaptations of protected images

- ❌ Using official logos
  - No Hasbro, Games Workshop, Ganesha Games, DR Games, etc. logos

- ❌ Suggesting official affiliation or endorsement
  - Never write "Official application for HeroQuest"
  - Always specify "not affiliated, not endorsed"

#### 1.2 What is ALLOWED

- ✅ Using generic fantasy terms
  - Classes: Barbarian, Wizard, Dwarf, Elf, Cleric, Thief
  - Monsters: Skeleton, Goblin, Orc, Zombie, Dragon
  - Places: Dungeon, Fortress, Tower, Cave

- ✅ Implementing game mechanics
  - Rules as concepts are not protectable
  - Rewrite the rules in your own words

- ✅ Mentioning compatibility in descriptions
  - Use *nominative fair use*: "compatible with the mechanics of [GameName]"
  - Only in READMEs, descriptions, and communications

- ✅ Creating your own descriptions
  - Item, room, and monster descriptions (original)
  - Procedural encounter tables

- ✅ Integrating community content with permission
  - Fan-made quests with the author's written consent
  - Clearly credit the authors

#### 1.3 Plugin structure

Each plugin must contain a `README.md` file with a clear legal disclaimer.

#### 1.4 Global disclaimer (to include in the main README)

The complete disclaimer is available in the main README.md file.

---

## TECHNICAL ARCHITECTURE

### 1. Project structure

    companion4soloplayer/
    ├── src/companion4soloplayer/                # Python sources (importable package)
    │   ├── main.py
    │   ├── core/                                # Generic engine
    │   │   ├── __init__.py
    │   │   ├── character_tracker.py             # HP, stats, inventory management
    │   │   ├── dice_roller.py                   # Dice rolls (d6, d10, d100, custom)
    │   │   ├── procedural_generator.py          # Procedural dungeon generation
    │   │   ├── combat_resolver.py               # Combat resolution
    │   │   ├── quest_manager.py                 # Objective and step tracking
    │   │   ├── rule_engine.py                   # Hybrid YAML/Python rule engine
    │   │   ├── yaml_loader.py                   # Safe YAML loader (custom tags)
    │   │   ├── rules/                           # Shared rule elements
    │   │   │   ├── __init__.py
    │   │   │   └── oracle_rule.py               # OracleRule (shared by all plugins)
    │   │   └── plugin_loader.py                 # Dynamic plugin loading
    │   │
    │   ├── plugins/                             # Game-specific modules
    │   │   │                                    # Every plugin shares the same layout:
    │   │   │                                    # data.py, manifest.py, plugin.py,
    │   │   │                                    # rules/ (1 file per class), datas/
    │   │   └── demo_plugin/                     # Demo plugin
    │   │       ├── __init__.py                  # Facade: Plugin + rule re-exports
    │   │       ├── data.py                      # datas/ directory + YAML access
    │   │       ├── manifest.py                  # PluginMetadata schema
    │   │       ├── plugin.py                    # Plugin facade (GamePlugin API)
    │   │       ├── rules/                       # Plugin specific rules
    │   │       │   ├── __init__.py
    │   │       │   ├── character_creation_rule.py
    │   │       │   ├── combat_rule.py
    │   │       │   ├── loot_rule.py
    │   │       │   └── magic_rule.py
    │   │       ├── datas/                       # Plugin specific datas
    │   │       │   ├── plugin.yaml
    │   │       │   ├── classes.yaml
    │   │       │   ├── monsters.yaml
    │   │       │   ├── items.yaml
    │   │       │   └── rules.yaml
    │   │       └── README.md
    │   │
    │   └── ui/                                  # User interface
    │       ├── __init__.py
    │       ├── main_window.py                   # Main window
    │       ├── character_panel.py               # Character management panel
    │       ├── quest_panel.py                   # Quest management panel
    │       ├── grid_view.py                     # Dungeon grid view
    │       └── dialogs/                         # Dialog windows
    │           ├── quest_wizard.py              # Quest creation wizard
    │           └── settings_dialog.py           # Settings
    │
    ├── assets/                                  # Shared assets (CC0 only)
    │   ├── icons/                               # Icons (CC0)
    │   ├── fonts/                               # Fonts (free)
    │   └── sounds/                              # Sounds (CC0)
    │
    ├── data/                                    # User data
    │   ├── saves/                               # Game saves
    │   ├── custom_quests/                       # Custom quests
    │   └── config/                              # User configuration
    │
    ├── tests/                                   # Tests
    │   ├── tests_core/                          # Core unit tests
    │   ├── tests_plugins/                       # Plugins tests
    │   └── tests_ui/                            # Core UI tests
    │
    ├── docs/                                    # Documentation
    │   ├── user_guide.md                        # User guide
    │   ├── plugin_development.md                # Plugin development guide
    │   └── legal_guidelines.md                  # Legal guidelines
    │
    ├── scripts/                                 # Project scripts
    │   ├── create_project.py                    # This project generator
    │   ├── make_icon.py                         # Icon Creator script
    │   ├── resize_logo.py                       # Logo Resizer script
    │   └── compile_plugins.py                   # Compile the game plugins into extension modules
    │
    ├── companion4soloplayer.spec                # PyInstaller build recipe
    ├── build/, dist/                            # PyInstaller output (generated)
    │
    ├── .vscode/                                 # Visual Studio Code workspace
    │   └── settings.json                        # Editor settings
    ├── companion4soloplayer.code-workspace      # VS Code workspace file
    │
    ├── pyproject.toml                           # Project configuration
    ├── README.md                                # Main README with disclaimer
    ├── CONTEXT.md                               # Complete development guide
    ├── LICENSE                                  # MIT license
    └── .gitignore                               # Git ignore

### 2. Tech stack

#### 2.1 Language and version
- **Python**: 3.13+ (latest stable version)
- **Type hints**: Mandatory for all public functions
- **Docstrings**: Google format for all functions and classes

#### 2.2 User interface
- **Framework**: PyQt6 or PySide6 (either one, but consistent throughout the project)
- **Style**: QSS (Qt Style Sheets) for theming
- **Responsive**: Support for high-resolution screens (4K)

#### 2.3 Data management
- **Format**: YAML (with comments) for plugin/rule data, loaded through a
  hardened `yaml.SafeLoader` subclass with custom tags (`!pyclass`, `!dice`);
  JSON for saves and user configuration
- **Validation**: Pydantic for plugin manifest validation
- **Serialization**: Standard JSON for saves (no pickle for security reasons)

#### 2.4 Build and distribution
- **Packaging**: PyInstaller to create the standalone Windows binary
- **Distribution**: Portable ZIP + optional NSIS installer
- **Dependencies**: All dependencies included in the binary

#### 2.5 Testing
- **Framework**: pytest
- **Coverage**: Minimum target 80%
- **CI/CD**: GitHub Actions for automated tests

#### 2.6 Documentation
- **Format**: Markdown
- **Generation**: MkDocs for technical documentation
- **API docs**: Sphinx or pdoc for automatic documentation

---

## DEVELOPMENT CONVENTIONS

### 1. Code style

#### 1.1 Formatting
- **Black**: Automatic formatting (100-character max lines)
- **Ruff**: Linting and style checking
- **isort**: Automatic import sorting

#### 1.2 Typing
- **Type hints**: Mandatory for all public functions
- **mypy**: Static type checking
- **Pydantic**: JSON data validation

#### 1.3 Naming
- **Variables/functions**: snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **Modules**: snake_case
- **Plugins**: gamename_plugin (e.g. demo_plugin)

### 2. Plugin management

#### 2.1 Plugin interface

Each plugin must implement the `GamePlugin` interface defined in `core/plugin_loader.py`.

#### 2.2 plugin.yaml file

Each plugin must contain a `datas/plugin.yaml` file with the following
metadata:
- `name`: Generic plugin name (no registered trademark)
- `version`: Plugin version (semver format)
- `description`: Short description
- `author`: Author name
- `license`: License (MIT recommended)
- `compatible_games`: List of compatible games (descriptive information)
- `disclaimer`: Legal disclaimer
- `dependencies`: Dependencies on the core

### 3. Data management

#### 3.1 Important rules
- **No pickle**: Plugin data is read through the safe YAML loader, saves
  and configuration through JSON, for security reasons
- **UTF-8 encoding**: Mandatory for all data files
- **Strict validation**: Any non-compliant data must raise an explicit exception
- **Informative logs**: Log the file path and error type on failure

### 4. Testing

#### 4.1 Test structure

Tests must be organized as follows:
- `tests/tests_core/`: Tests for the generic engine
- `tests/tests_plugins/`: Tests for the plugins
- `tests/tests_ui/`: Tests for the user interface

#### 4.2 Requirements
- Each public function must have at least one unit test
- Tests must be fast and independent
- Use fixtures for test data
- Minimum code coverage: 80%

### 5. Documentation

#### 5.1 Docstrings
Google format is mandatory for all public functions, with:
- Short description
- Detailed description (if necessary)
- `Args:` section for parameters
- `Returns:` section for the return value
- `Raises:` section for exceptions
- `Example:` section for a usage example

#### 5.2 README.md
The main README must contain:
1. Project description
2. Legal disclaimer
3. Features
4. Installation
5. Usage
6. Development
7. License

---

## DEVELOPMENT WORKFLOW

### 1. Development environment

    # Clone the repository
    git clone https://github.com/ultra-sonic-28/companion4soloplayer.git
    cd companion4soloplayer

    # Create a virtual environment and install development dependencies
    nox -s setup-dev

    # Check the installation using nox
    nox -s tests-unit
    nox -s tests-ui
    nox -s lint

### 2. Development cycle

    # 1. Create a feature branch
    git checkout -b feature/feature-name

    # 2. Develop and test
    # ... code ...
    nox -s tests-unit
    nox -s tests-ui
    nox -s lint

    # 3. Commit
    git add .
    git commit -m "feat: description of the feature"

    # 4. Push and create a Pull Request
    git push origin feature/feature-name
    # Create a PR on GitHub

    # 5. After approval, merge into main
    git checkout main
    git merge feature/feature-name

### 3. Commit messages

Conventional format:

    <type>(<scope>): <description>

    [optional body]

    [optional footer]

Allowed types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

Examples:
    feat(core): add the character management system
    fix(plugin): fix damage calculation
    docs(readme): update the legal disclaimer
    test(core): add tests for the dungeon generator

### 4. Windows Build

    # Build the executable, the release zip and its SHA256 checksum
    nox -s release

Each run:
1. increments the `build` entry of the `[tool.companion4soloplayer]`
   table in pyproject.toml,
2. stamps it into `src/companion4soloplayer/build_info.py`
   (read by the CLI banner, e.g. "companion4soloplayer v0.1.0 build 12"),
3. compiles plugins if necessary
4. runs PyInstaller on `companion4soloplayer.spec`,
5. packages the release archive with its SHA256 checksum.

---

## PRE-PUBLICATION CHECKLIST

### For each plugin

- [ ] The plugin name contains no registered trademark
- [ ] Class/monster names are generic
- [ ] Rules are rewritten in your own words
- [ ] The `README.md` file contains the legal disclaimer
- [ ] The `datas/plugin.yaml` file contains the correct metadata
- [ ] Visual assets are CC0 or created by you
- [ ] Unit tests pass
- [ ] Documentation is up to date

### For the overall project

- [ ] The main README contains the legal disclaimer
- [ ] The MIT license is present
- [ ] The `.gitignore` file is configured
- [ ] GitHub Actions are configured (automated tests)
- [ ] Code is formatted with Black
- [ ] Ruff linting passes without errors
- [ ] Types are checked with mypy
- [ ] Test coverage is >= 80%
- [ ] Documentation is complete

---

## USEFUL RESOURCES

### Legal documentation
- Nominative Fair Use (US): https://www.law.cornell.edu/wex/nominative_fair_use
- DMCA Takedown Process: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/dmca-takedown-policy
- Copyright vs Trademark: https://www.copyright.gov/help/faq/faq-differences.html

### Royalty-free assets
- Kenney.nl: https://kenney.nl/ - CC0 assets
- OpenGameArt.org: https://opengameart.org/ - Free assets
- Game-icons.net: https://game-icons.net/ - CC-BY icons

### Technical documentation
- PyQt6 Documentation: https://doc.qt.io/qtforpython/
- Pydantic Documentation: https://docs.pydantic.dev/
- PyInstaller Documentation: https://pyinstaller.org/en/stable/

### Community
- CasusNO: https://www.casusno.fr/ - French RPG forum
- TricTrac: https://forum.trictrac.net/ - Board game forum

---

## CONTACT AND SUPPORT

For any legal or technical question:
- Open an issue on GitHub
- Contact the maintainer: [your.email@example.com]

---

**Last updated**: 2026-10-01
**Document version**: 1.0.0
"""

    create_file("CONTEXT.md", context)

    _print_success(" CONTEXT.md file created! ")


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------
def main() -> None:
    """Main function of the script."""
    parser = argparse.ArgumentParser(
        prog="create_project.py",
        description=(
            "Create the Companion4SoloPlayer project structure, or (with "
            "--cleanup) only clean up an already generated project."
        ),
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help=(
            "Only clean up the generated project files (asks for "
            "confirmation), then exit without generating anything"
        ),
    )
    args = parser.parse_args()

    _print_title(" Companion4SoloPlayer - Project Creator ", _TITLE_STYLE)

    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        _print_title(
            f"Virtual environment is active:\n{venv}"
            "\n\nThis script should be run outside of a virtual environment to avoid conflicts.",
            _WARNING_STYLE
        )
        sys.exit()

    try:
        # --cleanup: clean the project directory, then exit without
        # generating anything.
        if args.cleanup:
            _cleanup_only()
            return

        # Refuse to silently overwrite an already generated project
        if _project_already_generated():
            _print_title("This project directory already contains generated files\nand maybe user created files!!!", _WARNING_STYLE)
            print(
                "  Everything will be deleted except:\n"
                "    - scripts/create_project.py\n"
                "    - assets/icons/logo-512x512.png\n"
                "    - .bintools/ (Qt utilities, Zig compiler)\n"
                "    - .git/ (version control history)\n"
            )
            if not _confirm_project_cleanup():
                _print_warning("Aborted: the project directory was left untouched! ")
                sys.exit(0)

            _print_step(" Cleaning up the project directory ")
            _cleanup_generated_project()

        # Create the structure
        create_directory_structure()

        # Create core files
        create_core_files()

        # Create plugins
        create_plugin_files()

        # Create the user interface
        create_ui_files()

        # Create tests files
        create_unittest_files()
        create_uitest_files()

        # Create project files (README, LICENSE, etc.)
        create_project_files()

        # Create scripts
        create_script_files()

        # Create the nox recipes file
        create_nox_file()

        # Create the editor settings (.vscode/settings.json)
        create_editor_files()

        # Create the CONTEXT.md file
        create_context_file()

        # Success message
        print()
        _print_title(" PROJECT CREATED SUCCESSFULLY! ", _SUCCESS_STYLE)

        _print_step(" Structure created: ")
        _print_with_check(f"{SRC_PACKAGE}/core/ (generic engine)")
        _print_with_check(f"{SRC_PACKAGE}/plugins/demo (demo plugin as an example)")
        _print_with_check(f"{SRC_PACKAGE}/ui/ (user interface)")
        _print_with_check("assets/")
        _print_with_check("data/")
        _print_with_check("tests/")
        _print_with_check("docs/")
        _print_with_check("build/")

        _print_step(" Main files created: ")
        _print_with_check("README.md (with legal disclaimer)")
        _print_with_check("LICENSE (MIT)")
        _print_with_check("pyproject.toml")
        _print_with_check(f"{SRC_PACKAGE}/main.py")
        _print_with_check("CONTEXT.md (complete development guide)")

        _print_step(" Build files created: ")
        _print_with_check("Scripts files (make_icon.py, resize_logo.py, compile_plugins.py)")
        _print_with_check("companion4soloplayer.spec (PyInstaller recipe)")
        _print_with_check("noxfile.py (in project root directory)")

        _print_step(" Editor settings created: ")
        _print_with_check(".vscode/settings.json (Visual Studio Code settings)")
        _print_with_check("companion4soloplayer.code-workspace (VS Code workspace file)")
        print("\n")

        _print_title(" NEXT STEPS", _SUCCESS_STYLE)

        _print_step(" 1. Create a virtual environment and install dev dependencies ")
        print("     nox -s setup-dev")

        _print_step(" 2. Activate the virtual environment ")
        print("     On Windows:")
        print(r"       PowerShell: .\.venv\Scripts\Activate.ps1")
        print(r"       CMD:        .venv\Scripts\activate.bat")
        print("     On Linux/macOS:")
        print(r"       source .venv/bin/activate")

        _print_step(" 3. Launch the application ")
        print("     c4sp")

        _print_step(" 4. (Optional) Build the Windows binary ")
        print("     nox -s release")

        print("\n See CONTEXT.md for the complete development guide")

    except Exception as e:
        _print_error(f"Error while creating the project: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
