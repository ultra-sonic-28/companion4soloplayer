"""
Player character persistence.

``CharacterSaveManager`` saves every piece of information of a newly created
player character into a structured file under ``data/saves/<plugin_name>/``.

The save directory (and every missing parent folder) is created automatically
on first use. Each character is stored in its own file named after the
*slugified* character name (see
:class:`~companion4soloplayer.utils.slugify.Slugify`).

The serialization format is YAML because it is already a hard project
dependency (``PyYAML``), every plugin data file already ships as YAML, and
YAML maps naturally onto nested mappings/sequences, keeping saved characters
human-readable and easy to hand-edit.

Examples::

    from companion4soloplayer.core.character_tracker import CharacterTracker
    from companion4soloplayer.utils.character_save import CharacterSaveManager

    tracker = CharacterTracker()
    character = tracker.create_character("Aragorn", "Ranger", {"body": 14})
    manager = CharacterSaveManager("demo_plugin")
    path = manager.save_character(character)
    # path == <project root>/data/saves/demo_plugin/aragorn.yaml
    reloaded = manager.load_character("aragorn")
    assert reloaded.name == "Aragorn"
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from companion4soloplayer.core.character_tracker import Character
from companion4soloplayer.utils.plugin_config import PluginConfigRegistry
from companion4soloplayer.utils.slugify import Slugify

__all__ = [
    "CharacterSaveManager",
    "OverwriteConfirmationError",
    "SavedCharacter",
    "default_saves_root",
]

SAVES_SUBDIR = Path("data") / "saves"
SAVE_FILE_EXTENSION = ".yaml"


class OverwriteConfirmationError(Exception):
    """Raised when a save file already exists and user confirmation is required.

    Attributes:
        file_path: Path of the existing save file.
        old_character: The character currently saved in the file.
        new_character: The character the user wants to save instead.
        old_saved_at: ISO-8601 timestamp of the existing save file.
    """

    def __init__(
        self,
        *,
        file_path: Path,
        old_character: Character,
        new_character: Character,
        old_saved_at: str,
    ) -> None:
        self.file_path = file_path
        self.old_character = old_character
        self.new_character = new_character
        self.old_saved_at = old_saved_at
        super().__init__(
            f"Save file {file_path} already exists; user confirmation needed to overwrite"
        )


def default_saves_root() -> Path:
    """Resolve the root of the saves tree (``data/saves``).

    Resolution order:

    1. Frozen (PyInstaller) build: ``<executable_dir>/data/saves``.
    2. Development: walk up from this module until a directory holding a
       ``data`` folder is found (the project root in a source checkout).
    3. Fallback: the current working directory.

    Returns:
        Absolute path of the saves root (parent folders are not created).
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        here = Path(__file__).resolve().parent
        base = next(
            (d for d in (here, *here.parents) if (d / "data").is_dir()),
            Path.cwd(),
        )
    return base / SAVES_SUBDIR


