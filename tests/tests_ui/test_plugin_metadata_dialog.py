"""
Tests for the Plugin metadata dialog.
"""

from PySide6.QtWidgets import QLabel, QTextEdit
from pytestqt.qtbot import QtBot

from companion4soloplayer.ui.dialogs.plugin_metadata_dialog import PluginMetadataDialog

MANIFEST = {
    "name": "Demo Plugin",
    "version": "1.0.0",
    "description": "Plugin provided as a generic example",
    "author": "ultra-sonic-28",
    "license": "MIT",
    "compatible_games": ["Dungeon Crawler", "RolePlay"],
    "disclaimer": "No affiliation.",
    "features": "- Features\n\t- Core line",
    "dependencies": {"core_version": ">=0.1.0"},
}


def test_metadata_dialog_shows_manifest_values(qtbot: QtBot) -> None:
    """The dialog renders every manifest field."""
    dialog = PluginMetadataDialog(MANIFEST, loaded=False)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    assert dialog.windowTitle() == "Plugin metadata"

    labels = [label.text() for label in dialog.findChildren(QLabel) if label.text()]
    assert "Plugin metadata" in labels
    assert "Installed plugin details and runtime requirements" in labels
    assert "NAME" in labels
    assert "Demo Plugin" in labels
    assert "VERSION" in labels
    assert "1.0.0" in labels
    assert "AUTHOR" in labels
    assert "ultra-sonic-28" in labels
    assert "LICENSE" in labels
    assert "MIT" in labels
    assert "COMPATIBLES GAMES" in labels
    assert "Dungeon Crawler" in labels
    assert "RolePlay" in labels
    assert "DESCRIPTION" in labels
    assert "FEATURES" in labels
    assert "DISCLAIMER" in labels
    assert "DEPENDENCIES" in labels

    # The four text areas follow the section order and are read-only.
    edits = dialog.findChildren(QTextEdit)
    assert len(edits) == 4
    assert edits[0].toPlainText() == "Plugin provided as a generic example"
    assert edits[1].toPlainText() == "- Features\n\t- Core line"
    assert edits[2].toPlainText() == "No affiliation."
    assert edits[3].toPlainText() == "core_version: >=0.1.0"
    assert all(edit.isReadOnly() for edit in edits)

    assert dialog.close_button.text() == "✓ Close"


def test_metadata_dialog_loaded_badge(qtbot: QtBot) -> None:
    """The badge shows the pastel Loaded: Yes/No state."""
    not_loaded = PluginMetadataDialog(MANIFEST, loaded=False)
    qtbot.addWidget(not_loaded)
    badge_texts = [
        label.text() for label in not_loaded.loaded_badge.findChildren(QLabel) if label.text()
    ]
    assert badge_texts == ["Loaded: No"]
    assert "#fde2e2" in not_loaded.loaded_badge.styleSheet()

    loaded = PluginMetadataDialog(MANIFEST, loaded=True)
    qtbot.addWidget(loaded)
    badge_texts = [
        label.text() for label in loaded.loaded_badge.findChildren(QLabel) if label.text()
    ]
    assert badge_texts == ["Loaded: Yes"]
    assert "#d9f2e6" in loaded.loaded_badge.styleSheet()


def test_metadata_dialog_close_button_closes(qtbot: QtBot) -> None:
    """Clicking the footer button closes the dialog."""
    dialog = PluginMetadataDialog(MANIFEST, loaded=False)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    dialog.close_button.click()
    qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=5000)

    assert not dialog.isVisible()
