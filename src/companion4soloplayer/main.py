#!/usr/bin/env python3
"""
Main entry point for Companion4SoloPlayer.
"""

import sys

from PySide6.QtWidgets import QApplication

from companion4soloplayer import __version__
from companion4soloplayer.ui.main_window import MainWindow


def main() -> None:
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("Companion4SoloPlayer")
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
