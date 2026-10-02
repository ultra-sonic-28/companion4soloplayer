
"""
Tests for the About dialog and its wiring in the main window.
"""

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from companion4soloplayer import __version__
from companion4soloplayer.ui.dialogs.about_dialog import (
    DESCRIPTION,
    LOGO_SIZE,
    AboutDialog,
)
from companion4soloplayer.ui.main_window import MainWindow


def test_about_dialog_shows(qtbot: QtBot) -> None:
    """The About dialog shows the logo and the four info lines."""
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    assert not dialog.windowIcon().isNull()

    texts = [label.text() for label in dialog.findChildren(QLabel) if label.text()]
    assert any("Companion4SoloPlayer" in text for text in texts)
    assert DESCRIPTION in texts
    assert any(
        text.startswith("<b>Version:</b>") and __version__ in text for text in texts
    )
    assert any(text.startswith("<b>Compiled at:</b>") for text in texts)

    pixmap = dialog.logo_label.pixmap()
    assert pixmap is not None
    assert pixmap.size().width() == LOGO_SIZE
    assert pixmap.size().height() == LOGO_SIZE

    # Close button present below the two columns
    assert dialog.close_button.text() == "Close"


def test_close_button_closes_dialog(qtbot: QtBot) -> None:
    """Clicking the centered Close button closes the dialog."""
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    dialog.close_button.click()
    qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=5000)

    assert not dialog.isVisible()


def test_about_action_opens_dialog(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Help > About menu action opens the About dialog."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    calls: list[int] = []
    monkeypatch.setattr(AboutDialog, "exec", lambda self: calls.append(1))

    about_actions = [
        action for action in window.findChildren(QAction) if action.text() == "&About"
    ]
    assert len(about_actions) == 1
    about_actions[0].trigger()

    assert calls == [1]
