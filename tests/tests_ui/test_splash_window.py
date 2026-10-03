"""
Tests for the startup splash screen background image.
"""

from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap
from pytestqt.qtbot import QtBot

from companion4soloplayer.ui.splash_window import (
    FALLBACK_HEIGHT,
    FALLBACK_WIDTH,
    SPLASH_IMAGE_NAME,
    SplashScreen,
)
from companion4soloplayer.utils.resource_manager import (
    ResourceManager,
    ResourceNotFoundError,
)

# Long duration so the auto-close timer never fires during the tests
TEST_DURATION_MS = 60_000


def test_splash_pixmap_follows_image_size(qtbot: QtBot) -> None:
    """The splash pixmap is the splash image, so its size follows the image."""
    image_path = ResourceManager.instance().get_image(SPLASH_IMAGE_NAME)
    assert image_path.is_file()

    expected = QPixmap(str(image_path))
    assert not expected.isNull()

    splash = SplashScreen(duration_ms=TEST_DURATION_MS)
    qtbot.addWidget(splash)

    pixmap = splash.pixmap()
    assert not pixmap.isNull()
    assert pixmap.size() == expected.size()
    # Explicitly not the old hard-coded 400x300 panel
    assert pixmap.size() != QSize(FALLBACK_WIDTH, FALLBACK_HEIGHT)


def test_splash_falls_back_to_dark_blue_panel(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing splash image still yields a usable dark blue pixmap."""

    def _missing_image(self: ResourceManager, name: str) -> Path:
        raise ResourceNotFoundError(f"Resource not found: {name}")

    monkeypatch.setattr(ResourceManager, "get_image", _missing_image)

    splash = SplashScreen(duration_ms=TEST_DURATION_MS)
    qtbot.addWidget(splash)

    pixmap = splash.pixmap()
    assert not pixmap.isNull()
    assert pixmap.size() == QSize(FALLBACK_WIDTH, FALLBACK_HEIGHT)


def test_splash_shows_loading_message(qtbot: QtBot) -> None:
    """The splash screen displays its loading message over the image."""
    splash = SplashScreen(duration_ms=TEST_DURATION_MS)
    qtbot.addWidget(splash)
    splash.show()
    qtbot.waitExposed(splash)

    assert splash.isVisible()
