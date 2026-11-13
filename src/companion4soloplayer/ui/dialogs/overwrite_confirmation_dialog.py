"""
Overwrite confirmation dialog for character saves.

Shows the user a side-by-side comparison of the old save values versus
the new values (date, plugin version, name, race, class) and asks
whether the existing save file should be overwritten.
"""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from companion4soloplayer.core.character_tracker import Character


class OverwriteConfirmationDialog(QDialog):
    """Dialog asking the user to confirm overwriting an existing save file.

    The left column shows the values currently stored in the save file
    (old values) and the right column shows the values the user wants to
    save instead (new values). The compared fields are: date, plugin
    version, name, race and class.

    Args:
        old_character: The character currently saved in the file.
        new_character: The character the user wants to save instead.
        old_saved_at: ISO-8601 timestamp of the existing save file.
        old_version: Plugin version stored in the existing save file.
        new_version: Plugin version of the currently running application.
        file_path: Path of the existing save file (shown for context).
        parent: Parent widget.
    """

    def __init__(
        self,
        *,
        old_character: Character,
        new_character: Character,
        old_saved_at: str,
        old_version: str,
        new_version: str,
        file_path: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm Overwrite")
        self.setMinimumWidth(500)

        self._old = old_character
        self._new = new_character
        self._old_saved_at = old_saved_at
        self._old_version = old_version
        self._new_version = new_version
        self._file_path = file_path

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the dialog layout: title, two-column comparison, buttons."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("A save file with the same name already exists.")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Context: file path
        path_label = QLabel(f"<b>File:</b> {self._file_path}")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        # Comparison table: label column, old column, new column
        grid = QGridLayout()

        old_header = QLabel("<b>Current values</b>")
        old_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        new_header = QLabel("<b>New values</b>")
        new_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(old_header, 0, 1)
        grid.addWidget(new_header, 0, 2)

        rows: list[tuple[str, str, str]] = [
            (
                "Date",
                self._format_date(self._old_saved_at),
                self._format_date(datetime.now(UTC)),
            ),
            (
                "Plugin version",
                self._old_version or "(unknown)",
                self._new_version or "(unknown)",
            ),
            ("Name", self._old.name, self._new.name),
            ("Race", self._old.race or "(none)", self._new.race or "(none)"),
            ("Class", self._old.character_class, self._new.character_class),
        ]

        for row_index, (label, old_value, new_value) in enumerate(rows, start=1):
            label_widget = QLabel(f"<b>{label}:</b>")
            label_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            old_widget = QLabel(old_value)
            old_widget.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            new_widget = QLabel(new_value)
            new_widget.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            grid.addWidget(label_widget, row_index, 0)
            grid.addWidget(old_widget, row_index, 1)
            grid.addWidget(new_widget, row_index, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 2)

        layout.addLayout(grid)

        # Buttons: Overwrite / Cancel
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = button_box.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setText("Overwrite")
        if cancel_button is not None:
            cancel_button.setText("Cancel")

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @staticmethod
    def _format_date(value: object) -> str:
        """Format a datetime value as a human-readable string.

        Args:
            value: A ``datetime`` instance or an ISO-8601 string.

        Returns:
            A readable date/time string, or ``"(none)"`` when the value
            is missing or unparseable.
        """
        if value is None:
            return "(none)"
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S UTC")
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
                return parsed.strftime("%Y-%m-%d %H:%M:%S UTC")
            except ValueError:
                return value
        return str(value)
