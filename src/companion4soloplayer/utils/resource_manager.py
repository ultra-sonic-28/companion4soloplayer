"""
Centralized resource manager.

Compatible with PyInstaller (_MEIPASS) and standalone development.

Python 3.13+ / PySide6
"""

from __future__ import annotations

import logging
import sys
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from PySide6.QtGui import QIcon, QPixmap
    from PySide6.QtMultimedia import QSoundEffect

logger = logging.getLogger(__name__)


class ResourceNotFoundError(FileNotFoundError):
    """Raised when a requested resource does not exist."""


class ResourceManager:
    """
    Singleton centralizing access to the application's resources.

    Automatically handles the difference between:

    - A development environment (path relative to the module)
    - A PyInstaller bundle (sys._MEIPASS)

    Usage:
        rm = ResourceManager.instance()
        logo = rm.get_icon("logo-512x512.png")
        pixmap = QPixmap(str(logo))
    """

    _instance: Self | None = None
    _initialized: bool = False

    # Type -> subfolder mapping (configurable)
    _SUBDIRS: dict[str, str] = {
        "icon": "icons",
        "image": "images",
        "sound": "sounds",
        "music": "music",
        "file": "files",
        "data": "data",
        "font": "fonts",
    }

    # Allowed extensions per type (secures paths)
    _EXTENSIONS: dict[str, tuple[str, ...]] = {
        "icon": (".png", ".svg", ".ico"),
        "image": (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"),
        "sound": (".wav", ".ogg", ".mp3"),
        "music": (".mp3", ".ogg", ".wav", ".flac"),
        "font": (".ttf", ".otf", ".woff", ".woff2"),
    }

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        root: Path | str | None = None,
        *,
        strict: bool = True,
    ) -> None:
        """
        Args:
            root: Resources root. Auto-detected if None.
            strict: Raises ResourceNotFoundError if the resource does not exist.
        """
        if self._initialized:
            return

        self._strict = strict
        self._root: Path = self._detect_root(root)
        self._path_cache: dict[str, Path] = {}
        self._object_cache: dict[str, object] = {}  # QPixmap, QIcon, etc.

        logger.info("ResourceManager initialized: root=%s", self._root)
        self._initialized = True

    @classmethod
    def instance(cls) -> Self:
        """Returns the single instance of the manager."""
        if cls._instance is None:
            cls()
        assert cls._instance is not None
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Resets the singleton (useful for tests)."""
        cls._instance = None
        cls._initialized = False

    # ------------------------------------------------------------------ #
    # Root detection                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _detect_root(root: Path | str | None) -> Path:
        """Automatically detects the resources root.

        Resolution order:

        1. The explicit ``root`` argument.
        2. PyInstaller bundle: ``<_MEIPASS>/assets`` when present (the
           spec ships the assets folder as-is), else ``_MEIPASS`` itself.
        3. Walk up from this file until a directory holding an ``assets``
           (or ``resources``) folder is found; in a source checkout that
           directory is the project root.
        4. ``<cwd>/assets`` (installed package run from the project root).
        5. The current module's folder, as a last resort.
        """
        if root is not None:
            return Path(root).resolve()

        # PyInstaller case (bundle)
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            bundle = Path(sys._MEIPASS).resolve()  # noqa: SLF001
            bundled_assets = bundle / "assets"
            if bundled_assets.is_dir():
                return bundled_assets
            return bundle

        # Development case: assets/ sits at the project root, walk up
        # from this file (companion4soloplayer/utils/resource_manager.py)
        # until the folder is found; fall back to the current working
        # directory (installed package run from the project root).
        here = Path(__file__).resolve().parent
        for directory in (here, *here.parents, Path.cwd()):
            for folder_name in ("assets", "resources"):
                candidate = directory / folder_name
                if candidate.is_dir():
                    return candidate

        # Last resort: the current module's folder.
        return here

    # ------------------------------------------------------------------ #
    # Public API: paths                                                   #
    # ------------------------------------------------------------------ #

    @property
    def root(self) -> Path:
        return self._root

    def get_resource(
        self,
        name: str,
        *,
        category: str = "file",
        validate: bool = True,
    ) -> Path:
        """
        Resolves and returns the absolute path of a resource.

        Args:
            name: Filename (e.g. "logo.png") or relative path
                  (e.g. "subdir/logo.png").
            category: Resource type (icon, image, sound, music, file...).
            validate: Checks existence and extension.

        Returns:
            The absolute path to the resource.

        Raises:
            ResourceNotFoundError: If strict=True and the resource does not exist.
        """
        cache_key = f"{category}:{name}"
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        subdir = self._SUBDIRS.get(category, "")
        path = (self._root / subdir / name).resolve()

        if validate:
            self._validate(path, category)

        self._path_cache[cache_key] = path
        return path

    def get_icon(self, name: str) -> Path:
        return self.get_resource(name, category="icon")

    def get_image(self, name: str) -> Path:
        return self.get_resource(name, category="image")

    def get_sound(self, name: str) -> Path:
        return self.get_resource(name, category="sound")

    def get_music(self, name: str) -> Path:
        return self.get_resource(name, category="music")

    def get_file(self, name: str) -> Path:
        return self.get_resource(name, category="file")

    def get_data(self, name: str) -> Path:
        return self.get_resource(name, category="data")

    def get_font(self, name: str) -> Path:
        return self.get_resource(name, category="font")

    # ------------------------------------------------------------------ #
    # Public API: loaded PySide6 objects (with cache)                     #
    # ------------------------------------------------------------------ #

    def load_pixmap(self, name: str) -> QPixmap:
        """Loads and caches a QPixmap."""
        from PySide6.QtGui import QPixmap

        cache_key = f"pixmap:{name}"
        if cache_key in self._object_cache:
            return self._object_cache[cache_key]  # type: ignore[return-value]

        path = self.get_image(name)
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise ResourceNotFoundError(f"Unable to load image: {path}")

        self._object_cache[cache_key] = pixmap
        return pixmap

    def load_icon(self, name: str) -> QIcon:
        """Loads and caches a QIcon."""
        from PySide6.QtGui import QIcon

        cache_key = f"icon:{name}"
        if cache_key in self._object_cache:
            return self._object_cache[cache_key]  # type: ignore[return-value]

        path = self.get_icon(name)
        icon = QIcon(str(path))
        if icon.isNull():
            raise ResourceNotFoundError(f"Invalid icon: {path}")

        self._object_cache[cache_key] = icon
        return icon

    def load_sound(self, name: str) -> QSoundEffect:
        """Loads a QSoundEffect (short sounds, non-blocking)."""
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QSoundEffect

        cache_key = f"sound:{name}"
        if cache_key in self._object_cache:
            return self._object_cache[cache_key]  # type: ignore[return-value]

        path = self.get_sound(name)
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(str(path)))
        self._object_cache[cache_key] = effect
        return effect

    # ------------------------------------------------------------------ #
    # Utilities                                                           #
    # ------------------------------------------------------------------ #

    def list_resources(self, category: str = "file") -> list[Path]:
        """Lists all resources of a given category."""
        subdir = self._SUBDIRS.get(category, "")
        folder = self._root / subdir
        if not folder.is_dir():
            return []
        return sorted(p for p in folder.iterdir() if p.is_file())

    def clear_cache(self, *, paths: bool = False, objects: bool = True) -> None:
        """Clears caches. By default, keeps paths (stable)."""
        if objects:
            self._object_cache.clear()
        if paths:
            self._path_cache.clear()

    # ------------------------------------------------------------------ #
    # Internal validation                                                 #
    # ------------------------------------------------------------------ #

    def _validate(self, path: Path, category: str) -> None:
        """Checks existence + allowed extension."""
        if not path.exists():
            if self._strict:
                raise ResourceNotFoundError(f"Resource not found: {path}")
            logger.warning("Resource not found: %s", path)
            return

        allowed = self._EXTENSIONS.get(category)
        if allowed and path.suffix.lower() not in allowed:
            raise ValueError(
                f"Extension {path.suffix!r} not allowed for {category!r}. " f"Expected: {allowed}"
            )

        # Security: prevents escaping the root (path traversal)
        try:
            path.relative_to(self._root)
        except ValueError as e:
            raise ValueError(f"Path outside root: {path}") from e


# ---------------------------------------------------------------------- #
# Convenient helper: global function (optional)                           #
# ---------------------------------------------------------------------- #


@lru_cache(maxsize=256)
def resource_path(name: str, category: str = "file") -> Path:
    """Quick access via a global function (paths are cached)."""
    return ResourceManager.instance().get_resource(name, category=category)
