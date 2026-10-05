import sys
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any, cast

import tomlkit
from tomlkit.items import Table

# Location of the configuration file, relative to the project root (source
# checkout) or to the executable directory (frozen build).
CONFIG_SUBDIR = Path("data") / "config"
CONFIG_FILENAME = "config.toml"


def default_config_path() -> Path:
    """Resolve the path of the configuration file.

    Resolution order:

    1. Frozen (PyInstaller) build: ``<executable_dir>/data/config/config.toml``,
       matching the portable layout where ``data`` sits next to the executable.
    2. Development: walk up from this module until a directory holding a
       ``data`` folder is found (the project root in a source checkout).
    3. Fallback: the current working directory.

    Returns:
        Absolute path of the configuration file (parent folders are not created).
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        here = Path(__file__).resolve().parent
        base = next((d for d in (here, *here.parents) if (d / "data").is_dir()), Path.cwd())
    return base / CONFIG_SUBDIR / CONFIG_FILENAME


class ConfigManager:
    """Reads and writes the TOML configuration file shared by the application."""

    def __init__(self, filename: str | Path | None = None) -> None:
        """Load the configuration file, or create it with default values.

        Args:
            filename: Path of the TOML file. Defaults to
                :func:`default_config_path` (``data/config/config.toml``).
        """
        self.filename = Path(filename) if filename is not None else default_config_path()

        # Default values
        self.data = tomlkit.table()
        self.data["window"] = {
            "x": 0,
            "y": 0,
            "width": 1280,
            "height": 720,
            "maximized": True,
        }

        # Load or create the file
        if self.filename.exists():
            self.load()
        else:
            self.save()  # ← creates the TOML file with default values

    def load(self) -> None:
        """Load the TOML file if it exists."""
        try:
            with open(self.filename, encoding="utf-8") as f:
                file_data = tomlkit.parse(f.read())
            self._deep_update(self.data, file_data)
        except Exception:
            # Corrupted file → rewrite with default values
            self.save()

    def save(self) -> None:
        """Write the TOML to the file."""
        # The data/config folders may not exist yet (first launch).
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(self.data))

    def window(self) -> Table:
        """Return the ``[window]`` table."""
        return cast(Table, self.data["window"])

    def logging(self) -> Table:
        """Return the ``[logging]`` table."""
        return cast(Table, self.data["logging"])

    @staticmethod
    def _deep_update(base: MutableMapping[str, Any], updates: Mapping[str, Any]) -> None:
        """Perform a recursive update of the TOML tables."""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigManager._deep_update(base[key], value)
            else:
                base[key] = value
