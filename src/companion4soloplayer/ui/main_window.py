"""
Main window module.
Contains the primary application window.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from companion4soloplayer.core.plugin_loader import PluginLoader
from companion4soloplayer.ui.asset_utils import LOGO_PATH, resolve_asset_path
from companion4soloplayer.ui.dialogs.about_dialog import AboutDialog
from companion4soloplayer.ui.dialogs.plugins_dialog import PluginsDialog
from companion4soloplayer.ui.dialogs.quest_wizard import QuestWizard
from companion4soloplayer.ui.dialogs.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        """Initialize the main window."""
        super().__init__()
        self.setWindowTitle("Companion4SoloPlayer")
        self.setMinimumSize(1200, 800)
        self.setWindowIcon(QIcon(str(resolve_asset_path(LOGO_PATH))))

        self._plugin_loader = PluginLoader()
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_status_bar()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Header
        header = QLabel("Companion4SoloPlayer")
        header.setStyleSheet("font-size: 24px; font-weight: bold; padding: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Add tabs
        self._add_character_tab()
        self._add_quest_tab()
        self._add_dungeon_tab()

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        new_action = QAction("&New Game", self)
        new_action.setShortcut("Ctrl+N")
        file_menu.addAction(new_action)

        open_action = QAction("&Open Game", self)
        open_action.setShortcut("Ctrl+O")
        file_menu.addAction(open_action)

        close_action = QAction("&Close Game", self)
        close_action.setEnabled(False)
        file_menu.addAction(close_action)

        save_action = QAction("&Save Game", self)
        save_action.setEnabled(False)
        save_action.setShortcut("Ctrl+S")
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Manage menu
        manage_menu = menu_bar.addMenu("&Manage")

        plugin_action = QAction("&Plugins", self)
        plugin_action.triggered.connect(self._show_plugin)
        manage_menu.addAction(plugin_action)

        quest_action = QAction("&Quests", self)
        quest_action.triggered.connect(self._show_quest)
        manage_menu.addAction(quest_action)

        manage_menu.addSeparator()

        settings_action = QAction("&Settings", self)
        settings_action.triggered.connect(self._show_settings)
        manage_menu.addAction(settings_action)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        legal_action = QAction("&Legal Information", self)
        help_menu.addAction(legal_action)

    def _add_character_tab(self) -> None:
        """Add the character management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        label = QLabel("Character Management")
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)

        info = QLabel(
            "Manage your party of characters here.\n"
            "Create, edit, and track stats, inventory, and equipment."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

        self.tab_widget.addTab(tab, "Characters")

    def _add_quest_tab(self) -> None:
        """Add the quest management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        label = QLabel("Quest Management")
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)

        info = QLabel(
            "Track your current quest objectives here.\n"
            "Create custom quests or load community-made content."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

        self.tab_widget.addTab(tab, "Quests")

    def _add_dungeon_tab(self) -> None:
        """Add the dungeon generation tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        label = QLabel("Dungeon Generation")
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)

        info = QLabel(
            "Generate procedural dungeons or load existing ones.\n"
            "Visualize rooms, corridors, and encounters on a grid."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

        self.tab_widget.addTab(tab, "Dungeon")

    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _show_about(self) -> None:
        """Show the About dialog."""
        dialog = AboutDialog(self)
        dialog.exec()

    def _show_settings(self) -> None:
        """Show the Settings dialog."""
        dialog = SettingsDialog(self)
        dialog.exec()

    def _show_quest(self) -> None:
        """Show the Quest wizard."""
        dialog = QuestWizard(self)
        dialog.exec()

    def _show_plugin(self) -> None:
        """Show the Plugin dialog."""
        dialog = PluginsDialog(self, self._plugin_loader)
        dialog.exec()
