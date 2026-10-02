
"""
Pytest configuration for UI tests.

Forces Qt to use the "offscreen" platform plugin so the GUI tests run
headless and deterministically, even in CI environments without a display.
Must be set before PySide6 is imported by any test module.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