class SavedCharacter:
    """A player character together with its persistence metadata.

    Structured payload written to (and read from) a save file. Wraps a
    :class:`~companion4soloplayer.core.character_tracker.Character` instance
    and adds bookkeeping information (plugin name, save timestamp, plugin
    version) so each file is self-describing.

    Attributes:
        plugin_name: Name of the plugin the character belongs to.
        saved_at: UTC instant when the character was saved (ISO-8601).
        version: Plugin version (semver) read from the plugin's
            ``config.yaml``.
        character: The player character data.
    """

    def __init__(
        self,
        *,
        plugin_name: str,
        saved_at: datetime,
        version: str,
        character: Character,
    ) -> None:
        self.plugin_name = plugin_name
        self.saved_at = saved_at
        self.version = version
        self.character = character

    def to_dict(self) -> dict[str, Any]:
        """Return a plain, YAML/JSON-serializable dictionary."""
        return {
            "plugin_name": self.plugin_name,
            "saved_at": self.saved_at.isoformat(),
            "version": self.version,
            "character": self.character.model_dump(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SavedCharacter:
        """Rebuild a :class:`SavedCharacter` from a serialized dictionary.

        Args:
            data: Dictionary previously produced by :meth:`to_dict`.

        Returns:
            The reconstructed :class:`SavedCharacter`.

        Raises:
            KeyError: If a required key is missing from *data*.
        """
        character = Character.model_validate(data["character"])
        saved_at = data["saved_at"]
        if isinstance(saved_at, str):
            saved_at = datetime.fromisoformat(saved_at)
        return cls(
            plugin_name=data["plugin_name"],
            saved_at=saved_at,
            version=data["version"],
            character=character,
        )


class CharacterSaveManager:
    """Save and load player characters under ``data/saves/<plugin>/``.

    Args:
        plugin_name: Name of the plugin owning the saved characters.
        saves_root: Root of the saves tree. Defaults to the project-level
            ``data/saves`` directory resolved by
            :func:`default_saves_root`.

    Raises:
        OSError: If a directory or file cannot be created or accessed.
        ValueError: If a save file exists but is not a valid save.
    """

    def __init__(self, plugin_name: str, saves_root: Path | None = None) -> None:
        self.plugin_name = plugin_name
        self.saves_root = saves_root if saves_root is not None else default_saves_root()
        self.save_dir = self.saves_root / plugin_name
        self._slugger = Slugify()
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #

    def save_character(
        self, character: Character, *, overwrite: bool = False
    ) -> Path:
        """Persist *character* to ``data/saves/<plugin>/<slug>.yaml``.

        The plugin sub-directory (and every missing parent folder) is
        created automatically. The file is named after the slugified
        character name with a ``.yaml`` extension.

        If a save file already exists and *overwrite* is ``False``, an
        :class:`OverwriteConfirmationError` exception is raised so the
        caller can ask the user for confirmation before replacing the
        old values. When *overwrite* is ``True``, the existing file is
        silently replaced.

        Args:
            character: The player character to save.
            overwrite: When ``True``, overwrite an existing file without
                asking for confirmation. Defaults to ``False``.

        Returns:
            Path of the file that was written.

        Raises:
            OverwriteConfirmationError: If a save file already exists
                and *overwrite* is ``False``.
            OSError: If the file cannot be written.
        """
        self.save_dir.mkdir(parents=True, exist_ok=True)

        slug = self._slugger(character.name)
        file_path = self.save_dir / f"{slug}{SAVE_FILE_EXTENSION}"

        if file_path.is_file() and not overwrite:
            old_saved_at: str = ""
            try:
                raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    old_saved_at = str(raw.get("saved_at", ""))
            except (OSError, yaml.YAMLError):
                pass
            old_character = self.load_character(slug)
            if old_character is None:
                raise OSError(
                    f"Cannot read existing save file {file_path} for overwrite check"
                )
            raise OverwriteConfirmationError(
                file_path=file_path,
                old_character=old_character,
                new_character=character,
                old_saved_at=old_saved_at,
            )

        payload = SavedCharacter(
            plugin_name=self.plugin_name,
            saved_at=datetime.now(UTC),
            version=PluginConfigRegistry.instance().plugin_version(self.plugin_name),
            character=character,
        )
        text = yaml.safe_dump(
            payload.to_dict(),
            allow_unicode=True,
            sort_keys=False,
        )
        file_path.write_text(text, encoding="utf-8")

        self.logger.info("Saved character %r to %s", character.name, file_path)
        return file_path

    def load_character(self, slug: str) -> Character | None:
        """Load a character by its slugified name.

        Args:
            slug: Slugified character name (file name without extension).

        Returns:
            The loaded :class:`Character`, or ``None`` when no matching
            save file exists.

        Raises:
            ValueError: If the file exists but is not a valid save file.
            OSError: If the file cannot be read.
        """
        file_path = self.save_dir / f"{slug}{SAVE_FILE_EXTENSION}"
        if not file_path.is_file():
            return None

        try:
            data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid save file {file_path}: cannot parse YAML: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(
                f"Invalid save file {file_path}: expected a mapping, " f"got {type(data).__name__}"
            )
        return SavedCharacter.from_dict(data).character

    def list_characters(self) -> list[str]:
        """Return the slugified names of every saved character.

        Returns:
            List of slugs (file stems) sorted alphabetically. Empty list
            when the plugin directory does not exist yet.
        """
        if not self.save_dir.is_dir():
            return []
        return sorted(
            path.stem for path in self.save_dir.glob(f"*{SAVE_FILE_EXTENSION}") if path.is_file()
        )

    def delete_character(self, slug: str) -> bool:
        """Delete the save file for *slug*.

        Args:
            slug: Slugified character name (file name without extension).

        Returns:
            ``True`` when a file was removed, ``False`` when none existed.
        """
        file_path = self.save_dir / f"{slug}{SAVE_FILE_EXTENSION}"
        if not file_path.is_file():
            return False
        file_path.unlink()
        self.logger.info("Deleted save file %s", file_path)
        return True

    def character_exists(self, slug: str) -> bool:
        """Return ``True`` when a save file exists for *slug*."""
        return (self.save_dir / f"{slug}{SAVE_FILE_EXTENSION}").is_file()

    @property
    def directory(self) -> Path:
        """Return the plugin save directory (created on first save)."""
        return self.save_dir
