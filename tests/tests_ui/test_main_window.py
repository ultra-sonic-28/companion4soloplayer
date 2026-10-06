"""
Smoke tests for the Qt GUI.

Verifies that the application launches (main window shown) and exits
cleanly. More advanced interaction tests will be added later.
"""

import logging
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QAction, QIcon
from pytestqt.qtbot import QtBot

from companion4soloplayer import APPLICATION_NAME, ORGANIZATION_NAME, __version__
from companion4soloplayer import main as main_module
from companion4soloplayer.ui.main_window import MainWindow
from companion4soloplayer.utils.config_manager import ConfigManager
from companion4soloplayer.utils.logger import APP_LOGGER_NAME


class _StubApplication:
    """
    Minimal stand-in for CompanionApplication used to test the main() entry point.

    pytest-qt already owns the real QApplication singleton, and PySide6
    forbids creating a second one. Substituting the application class in
    the main module lets main() run its launch/exit flow against the
    existing event-loop-less test context.
    """

    def __init__(self, argv: list[str], config: ConfigManager | None = None) -> None:
        """Store the arguments, the configuration and default attributes."""
        self.argv = argv
        self.config = config
        self.application_name: str | None = None
        self.application_display_name: str | None = None
        self.application_version: str | None = None
        self.organization_name: str | None = None
        self.window_icon: QIcon | None = None

    def setApplicationName(self, name: str) -> None:  # noqa: N802
        """Record the application name (Qt naming convention kept)."""
        self.application_name = name

    def setApplicationDisplayName(self, name: str) -> None:  # noqa: N802
        """Record the application display name (Qt naming convention kept)."""
        self.application_display_name = name

    def setApplicationVersion(self, version: str) -> None:  # noqa: N802
        """Record the application version (Qt naming convention kept)."""
        self.application_version = version

    def setOrganizationName(self, name: str) -> None:  # noqa: N802
        """Record the organization name (Qt naming convention kept)."""
        self.organization_name = name

    def setWindowIcon(self, icon: QIcon) -> None:  # noqa: N802
        """Record the window icon (Qt naming convention kept)."""
        self.window_icon = icon

    def processEvents(self) -> None:  # noqa: N802
        """Flush pending events; a no-op is enough for the launch flow."""

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


def test_main_entry_point_launches_and_exits(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    The main() entry point starts the application and exits cleanly.

    The configuration is read first and drives the logging setup before the
    application class (QApplication subclass) is built: both receive the
    very same configuration instance. The application class is replaced by
    a stub because pytest-qt already created the real singleton, and the
    stub's exec() returns immediately, simulating a normal exit. Leaving
    the event loop must be logged before the process ends.
    """
    config = ConfigManager(tmp_path / "config.toml")
    created: list[_StubApplication] = []
    setup_calls: list[ConfigManager] = []

    def application_factory(
        argv: list[str], config: ConfigManager | None = None
    ) -> _StubApplication:
        """Build a stub application and keep track of it."""
        app = _StubApplication(argv, config)
        created.append(app)
        return app

    monkeypatch.setattr(main_module, "ConfigManager", lambda: config)
    monkeypatch.setattr(main_module, "setup_logging", setup_calls.append)
    monkeypatch.setattr(main_module, "CompanionApplication", application_factory)
    monkeypatch.setattr(sys, "exit", lambda code=0: (_ for _ in ()).throw(SystemExit(code)))

    with (
        caplog.at_level(logging.INFO, logger=APP_LOGGER_NAME),
        pytest.raises(SystemExit) as excinfo,
    ):
        main_module.main()

    # Normal exit code, application identity applied, window shown
    assert excinfo.value.code == 0
    assert len(created) == 1
    assert created[0].application_name == "Companion4SoloPlayer"
    assert created[0].application_display_name == APPLICATION_NAME
    assert created[0].application_version == __version__
    assert created[0].organization_name == ORGANIZATION_NAME
    assert created[0].window_icon is not None
    # Logging is configured from the configuration, as early as possible...
    assert setup_calls == [config]
    # ...and the application shares that same configuration.
    assert created[0].config is config
    # The session is closed with a logged message.
    assert "Application exiting with code 0" in caplog.text
