#!/usr/bin/env python3
"""
Main entry point for Companion4SoloPlayer.
"""

import sys

from PySide6.QtCore import QTimer

from companion4soloplayer import __version__
from companion4soloplayer.application import CompanionApplication
from companion4soloplayer.ui.main_window import MainWindow
from companion4soloplayer.ui.splash_window import SPLASH_DURATION_MS, SplashScreen


def main() -> None:
    """Main application entry point."""
    # Reads data/config/config.toml and keeps it available app-wide.
    app = CompanionApplication(sys.argv)

    splash = SplashScreen(duration_ms=SPLASH_DURATION_MS)
    splash.show()

    app.processEvents()

    app.setApplicationName("Companion4SoloPlayer")
    app.setApplicationVersion(__version__)

    window = MainWindow()

    QTimer.singleShot(SPLASH_DURATION_MS, window.show)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
