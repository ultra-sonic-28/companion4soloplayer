"""
Asset path resolution for Companion4SoloPlayer.

Locates the application assets in source, installed and packaged
(PyInstaller one-dir) modes.
"""

import sys
from pathlib import Path

LOGO_PATH = Path("assets") / "icons" / "logo-512x512.png"
SPLASH_IMAGE_PATH = Path("assets") / "images" / "splashscreen-1024.png"


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
