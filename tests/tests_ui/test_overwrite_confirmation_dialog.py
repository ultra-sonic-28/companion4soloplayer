"""
Unit tests for the Overwrite confirmation dialog.

Covers the side-by-side plugin version comparison (old version read from
the existing save file versus new version of the running plugin) and the
Overwrite / Cancel user interaction.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QLabel
from pytestqt.qtbot import QtBot

from companion4soloplayer.core.character_tracker import Character, CharacterTracker
from companion4soloplayer.ui.dialogs.overwrite_confirmation_dialog import (
    OverwriteConfirmationDialog,
)

OLD_VERSION = "1.0.0"
NEW_VERSION = "2.0.0"


def _make_character(name: str, character_class: str) -> Character:
    tracker = CharacterTracker()
    return tracker.create_character(name, character_class, {"body": 10})


def _grid(dialog: OverwriteConfirmationDialog) -> QGridLayout:
    """Return the comparison grid layout held by the dialog."""
    layout = dialog.layout()
    assert layout is not None
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is not None:
            child_layout = item.layout()
            if isinstance(child_layout, QGridLayout):
                return child_layout
    raise AssertionError("comparison grid layout not found")


def _cell_text(grid: QGridLayout, row: int, column: int) -> str:
    item = grid.itemAtPosition(row, column)
    assert item is not None, f"no cell at row {row}, column {column}"
    widget = item.widget()
    assert isinstance(widget, QLabel)
    return widget.text()


def test_dialog_shows_plugin_version_side_by_side(qtbot: QtBot) -> None:
    """The Version row shows the old version on the left and the new
    version on the right."""
    dialog = OverwriteConfirmationDialog(
        old_character=_make_character("Aragorn", "Ranger"),
        new_character=_make_character("Aragorn", "Warrior"),
        old_saved_at="2026-01-15T10:30:00+00:00",
        old_version=OLD_VERSION,
        new_version=NEW_VERSION,
        file_path="/data/saves/demo_plugin/aragorn.yaml",
    )
    qtbot.addWidget(dialog)

    grid = _grid(dialog)
    # Row 1 is Date, row 2 is Plugin version.
    assert _cell_text(grid, 2, 0) == "<b>Plugin version:</b>"
    assert _cell_text(grid, 2, 1) == OLD_VERSION
    assert _cell_text(grid, 2, 2) == NEW_VERSION


def test_dialog_uses_unknown_when_versions_missing(qtbot: QtBot) -> None:
    """Missing version values fall back on ``(unknown)``."""
    dialog = OverwriteConfirmationDialog(
        old_character=_make_character("Aragorn", "Ranger"),
        new_character=_make_character("Aragorn", "Warrior"),
        old_saved_at="2026-01-15T10:30:00+00:00",
        old_version="",
        new_version="",
        file_path="/data/saves/demo_plugin/aragorn.yaml",
    )
    qtbot.addWidget(dialog)

    grid = _grid(dialog)
    assert _cell_text(grid, 2, 1) == "(unknown)"
    assert _cell_text(grid, 2, 2) == "(unknown)"


def test_overwrite_button_accepts_dialog(qtbot: QtBot) -> None:
    """Clicking Overwrite accepts the dialog."""
    dialog = OverwriteConfirmationDialog(
        old_character=_make_character("Aragorn", "Ranger"),
        new_character=_make_character("Aragorn", "Warrior"),
        old_saved_at="2026-01-15T10:30:00+00:00",
        old_version=OLD_VERSION,
        new_version=NEW_VERSION,
        file_path="/data/saves/demo_plugin/aragorn.yaml",
    )
    qtbot.addWidget(dialog)

    button_box = dialog.findChild(QDialogButtonBox)
    assert button_box is not None
    save_button = button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save_button is not None
    save_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_cancel_button_rejects_dialog(qtbot: QtBot) -> None:
    """Clicking Cancel rejects the dialog."""
    dialog = OverwriteConfirmationDialog(
        old_character=_make_character("Aragorn", "Ranger"),
        new_character=_make_character("Aragorn", "Warrior"),
        old_saved_at="2026-01-15T10:30:00+00:00",
        old_version=OLD_VERSION,
        new_version=NEW_VERSION,
        file_path="/data/saves/demo_plugin/aragorn.yaml",
    )
    qtbot.addWidget(dialog)

    button_box = dialog.findChild(QDialogButtonBox)
    assert button_box is not None
    cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
    assert cancel_button is not None
    cancel_button.click()
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_dialog_contains_expected_comparison_rows(qtbot: QtBot) -> None:
    """The comparison grid contains Date, Plugin version, Name, Race,
    Class rows."""
    dialog = OverwriteConfirmationDialog(
        old_character=_make_character("Aragorn", "Ranger"),
        new_character=_make_character("Aragorn", "Warrior"),
        old_saved_at="2026-01-15T10:30:00+00:00",
        old_version=OLD_VERSION,
        new_version=NEW_VERSION,
        file_path="/data/saves/demo_plugin/aragorn.yaml",
    )
    qtbot.addWidget(dialog)

    grid = _grid(dialog)
    expected_labels = [
        "<b>Date:</b>",
        "<b>Plugin version:</b>",
        "<b>Name:</b>",
        "<b>Race:</b>",
        "<b>Class:</b>",
    ]
    actual_labels = [
        _cell_text(grid, row, 0) for row in range(1, grid.rowCount())
    ]
    assert actual_labels == expected_labels
