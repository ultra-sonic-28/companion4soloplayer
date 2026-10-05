#!/usr/bin/env python3
"""
Main entry point for Companion4SoloPlayer.
"""

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon

from companion4soloplayer import APPLICATION_NAME, ORGANIZATION_NAME, __version__
from companion4soloplayer.app.application import CompanionApplication
from companion4soloplayer.ui.main_window import MainWindow
from companion4soloplayer.ui.splash_window import SPLASH_DURATION_MS, SplashScreen
from companion4soloplayer.utils.config_manager import ConfigManager
from companion4soloplayer.utils.logger import APP_LOGGER_NAME, setup_logging
from companion4soloplayer.utils.resource_manager import ResourceManager, ResourceNotFoundError


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

    # For better rendering on Windows / HiDPI
    app.setApplicationName(APPLICATION_NAME)
    app.setApplicationDisplayName(APPLICATION_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(ORGANIZATION_NAME)

    icon_path: Path | None
    try:
        icon_path = ResourceManager.instance().get_icon("icon.ico")
    except ResourceNotFoundError:
        icon_path = None

    if icon_path is not None:
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)

    window = MainWindow()

    QTimer.singleShot(SPLASH_DURATION_MS, window.show)

    exit_code = app.exec()
    # Every way of leaving the application goes through this point, so it is
    # the place for the last message of the session.
    logging.getLogger(APP_LOGGER_NAME).info("Application exiting with code %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
