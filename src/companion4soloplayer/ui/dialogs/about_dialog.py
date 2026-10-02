"""
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
