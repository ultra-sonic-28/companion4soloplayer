"""
Tests for the Plugins dialog (replacement of the former Plugins tab).
"""

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QPushButton
from pytestqt.qtbot import QtBot

from companion4soloplayer.core.plugin_loader import PluginLoader
from companion4soloplayer.ui.dialogs.plugin_metadata_dialog import PluginMetadataDialog
from companion4soloplayer.ui.dialogs.plugins_dialog import DETAILS_COLUMN, PluginsDialog
from companion4soloplayer.ui.main_window import MainWindow


def _cell_text(dialog: PluginsDialog, row: int, column: int) -> str:
    """Return the text of a table cell."""
    item = dialog.table.item(row, column)
    assert item is not None
    return item.text()


def _header_texts(dialog: PluginsDialog) -> list[str]:
    """Return the column header labels of the plugin table."""
    texts: list[str] = []
    for column in range(dialog.table.columnCount()):
        header_item = dialog.table.horizontalHeaderItem(column)
        assert header_item is not None
        texts.append(header_item.text())
    return texts


def test_plugins_dialog_lists_plugins(qtbot: QtBot) -> None:
    """The table shows each plugin with its manifest metadata."""
    dialog = PluginsDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    assert _header_texts(dialog) == [
        "Name",
        "Description",
        "Version",
        "License",
        "Author",
        "Compatible Games",
        "Loaded",
        "Action",
        "Details",
    ]

    plugin_names = dialog._plugin_loader.discover_plugins()
    assert plugin_names
    assert dialog.table.rowCount() == len(plugin_names)

    texts = [label.text() for label in dialog.findChildren(QLabel) if label.text()]
    assert "Plugins" in texts

    # Manifest metadata of the demo plugin (plugins/demo_plugin/datas/plugin.yaml).
    button, loaded_item = dialog._plugin_rows["demo"]
    row = loaded_item.row()
    assert _cell_text(dialog, row, 0) == "Demo Plugin"
    assert _cell_text(dialog, row, 1) == "Plugin provided as a generic example"
    assert _cell_text(dialog, row, 2) == "1.0.0"
    assert _cell_text(dialog, row, 3) == "MIT"
    assert _cell_text(dialog, row, 4) == "ultra-sonic-28"
    assert _cell_text(dialog, row, 5) == "None or All :)"
    assert _cell_text(dialog, row, 6) == "No"
    assert button.text() == "Load"

    assert dialog.close_button.text() == "Close"


def test_plugins_dialog_loads_and_unloads(qtbot: QtBot) -> None:
    """Clicking Load loads the plugin dynamically; Unload reverses it."""
    dialog = PluginsDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    plugin_name = dialog._plugin_loader.discover_plugins()[0]
    button, loaded_item = dialog._plugin_rows[plugin_name]

    button.click()
    assert button.text() == "Unload"
    assert loaded_item.text() == "Yes"
    assert dialog._plugin_loader.get_plugin(plugin_name) is not None

    button.click()
    assert button.text() == "Load"
    assert loaded_item.text() == "No"
    assert dialog._plugin_loader.get_plugin(plugin_name) is None


def test_plugins_dialog_reflects_already_loaded_plugin(qtbot: QtBot) -> None:
    """A plugin loaded before the dialog opens is shown as loaded."""
    loader = PluginLoader()
    plugin_name = loader.discover_plugins()[0]
    assert loader.load_plugin(plugin_name) is not None

    dialog = PluginsDialog(plugin_loader=loader)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    button, loaded_item = dialog._plugin_rows[plugin_name]
    assert button.text() == "Unload"
    assert loaded_item.text() == "Yes"

    assert loader.unload_plugin(plugin_name)


def test_plugins_dialog_reports_status_in_parent_window(qtbot: QtBot) -> None:
    """Toggling a plugin reports the action in the parent status bar."""
    window = MainWindow()
    qtbot.addWidget(window)

    dialog = PluginsDialog(window, window._plugin_loader)
    plugin_name = dialog._plugin_loader.discover_plugins()[0]

    button, _loaded_item = dialog._plugin_rows[plugin_name]

    button.click()
    assert window.status_bar.currentMessage() == f"Plugin '{plugin_name}' loaded"

    button.click()
    assert window.status_bar.currentMessage() == f"Plugin '{plugin_name}' unloaded"


def test_plugins_action_opens_dialog(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    """The Manage > Plugins menu action opens the Plugins dialog."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    calls: list[int] = []
    monkeypatch.setattr(PluginsDialog, "exec", lambda self: calls.append(1))

    plugin_actions = [
        action for action in window.findChildren(QAction) if action.text() == "&Plugins"
    ]
    assert len(plugin_actions) == 1
    plugin_actions[0].trigger()

    assert calls == [1]


def test_plugins_dialog_eye_button_opens_metadata(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The eye button of a row opens the plugin metadata dialog."""
    dialog = PluginsDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    row = dialog._plugin_rows["demo"][1].row()
    eye_button = dialog.table.cellWidget(row, DETAILS_COLUMN)
    assert isinstance(eye_button, QPushButton)
    assert not eye_button.icon().isNull()

    captured: list[PluginMetadataDialog] = []
    monkeypatch.setattr(PluginMetadataDialog, "exec", lambda self: captured.append(self))
    eye_button.click()

    assert len(captured) == 1
    labels = [label.text() for label in captured[0].findChildren(QLabel) if label.text()]
    assert "Demo Plugin" in labels
    assert "Loaded: No" in labels
