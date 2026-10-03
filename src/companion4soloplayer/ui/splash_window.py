from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QSplashScreen

from companion4soloplayer.utils.resource_manager import ResourceManager, ResourceNotFoundError

# Constant for the display duration (in milliseconds)
SPLASH_DURATION_MS = 3000  # 3 seconds

# Splash image resource, resolved through the resource manager
SPLASH_IMAGE_NAME = "splashscreen-1024.png"

# Fallback panel used when the splash image cannot be loaded
FALLBACK_WIDTH = 400
FALLBACK_HEIGHT = 300


def _build_splash_pixmap() -> QPixmap:
    """Build the background pixmap of the splash screen.

    The pixmap is loaded from the splash image, so its size follows the
    image dimensions: swapping the artwork for another resolution needs
    no code change. If the image is missing or unreadable, a solid dark
    blue panel of the fallback size is used instead.

    Returns:
        The pixmap to display (never null).
    """
    # The resource manager raises when the image is missing: keep the
    # fallback panel usable instead of crashing the splash screen.
    image_path: Path | None
    try:
        image_path = ResourceManager.instance().get_image(SPLASH_IMAGE_NAME)
    except ResourceNotFoundError:
        image_path = None

    if image_path is not None:
        pixmap = QPixmap(str(image_path))
        if not pixmap.isNull():
            return pixmap

    fallback = QPixmap(FALLBACK_WIDTH, FALLBACK_HEIGHT)
    fallback.fill(Qt.GlobalColor.darkBlue)
    return fallback


class SplashScreen(QSplashScreen):
    """Custom splash screen displayed when the application starts."""

    def __init__(self, duration_ms: int = SPLASH_DURATION_MS):
        # Creating a pixmap for the background from the splash image
        pixmap = _build_splash_pixmap()

        # Configuring window flags before initialization
        flags = (
            Qt.WindowType.FramelessWindowHint  # No border or title bar
            | Qt.WindowType.WindowStaysOnTopHint  # Always on top
            | Qt.WindowType.SplashScreen  # Splash screen type
        )

        # Using the QSplashScreen(QPixmap, WindowType) overload
        super().__init__(pixmap, flags)

        self.duration_ms = duration_ms
        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self) -> None:
        """Configure the interface of the splash screen."""
        # Adding a message
        self.showMessage(
            "Loading the application...",
            alignment=Qt.AlignmentFlag.AlignCenter,
            color=Qt.GlobalColor.white,
        )

        # Configuration of the font
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.setFont(font)

    def _setup_timer(self) -> None:
        """Configure the timer to close the splash screen after the specified duration."""
        QTimer.singleShot(self.duration_ms, self.close)
        self.raise_()  # Ensure the window is on top
        self.activateWindow()  # Activate the window

    def show(self) -> None:
        """Display the splash screen."""
        super().show()
