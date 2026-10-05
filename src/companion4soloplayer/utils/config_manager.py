import os
from collections.abc import Mapping, MutableMapping
from typing import Any, cast

import tomlkit
from tomlkit.items import Table


class ConfigManager:
    def __init__(self, filename: str = "config.toml") -> None:
        self.filename = filename

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
        if os.path.exists(self.filename):
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
