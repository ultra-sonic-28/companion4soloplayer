import contextlib
import logging
import shutil
import sys
from collections.abc import Mapping, MutableMapping
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

import tomlkit
from tomlkit.items import Table

# Location of the configuration file, relative to the project root (source
# checkout) or to the executable directory (frozen build).
CONFIG_SUBDIR = Path("data") / "config"
CONFIG_FILENAME = "config.toml"

# Suffix appended to the file name when its content cannot be parsed: the
# unreadable file is preserved under that name before the defaults are
# written back, so a hand edit is never silently lost.
INVALID_SUFFIX = ".invalid"

# qt_material stylesheet applied at startup when the configuration does not
# specify another one.
DEFAULT_THEME = "light_blue.xml"


class TooltipCornerType(StrEnum):
    """Shape of the corners of a tooltip, as configured in ``[tooltip]``.

    ``ROUND`` rounds the corners with the ``border_radius`` radius;
    ``SQUARE`` keeps right angles (the radius is then ignored).
    """

    ROUND = "round"
    SQUARE = "square"


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
        self.data["logging"] = {
            "enabled": True,
            # Standard logging level name (DEBUG, INFO, WARNING, ...).
            "level": "DEBUG",
            "file": "./companion4soloplayer.log",
            # "write" -> recreate the file, "append" -> keep its content.
            "mode": "write",
        }
        self.data["appearance"] = {
            # qt_material stylesheet applied by main() at startup.
            "theme": DEFAULT_THEME,
        }
        # Style of the description tooltips (see
        # companion4soloplayer.ui.widgets.tooltip): these values are the
        # defaults displayed by every tooltip.
        self.data["tooltip"] = {
            "background_color": "#ffffff",
            "text_color": "#000000",
            "border_color": "#3b3a98",
            # Border thickness, in pixels.
            "border_size": 2,
            # Corner radius, in pixels (used when corner_type = "round").
            "border_radius": 5,
            # "round" (radius applied) or "square" (right angles).
            "corner_type": "round",
        }

        # Load or create the file
        if self.filename.exists():
            self.load()
        else:
            self.save()  # ← creates the TOML file with default values

    def load(self) -> None:
        """Load the TOML file if it exists.

        A file that cannot be parsed (typically a hand edit with an
        invalid syntax, an unquoted string for instance) is **never
        silently discarded**: its content is first preserved as
        ``<file><INVALID_SUFFIX>`` next to the configuration file and a
        warning is logged, then the defaults are written back so the
        application can still start.
        """
        try:
            with open(self.filename, encoding="utf-8") as f:
                file_data = tomlkit.parse(f.read())
        except FileNotFoundError:
            # Removed while the application was running: keep the
            # in-memory values (the next save() recreates the file).
            return
        except Exception:
            # Preserve the unreadable file before restoring the defaults.
            self._preserve_invalid_file()
            logging.getLogger(__name__).warning(
                "Invalid configuration file %s: defaults restored, your " "content is kept as %s",
                self.filename,
                self.filename.with_name(self.filename.name + INVALID_SUFFIX),
            )
            self.save()
            return
        self._deep_update(self.data, file_data)

    def _preserve_invalid_file(self) -> None:
        """Copy the unreadable file aside before it gets rewritten."""
        # Nothing to preserve (missing or unreadable file).
        with contextlib.suppress(OSError):
            shutil.copyfile(
                self.filename,
                self.filename.with_name(self.filename.name + INVALID_SUFFIX),
            )

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

    def appearance(self) -> Table:
        """Return the ``[appearance]`` table."""
        return cast(Table, self.data["appearance"])

    def tooltip(self) -> Table:
        """Return the ``[tooltip]`` table.

        The table holds the default style of every description tooltip
        (background and text colors, border color/size, corner radius
        and corner shape, see :class:`TooltipCornerType`).
        """
        return cast(Table, self.data["tooltip"])

    def tooltip_corner_type(self) -> TooltipCornerType:
        """Return the configured tooltip corner shape.

        Returns:
            The configured :class:`TooltipCornerType`, or
            :attr:`TooltipCornerType.ROUND` when the value is missing or
            not a valid ``round``/``square`` name.
        """
        try:
            return TooltipCornerType(str(self.tooltip().get("corner_type", "")))
        except ValueError:
            return TooltipCornerType.ROUND

    def theme(self) -> str:
        """Return the qt_material theme stored in the configuration.

        Returns:
            The configured theme, or :data:`DEFAULT_THEME` when the key is
            missing or empty.
        """
        theme = str(self.appearance().get("theme", DEFAULT_THEME))
        return theme or DEFAULT_THEME

    @staticmethod
    def _deep_update(base: MutableMapping[str, Any], updates: Mapping[str, Any]) -> None:
        """Perform a recursive update of the TOML tables."""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigManager._deep_update(base[key], value)
            else:
                base[key] = value
