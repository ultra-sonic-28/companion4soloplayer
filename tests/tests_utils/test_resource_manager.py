"""
Tests for the centralized ResourceManager.

Covers root detection (development, explicit and PyInstaller layouts),
path resolution against the assets shipped with the project, validation
(strict mode, allowed extensions, path traversal), caching and the
PySide6 object loaders.
"""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from companion4soloplayer.utils.resource_manager import (
    ResourceManager,
    ResourceNotFoundError,
    resource_path,
)

# tests/tests_utils/test_resource_manager.py -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_ROOT = PROJECT_ROOT / "assets"

# Resources actually shipped in the repository
LOGO_NAME = "logo-512x512.png"
SPLASH_NAME = "splashscreen-1024.png"


@pytest.fixture(autouse=True)
def fresh_singleton() -> Iterator[None]:
    """Give every test a pristine singleton and empty caches."""
    ResourceManager.reset()
    resource_path.cache_clear()
    yield
    ResourceManager.reset()
    resource_path.cache_clear()


# ------------------------------------------------------------------ #
# Singleton                                                           #
# ------------------------------------------------------------------ #


def test_instance_returns_the_same_object() -> None:
    """instance() always exposes the same singleton."""
    assert ResourceManager.instance() is ResourceManager.instance()


def test_reset_creates_a_new_instance() -> None:
    """reset() drops the singleton so the next call builds a new one."""
    first = ResourceManager.instance()
    ResourceManager.reset()
    second = ResourceManager.instance()
    assert second is not first


def test_arguments_are_ignored_once_initialized(tmp_path: Path) -> None:
    """The singleton keeps the configuration of its first construction."""
    first = ResourceManager(root=tmp_path)
    second = ResourceManager(root=tmp_path / "ignored")
    assert first is second
    assert second.root == tmp_path.resolve()


# ------------------------------------------------------------------ #
# Root detection                                                      #
# ------------------------------------------------------------------ #


def test_default_root_is_the_project_assets_folder() -> None:
    """In development the root is <project root>/assets."""
    assert ResourceManager.instance().root == ASSETS_ROOT.resolve()


def test_explicit_root_wins_over_detection(tmp_path: Path) -> None:
    """An explicit root is resolved and used as-is."""
    manager = ResourceManager(root=tmp_path)
    assert manager.root == tmp_path.resolve()


def test_explicit_root_accepts_a_string(tmp_path: Path) -> None:
    """A string root is accepted and resolved to a Path."""
    manager = ResourceManager(root=str(tmp_path))
    assert isinstance(manager.root, Path)
    assert manager.root == tmp_path.resolve()


def test_detect_root_uses_bundled_assets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A PyInstaller bundle resolves to <_MEIPASS>/assets when present."""
    bundle = tmp_path / "_internal"
    (bundle / "assets").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert ResourceManager._detect_root(None) == (bundle / "assets").resolve()


def test_detect_root_falls_back_to_bundle_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without a bundled assets folder the bundle root itself is used."""
    bundle = tmp_path / "_internal"
    bundle.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert ResourceManager._detect_root(None) == bundle.resolve()


# ------------------------------------------------------------------ #
# Path resolution                                                     #
# ------------------------------------------------------------------ #


def test_get_icon_resolves_the_logo() -> None:
    """get_icon() resolves into the icons subfolder of the root."""
    path = ResourceManager.instance().get_icon(LOGO_NAME)
    assert path == (ASSETS_ROOT / "icons" / LOGO_NAME).resolve()
    assert path.is_file()


def test_get_image_resolves_the_splashscreen() -> None:
    """get_image() resolves into the images subfolder of the root."""
    path = ResourceManager.instance().get_image(SPLASH_NAME)
    assert path == (ASSETS_ROOT / "images" / SPLASH_NAME).resolve()
    assert path.is_file()


def test_get_resource_maps_every_documented_category(tmp_path: Path) -> None:
    """Each category is resolved through its own subfolder."""
    expected = {
        "icon": "icons",
        "image": "images",
        "sound": "sounds",
        "music": "music",
        "file": "files",
        "data": "data",
        "font": "fonts",
    }
    manager = ResourceManager(root=tmp_path)
    for category, subdir in expected.items():
        path = manager.get_resource("resource.bin", category=category, validate=False)
        assert path == (tmp_path / subdir / "resource.bin").resolve()


def test_unknown_category_falls_back_to_the_root(tmp_path: Path) -> None:
    """An unknown category resolves directly under the root."""
    manager = ResourceManager(root=tmp_path)
    path = manager.get_resource("file.txt", category="unknown", validate=False)
    assert path == (tmp_path / "file.txt").resolve()


# ------------------------------------------------------------------ #
# Caching                                                             #
# ------------------------------------------------------------------ #


def test_get_resource_caches_resolved_paths(tmp_path: Path) -> None:
    """Resolved paths are cached per category:name key."""
    manager = ResourceManager(root=tmp_path)
    first = manager.get_resource("file.txt", validate=False)
    second = manager.get_resource("file.txt", validate=False)
    assert first is second


