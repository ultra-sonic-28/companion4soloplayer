"""
Settings dialog for Companion4SoloPlayer.
Allows users to configure application preferences.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    """Settings dialog for application preferences."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the settings dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 400)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the settings interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Application Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Appearance group
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark", "System"])
        appearance_layout.addRow("Theme:", self.theme_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(12)
        appearance_layout.addRow("Font size:", self.font_size_spin)

        layout.addWidget(appearance_group)

        # Gameplay group
        gameplay_group = QGroupBox("Gameplay")
        gameplay_layout = QVBoxLayout(gameplay_group)

        self.auto_save_check = QCheckBox("Enable auto-save")
        self.auto_save_check.setChecked(True)
        gameplay_layout.addWidget(self.auto_save_check)

        self.sound_check = QCheckBox("Enable sound effects")
        self.sound_check.setChecked(True)
        gameplay_layout.addWidget(self.sound_check)

        self.animations_check = QCheckBox("Enable animations")
        self.animations_check.setChecked(True)
        gameplay_layout.addWidget(self.animations_check)

        layout.addWidget(gameplay_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.accept)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def get_settings(self) -> dict:
        """Get the current settings.

        Returns:
            Dictionary containing settings
        """
        return {
            'theme': self.theme_combo.currentText(),
            'font_size': self.font_size_spin.value(),
            'auto_save': self.auto_save_check.isChecked(),
            'sound': self.sound_check.isChecked(),
            'animations': self.animations_check.isChecked()
        }
