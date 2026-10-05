"""
Companion4SoloPlayer - companion application for tabletop board games.
"""

from importlib.metadata import PackageNotFoundError, version

APPLICATION_NAME = "Companion4SoloPlayer"
ORGANIZATION_NAME = ""

try:
    __version__ = version("companion4soloplayer")
except PackageNotFoundError:
    # Package not installed (running from sources without pip install -e .)
    __version__ = "0.0.0+unknown"