def test_clear_cache_paths_forces_a_new_resolution(tmp_path: Path) -> None:
    """clear_cache(paths=True) drops the path cache."""
    manager = ResourceManager(root=tmp_path)
    first = manager.get_resource("file.txt", validate=False)
    manager.clear_cache(paths=True)
    second = manager.get_resource("file.txt", validate=False)
    assert second == first
    assert second is not first


def test_clear_cache_keeps_paths_by_default(tmp_path: Path) -> None:
    """By default only the object cache is cleared."""
    manager = ResourceManager(root=tmp_path)
    first = manager.get_resource("file.txt", validate=False)
    manager.clear_cache()
    second = manager.get_resource("file.txt", validate=False)
    assert second is first


# ------------------------------------------------------------------ #
# Validation                                                          #
# ------------------------------------------------------------------ #


def test_missing_resource_raises_in_strict_mode() -> None:
    """Strict mode (the default) raises ResourceNotFoundError."""
    with pytest.raises(ResourceNotFoundError):
        ResourceManager.instance().get_file("does-not-exist.txt")


def test_missing_resource_is_returned_in_non_strict_mode() -> None:
    """Non-strict mode logs a warning and returns the path anyway."""
    manager = ResourceManager(strict=False)
    path = manager.get_file("does-not-exist.txt")
    assert path == (ASSETS_ROOT / "files" / "does-not-exist.txt").resolve()
    assert not path.exists()


def test_disallowed_extension_raises(tmp_path: Path) -> None:
    """A file whose extension is not allowed for the category raises."""
    icons = tmp_path / "icons"
    icons.mkdir(parents=True)
    (icons / "impostor.txt").write_text("not an icon", encoding="utf-8")

    manager = ResourceManager(root=tmp_path)
    with pytest.raises(ValueError, match="not allowed"):
        manager.get_icon("impostor.txt")


def test_path_outside_root_raises(tmp_path: Path) -> None:
    """Path traversal is rejected: the resource must stay under the root."""
    root = tmp_path / "assets"
    root.mkdir()
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")

    manager = ResourceManager(root=root)
    with pytest.raises(ValueError, match="outside root"):
        manager.get_resource("../../outside.txt", category="file")


# ------------------------------------------------------------------ #
# Listing and global helper                                           #
# ------------------------------------------------------------------ #


def test_list_resources_returns_sorted_files(tmp_path: Path) -> None:
    """list_resources() returns the sorted files of the subfolder."""
    icons = tmp_path / "icons"
    icons.mkdir(parents=True)
    (icons / "z.png").write_bytes(b"")
    (icons / "a.png").write_bytes(b"")
    (icons / "subfolder").mkdir()  # directories are ignored

    manager = ResourceManager(root=tmp_path)
    listed = manager.list_resources("icon")
    assert [path.name for path in listed] == ["a.png", "z.png"]


def test_list_resources_returns_an_empty_list_when_missing(tmp_path: Path) -> None:
    """A missing subfolder yields an empty list, not an error."""
    manager = ResourceManager(root=tmp_path)
    assert manager.list_resources("icon") == []


def test_resource_path_matches_the_manager_lookup() -> None:
    """The global helper resolves like ResourceManager.get_resource()."""
    expected = ResourceManager.instance().get_icon(LOGO_NAME)
    assert resource_path(LOGO_NAME, "icon") == expected


def test_resource_path_is_cached() -> None:
    """Two identical calls return the very same Path object."""
    first = resource_path(LOGO_NAME, "icon")
    second = resource_path(LOGO_NAME, "icon")
    assert first is second


# ------------------------------------------------------------------ #
# PySide6 object loaders                                              #
# ------------------------------------------------------------------ #


def test_load_pixmap_returns_a_cached_pixmap(qtbot: QtBot) -> None:
    """load_pixmap() loads the image once and reuses the cached object."""
    manager = ResourceManager.instance()
    pixmap = manager.load_pixmap(SPLASH_NAME)
    assert not pixmap.isNull()
    assert manager.load_pixmap(SPLASH_NAME) is pixmap


def test_load_icon_returns_a_cached_icon(qtbot: QtBot) -> None:
    """load_icon() loads the icon once and reuses the cached object."""
    manager = ResourceManager.instance()
    icon = manager.load_icon(LOGO_NAME)
    assert not icon.isNull()
    assert manager.load_icon(LOGO_NAME) is icon


def test_clear_cache_drops_loaded_objects(qtbot: QtBot) -> None:
    """clear_cache() (default) forces the next load to build a new object."""
    manager = ResourceManager.instance()
    first = manager.load_pixmap(SPLASH_NAME)
    manager.clear_cache()
    second = manager.load_pixmap(SPLASH_NAME)
    assert second is not first


def test_load_pixmap_missing_resource_raises() -> None:
    """A missing image raises ResourceNotFoundError in strict mode."""
    with pytest.raises(ResourceNotFoundError):
        ResourceManager.instance().load_pixmap("does-not-exist.png")
