"""
Plugins dialog for Companion4SoloPlayer.

Replacement for the former Plugins tab of the main window: lists the
discovered game plugins and lets the user load/unload them dynamically.
Opened from the Plugins entry of the Manage menu.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from companion4soloplayer.core.plugin_loader import PluginLoader


class PluginsDialog(QDialog):
    """Plugins dialog: one row per discovered plugin with load controls."""

    def __init__(
        self,
        parent: QWidget | None = None,
        plugin_loader: PluginLoader | None = None,
    ) -> None:
        """Initialize the plugins dialog.

        Args:
            parent: Parent widget
            plugin_loader: Loader shared with the main window so that
                plugins stay loaded across dialog openings. When omitted,
                the dialog works against a dedicated loader.
        """
        super().__init__(parent)
        self.setWindowTitle("Plugins")
        self.setMinimumSize(480, 300)

        self._plugin_loader = plugin_loader if plugin_loader is not None else PluginLoader()
        self._plugin_rows: dict[str, tuple[QPushButton, QLabel]] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the plugin list and the centered Close button."""
        layout = QVBoxLayout(self)

        label = QLabel("Plugins")
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)

        info = QLabel(
            "Manage game plugins here.\n" "Load a plugin on demand to make its content available."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # One row per discovered plugin with a Load/Unload button and a
        # status label showing the plugin version once loaded. The rows
        # mirror the loader state, so a plugin loaded during a previous
        # dialog opening is still reported as loaded.
        for plugin_name in self._plugin_loader.discover_plugins():
            loaded = self._plugin_loader.get_plugin(plugin_name)

            row = QHBoxLayout()
            name_label = QLabel(plugin_name)
            row.addWidget(name_label, stretch=1)

            status_label = QLabel(f"v{loaded.version} loaded" if loaded else "Not loaded")
            row.addWidget(status_label)

            button = QPushButton("Unload" if loaded else "Load")
            button.clicked.connect(
                lambda checked=False, name=plugin_name, btn=button, status=status_label: self._toggle_plugin(
                    name, btn, status
                )
            )
            row.addWidget(button)

            layout.addLayout(row)
            self._plugin_rows[plugin_name] = (button, status_label)

        layout.addStretch()

        # Close button centered below the list
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignHCenter)

    def _toggle_plugin(self, plugin_name: str, button: QPushButton, status_label: QLabel) -> None:
        """Load or unload a plugin on demand from the plugin list."""
        plugin = self._plugin_loader.get_plugin(plugin_name)
        if plugin is None:
            plugin = self._plugin_loader.load_plugin(plugin_name)
            if plugin is None:
                # Surface the underlying error: the released app has no
                # console, so prints from the loader are invisible.
                message = f"Failed to load plugin '{plugin_name}'."
                reason = self._plugin_loader.last_errors.get(plugin_name)
                if reason:
                    message = f"{message} {reason}"
                QMessageBox.warning(
                    self,
                    "Plugins",
                    message,
                )
                return
            status_label.setText(f"v{plugin.version} loaded")
            button.setText("Unload")
            self._report_status(f"Plugin '{plugin_name}' loaded")
        else:
            self._plugin_loader.unload_plugin(plugin_name)
            status_label.setText("Not loaded")
            button.setText("Load")
            self._report_status(f"Plugin '{plugin_name}' unloaded")

    def _report_status(self, message: str) -> None:
        """Report an action in the parent window status bar when present."""
        parent = self.parent()
        if isinstance(parent, QMainWindow):
            parent.statusBar().showMessage(message)
