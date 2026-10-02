"""
Quest creation wizard dialog.
Guides users through creating a new quest.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class QuestWizard(QDialog):
    """Wizard dialog for creating a new quest."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the quest wizard.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Create New Quest")
        self.setMinimumSize(600, 500)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the wizard interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Quest Creation Wizard")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Quest details group
        details_group = QGroupBox("Quest Details")
        details_layout = QFormLayout(details_group)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter quest name")
        details_layout.addRow("Name:", self.name_input)

        self.template_combo = QComboBox()
        self.template_combo.addItems([
            "Blank Quest",
            "Rescue Mission",
            "Boss Hunt",
            "Treasure Recovery",
            "Survival Challenge"
        ])
        details_layout.addRow("Template:", self.template_combo)

        layout.addWidget(details_group)

        # Description
        desc_group = QGroupBox("Description")
        desc_layout = QVBoxLayout(desc_group)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Enter quest description and objectives..."
        )
        desc_layout.addWidget(self.description_input)

        layout.addWidget(desc_group)

        # Parameters
        params_group = QGroupBox("Parameters")
        params_layout = QFormLayout(params_group)

        self.num_rooms_spin = QSpinBox()
        self.num_rooms_spin.setRange(5, 50)
        self.num_rooms_spin.setValue(10)
        params_layout.addRow("Number of rooms:", self.num_rooms_spin)

        self.difficulty_spin = QSpinBox()
        self.difficulty_spin.setRange(1, 10)
        self.difficulty_spin.setValue(1)
        params_layout.addRow("Difficulty level:", self.difficulty_spin)

        layout.addWidget(params_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.create_button = QPushButton("Create Quest")
        self.create_button.clicked.connect(self.accept)
        button_layout.addWidget(self.create_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def get_quest_data(self) -> dict:
        """Get the quest data entered by the user.

        Returns:
            Dictionary containing quest data
        """
        return {
            'name': self.name_input.text(),
            'template': self.template_combo.currentText(),
            'description': self.description_input.toPlainText(),
            'num_rooms': self.num_rooms_spin.value(),
            'difficulty': self.difficulty_spin.value()
        }
