"""
Smoke tests for the Qt GUI.

Verifies that the application launches (main window shown) and exits
cleanly. More advanced interaction tests will be added later.
"""

import sys

import pytest
from PySide6.QtGui import QAction
from pytestqt.qtbot import QtBot

from companion4soloplayer import __version__
from companion4soloplayer import main as main_module
from companion4soloplayer.ui.main_window import MainWindow


class _StubApplication:
    """
    Minimal stand-in for QApplication used to test the main() entry point.

    pytest-qt already owns the real QApplication singleton, and PySide6
    forbids creating a second one. Substituting the QApplication symbol in
    the main module lets main() run its launch/exit flow against the
    existing event-loop-less test context.
    """

    def __init__(self, argv: list[str]) -> None:
        """Store the arguments and default attributes."""
        self.argv = argv
        self.application_name: str | None = None
        self.application_version: str | None = None

    def setApplicationName(self, name: str) -> None:  # noqa: N802
        """Record the application name (Qt naming convention kept)."""
        self.application_name = name

    def setApplicationVersion(self, version: str) -> None:  # noqa: N802
        """Record the application version (Qt naming convention kept)."""
        self.application_version = version

    def exec(self) -> int:
        """Return immediately, as if the event loop exited normally."""
        return 0


def test_main_window_launches(qtbot: QtBot) -> None:
    """The main window is created, shown and correctly initialized."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    assert window.isVisible()
    assert window.windowTitle() == "Companion4SoloPlayer"
    assert not window.windowIcon().isNull()
    # The three expected tabs are present: Characters, Quests, Dungeon
    assert window.tab_widget.count() == 3
    assert window.status_bar.currentMessage() == "Ready"


def test_main_window_closes_cleanly(qtbot: QtBot) -> None:
    """Closing the main window hides it without error (no deferred crash)."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    assert window.isVisible()

    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)

    assert not window.isVisible()


def test_exit_action_closes_application(qtbot: QtBot) -> None:
    """The File > Exit menu action closes the main window."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    # The Exit action was created with the window as parent, so it is
    # reachable among the window's child actions (Qt naming: "E&xit").
    exit_actions = [action for action in window.findChildren(QAction) if action.text() == "E&xit"]
    assert len(exit_actions) == 1

    exit_actions[0].trigger()
    assert not window.isVisible()


def test_main_entry_point_launches_and_exits(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The main() entry point starts the application and exits cleanly.

    QApplication is replaced by a stub because pytest-qt already created
    the real singleton. The stub's exec() returns immediately, simulating
    a normal application exit.
    """
    created: list[_StubApplication] = []

    def application_factory(argv: list[str]) -> _StubApplication:
        """Build a stub application and keep track of it."""
        app = _StubApplication(argv)
        created.append(app)
        return app

    monkeypatch.setattr(main_module, "QApplication", application_factory)
    monkeypatch.setattr(sys, "exit", lambda code=0: (_ for _ in ()).throw(SystemExit(code)))

    with pytest.raises(SystemExit) as excinfo:
        main_module.main()

    # Normal exit code, application name/version applied, window shown
    assert excinfo.value.code == 0
    assert len(created) == 1
    assert created[0].application_name == "Companion4SoloPlayer"
    assert created[0].application_version == __version__
