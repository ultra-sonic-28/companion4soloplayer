#!/usr/bin/env python3
"""
Main entry point for Companion4SoloPlayer.
"""

import logging
import sys

from PySide6.QtCore import QTimer

from companion4soloplayer import __version__
from companion4soloplayer.app.application import CompanionApplication
from companion4soloplayer.ui.main_window import MainWindow
from companion4soloplayer.ui.splash_window import SPLASH_DURATION_MS, SplashScreen
from companion4soloplayer.utils.config_manager import ConfigManager
from companion4soloplayer.utils.logger import APP_LOGGER_NAME, setup_logging


def main() -> None:
    """Main application entry point."""
    # The configuration drives both the logger and the application: it is
    # read first, so that everything happening afterwards can be logged.
    config = ConfigManager()
    setup_logging(config)

    # The same configuration instance is shared application-wide.
    app = CompanionApplication(sys.argv, config=config)

    splash = SplashScreen(duration_ms=SPLASH_DURATION_MS)
    splash.show()

    app.processEvents()

    app.setApplicationName("Companion4SoloPlayer")
    app.setApplicationVersion(__version__)

    window = MainWindow()

    QTimer.singleShot(SPLASH_DURATION_MS, window.show)

    exit_code = app.exec()
    # Every way of leaving the application goes through this point, so it is
    # the place for the last message of the session.
    logging.getLogger(APP_LOGGER_NAME).info("Application exiting with code %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
