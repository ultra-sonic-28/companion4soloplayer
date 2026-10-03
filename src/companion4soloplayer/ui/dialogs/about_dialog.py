"""
About dialog for Companion4SoloPlayer.

Shows the application logo on the left and the application name,
description, version, build number and build datetime on the right,
with a Close button centered below.
"""

import tomllib
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path

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
from companion4soloplayer.utils.resource_manager import ResourceManager

try:
    from companion4soloplayer.build_info import BUILD_DATETIME, BUILD_NUMBER
except ImportError:
    # build_info.py is written by the nox 'release' session; a fresh
    # source checkout may not have it yet.
    BUILD_DATETIME = "unknown"
    BUILD_NUMBER = 0

try:
    DESCRIPTION = str(metadata("companion4soloplayer")["Summary"])
except PackageNotFoundError:
    # Package not installed (running from sources without pip install):
    # fall back to the static project description.
    DESCRIPTION = "Open-source companion application for dungeon crawler style board games"

APP_NAME = "Companion4SoloPlayer"
LOGO_SIZE = 128


def _read_build_version(pyproject_path: Path) -> int:
    """Read the build counter declared in pyproject.toml.

    The counter lives in the [tool.companion4soloplayer] table and is
    incremented by the nox 'build-exe' session on every generated
    executable.

    Args:
        pyproject_path: Path of the pyproject.toml file to read.

    Returns:
        The build counter, or the build number stamped in build_info.py
        when pyproject.toml cannot be read (installed package or frozen
        executable).
    """
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        return int(data["tool"]["companion4soloplayer"]["build"])
    # OSError: pyproject.toml not shipped; KeyError/TypeError/ValueError:
    # missing or malformed [tool.companion4soloplayer] entry.
    except (OSError, KeyError, TypeError, ValueError):
        return BUILD_NUMBER


# In a source checkout, pyproject.toml sits four levels above this file
# (src/companion4soloplayer/ui/dialogs/about_dialog.py).
build_version = _read_build_version(Path(__file__).resolve().parents[4] / "pyproject.toml")


class AboutDialog(QDialog):
    """About dialog: logo on the left, application info on the right."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the about dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("About " + APP_NAME)
        rm = ResourceManager.instance()
        self.setWindowIcon(QIcon(str(rm.get_icon("logo-512x512.png"))))

        self._setup_ui()

        self.setFixedSize(400, 200)

    def _setup_ui(self) -> None:
        """Set up the two-column layout and the centered Close button."""
        layout = QVBoxLayout(self)

        columns_layout = QHBoxLayout()

        # Left column: application logo scaled to 128x128 pixels
        self.logo_label = QLabel()
        rm = ResourceManager.instance()
        pixmap = QPixmap(str(rm.get_icon("logo-512x512.png")))
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

        # Right column: application name, description, version with its
        # build number, and build datetime (HTML for these, plain text
        # description)
        info_layout = QVBoxLayout()

        name_label = QLabel(f"<h2>{APP_NAME}</h2>")
        description_label = QLabel(DESCRIPTION)
        description_label.setWordWrap(True)
        version_label = QLabel(f"<b>Version:</b> {__version__} build {build_version}")
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
