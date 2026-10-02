"""
Plugins dialog for Companion4SoloPlayer.

Replacement for the former Plugins tab of the main window: shows every
discovered game plugin in a scrollable multi-column table (metadata read
from each plugin's ``datas/plugin.yaml`` manifest) and lets the user
load/unload them dynamically. Opened from the Plugins entry of the
Manage menu.
"""

from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from companion4soloplayer.core.plugin_loader import MANIFEST_NAMES, PluginLoader
from companion4soloplayer.core.yaml_loader import YamlLoadError, YamlTagError, load_yaml_file
from companion4soloplayer.ui.dialogs.plugin_metadata_dialog import PluginMetadataDialog

# Column layout of the plugin table.
COLUMN_HEADERS = [
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
DESCRIPTION_COLUMN = 1
LOADED_COLUMN = 6
ACTION_COLUMN = 7
DETAILS_COLUMN = 8


def _format_compatible_games(value: Any) -> str:
    """Format the manifest ``compatible_games`` entry as comma-separated text.

    Args:
        value: Raw manifest value (list of game systems, plain string...).

    Returns:
        The comma-separated rendering, empty when the entry is absent.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ", ".join(str(game) for game in value)
    return ""


def _read_manifest(plugin_loader: PluginLoader, plugin_name: str) -> dict[str, Any]:
    """Read the ``plugin.yaml`` manifest of a discovered plugin.

    The manifest lives in the plugin data directory:
    ``<plugins_dir>/<name>_plugin/datas/plugin.yaml`` in development,
    or ``<plugins_dir>/<name>/datas/plugin.yaml`` for a frozen build.

    Args:
        plugin_loader: Loader providing the plugins directory.
        plugin_name: Canonical plugin name (e.g. ``demo``).

    Returns:
        The manifest fields, or an empty mapping when the manifest is
        missing or cannot be parsed (display-only fallback).
    """
    plugins_dir = plugin_loader.plugins_dir
    if not plugins_dir.is_dir():
        return {}
    for directory in plugins_dir.iterdir():
        if not directory.is_dir() or directory.name.removesuffix("_plugin") != plugin_name:
            continue
        for manifest_name in MANIFEST_NAMES:
            manifest_path = directory / manifest_name
            if manifest_path.is_file():
                try:
                    data = load_yaml_file(manifest_path)
                except (OSError, YamlLoadError, YamlTagError):
                    return {}
                return data if isinstance(data, dict) else {}
    return {}


def _eye_icon() -> QIcon:
    """Build the eye pictogram used by the metadata (details) buttons."""
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    outline = QPen(QColor("#555555"))
    outline.setWidthF(1.4)
    painter.setPen(outline)
    painter.setBrush(QBrush(QColor("#ffffff")))
    painter.drawEllipse(QRectF(1.5, 4.5, 15.0, 9.0))
    painter.setBrush(QBrush(QColor("#555555")))
    painter.drawEllipse(QRectF(6.0, 6.0, 6.0, 6.0))
    painter.end()
    return QIcon(pixmap)


class PluginsDialog(QDialog):
    """Plugins dialog: scrollable table of plugins with load controls."""

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
        self.setMinimumSize(900, 400)

        self._plugin_loader = plugin_loader if plugin_loader is not None else PluginLoader()
        self._plugin_rows: dict[str, tuple[QPushButton, QTableWidgetItem]] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the scrollable plugin table and the Close button."""
        layout = QVBoxLayout(self)

        label = QLabel("Plugins")
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)

        info = QLabel(
            "Manage game plugins here.\n" "Load a plugin on demand to make its content available."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Scrollable table: one row per discovered plugin with its
        # manifest metadata (name, description, version, license, author,
        # compatible games), load status and Load/Unload button. The rows
        # mirror the loader state, so a plugin loaded during a previous
        # dialog opening is still reported as loaded.
        plugin_names = self._plugin_loader.discover_plugins()
        self.table = QTableWidget(len(plugin_names), len(COLUMN_HEADERS))
        self.table.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        for column in range(len(COLUMN_HEADERS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(DESCRIPTION_COLUMN, QHeaderView.ResizeMode.Stretch)

        for row, plugin_name in enumerate(plugin_names):
            manifest = _read_manifest(self._plugin_loader, plugin_name)
            values = [
                str(manifest.get("name") or plugin_name),
                str(manifest.get("description") or ""),
                str(manifest.get("version") or ""),
                str(manifest.get("license") or ""),
                str(manifest.get("author") or ""),
                _format_compatible_games(manifest.get("compatible_games")),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

            loaded = self._plugin_loader.get_plugin(plugin_name) is not None
            loaded_item = QTableWidgetItem("Yes" if loaded else "No")
            self.table.setItem(row, LOADED_COLUMN, loaded_item)

            button = QPushButton("Unload" if loaded else "Load")
            button.clicked.connect(
                lambda checked=False, name=plugin_name: self._toggle_plugin(name)
            )
            self.table.setCellWidget(row, ACTION_COLUMN, button)

            # Eye button opening the metadata dialog of the plugin.
            eye_button = QPushButton()
            eye_button.setIcon(_eye_icon())
            eye_button.setToolTip("Show plugin metadata")
            eye_button.clicked.connect(
                lambda checked=False, name=plugin_name: self._show_metadata(name)
            )
            self.table.setCellWidget(row, DETAILS_COLUMN, eye_button)

            self._plugin_rows[plugin_name] = (button, loaded_item)

        layout.addWidget(self.table)

        # Close button centered below the table
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignHCenter)

    def _toggle_plugin(self, plugin_name: str) -> None:
        """Load or unload a plugin on demand from the plugin table."""
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
            self._set_loaded_state(plugin_name, True)
            self._report_status(f"Plugin '{plugin_name}' loaded")
        else:
            self._plugin_loader.unload_plugin(plugin_name)
            self._set_loaded_state(plugin_name, False)
            self._report_status(f"Plugin '{plugin_name}' unloaded")

    def _set_loaded_state(self, plugin_name: str, loaded: bool) -> None:
        """Refresh the Loaded cell and the action button of a plugin row."""
        button, loaded_item = self._plugin_rows[plugin_name]
        loaded_item.setText("Yes" if loaded else "No")
        button.setText("Unload" if loaded else "Load")

    def _show_metadata(self, plugin_name: str) -> None:
        """Show the metadata dialog of a plugin."""
        manifest = _read_manifest(self._plugin_loader, plugin_name)
        loaded = self._plugin_loader.get_plugin(plugin_name) is not None
        dialog = PluginMetadataDialog(manifest, loaded, self)
        dialog.exec()

    def _report_status(self, message: str) -> None:
        """Report an action in the parent window status bar when present."""
        parent = self.parent()
        if isinstance(parent, QMainWindow):
            parent.statusBar().showMessage(message)
