"""
Plugin metadata dialog for Companion4SoloPlayer.

Shows the contents of a plugin's ``plugin.yaml`` manifest: identity
(name/version), author and license, compatible games tags, description,
features, disclaimer and dependencies, plus a live "Loaded" badge.
Opened from the eye button on each row of the PluginsDialog table.
"""

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Small uppercase gray caption above every value.
_SECTION_STYLE = "QLabel { font-size: 11px; color: #8a8a8a; }"

# Plain black value text.
_VALUE_STYLE = "QLabel { color: #111111; font-size: 13px; }"

# Transparent container blocks (header, value blocks, tag rows).
_PLAIN_FRAME_STYLE = "QFrame { background-color: transparent; border: none; }"


def _mono_font(*, bold: bool = False) -> QFont:
    """Return the system fixed-width font, optionally bold.

    Args:
        bold: Whether the returned font should be bold.

    Returns:
        The monospace font.
    """
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setBold(bold)
    return font


def _text(manifest: Mapping[str, Any], key: str) -> str:
    """Return a manifest scalar as display text (empty when absent).

    Args:
        manifest: Parsed plugin.yaml contents.
        key: Manifest field name.

    Returns:
        The scalar rendered as text.
    """
    value = manifest.get(key)
    return "" if value is None else str(value)


def _dependencies_text(manifest: Mapping[str, Any]) -> str:
    """Render the dependencies mapping as one ``key: value`` line each.

    Args:
        manifest: Parsed plugin.yaml contents.

    Returns:
        The rendered dependency lines.
    """
    value = manifest.get("dependencies")
    if isinstance(value, Mapping):
        return "\n".join(f"{key}: {entry}" for key, entry in value.items())
    return "" if value is None else str(value)


class PluginMetadataDialog(QDialog):
    """Metadata dialog displaying the plugin.yaml contents of a plugin."""

    def __init__(
        self,
        manifest: Mapping[str, Any],
        loaded: bool,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the metadata dialog.

        Args:
            manifest: Parsed plugin.yaml contents.
            loaded: Whether the plugin is currently loaded.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Plugin metadata")
        self.setMinimumSize(860, 640)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")

        self._manifest = manifest
        self._loaded = loaded
        self.loaded_badge: QFrame

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the header, the metadata sections and the footer."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)

        layout.addWidget(self._build_header())

        # NAME / VERSION (70% / 30%), then AUTHOR / LICENSE.
        layout.addLayout(
            self._pair_row(
                self._value_block("NAME", _text(self._manifest, "name")),
                self._value_block(
                    "VERSION",
                    _text(self._manifest, "version"),
                    mono=True,
                    bold=True,
                    align_right=True,
                ),
            )
        )
        layout.addLayout(
            self._pair_row(
                self._value_block("AUTHOR", _text(self._manifest, "author"), mono=True),
                self._value_block(
                    "LICENSE",
                    _text(self._manifest, "license"),
                    bold=True,
                    align_right=True,
                ),
            )
        )

        # Compatible games as rounded bordered tags.
        layout.addWidget(self._section_label("COMPATIBLES GAMES"))
        layout.addWidget(self._build_games_tags())

        # Free-form text sections.
        layout.addWidget(self._section_label("DESCRIPTION"))
        layout.addWidget(self._build_text_edit(_text(self._manifest, "description")))

        layout.addWidget(self._section_label("FEATURES"))
        layout.addWidget(self._build_text_edit(_text(self._manifest, "features"), min_height=170))

        layout.addWidget(self._section_label("DISCLAIMER"))
        layout.addWidget(self._build_text_edit(_text(self._manifest, "disclaimer")))

        layout.addWidget(self._section_label("DEPENDENCIES"))
        layout.addWidget(self._build_text_edit(_dependencies_text(self._manifest), mono=True))

        layout.addStretch()

        # Footer: Close button on the right.
        footer = QHBoxLayout()
        footer.addStretch()
        self.close_button = QPushButton("✓ Close")
        self.close_button.clicked.connect(self.accept)
        footer.addWidget(self.close_button)
        layout.addLayout(footer)

    def _build_header(self) -> QFrame:
        """Build the title/subtitle block with the loaded badge on the right."""
        header = QFrame()
        header.setStyleSheet(_PLAIN_FRAME_STYLE)
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("Plugin metadata")
        title.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; color: #111111; }")
        subtitle = QLabel("Installed plugin details and runtime requirements")
        subtitle.setStyleSheet("QLabel { font-size: 12px; color: #6a6a6a; }")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        row.addLayout(titles)
        row.addStretch()
        row.addWidget(self._build_loaded_badge(), 0, Qt.AlignmentFlag.AlignVCenter)
        return header

    def _build_loaded_badge(self) -> QFrame:
        """Build the pastel Loaded: Yes/No badge with its status dot."""
        if self._loaded:
            background, dot, text = "#d9f2e6", "#1f9d55", "Loaded: Yes"
        else:
            background, dot, text = "#fde2e2", "#c83737", "Loaded: No"

        badge = QFrame()
        badge.setStyleSheet(f"""
            QFrame {{
                background-color: {background};
                border-radius: 10px;
            }}
            """)
        self.loaded_badge = badge

        row = QHBoxLayout(badge)
        row.setContentsMargins(12, 5, 12, 5)
        row.setSpacing(6)

        dot_label = QLabel()
        dot_label.setFixedSize(8, 8)
        dot_label.setStyleSheet(f"QLabel {{ background-color: {dot}; border-radius: 4px; }}")

        text_label = QLabel(text)
        text_label.setStyleSheet("QLabel { color: #333333; font-size: 12px; font-weight: 600; }")

        row.addWidget(dot_label, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(text_label, 0, Qt.AlignmentFlag.AlignVCenter)
        return badge

    def _section_label(self, text: str) -> QLabel:
        """Build a small uppercase gray section caption.

        Args:
            text: Caption text.

        Returns:
            The caption label.
        """
        label = QLabel(text)
        label.setStyleSheet(_SECTION_STYLE)
        return label

    def _value_block(
        self,
        caption: str,
        value: str,
        *,
        mono: bool = False,
        bold: bool = False,
        align_right: bool = False,
    ) -> QFrame:
        """Build a captioned value block (NAME/AUTHOR style).

        Args:
            caption: Uppercase gray caption.
            value: Value taken from the manifest.
            mono: Render the value in monospace font.
            bold: Render the value in bold font.
            align_right: Right-align caption and value.

        Returns:
            The block frame.
        """
        block = QFrame()
        block.setStyleSheet(_PLAIN_FRAME_STYLE)
        column = QVBoxLayout(block)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)

        label = QLabel(caption)
        label.setStyleSheet(_SECTION_STYLE)
        column.addWidget(label)

        text = QLabel(value)
        text.setStyleSheet(_VALUE_STYLE)
        text.setWordWrap(True)
        if mono:
            text.setFont(_mono_font(bold=bold))
        elif bold:
            font = text.font()
            font.setBold(True)
            text.setFont(font)
        if align_right:
            label.setAlignment(Qt.AlignmentFlag.AlignRight)
            text.setAlignment(Qt.AlignmentFlag.AlignRight)
        column.addWidget(text)
        return block

    @staticmethod
    def _pair_row(left: QFrame, right: QFrame) -> QHBoxLayout:
        """Build a 70/30 row holding two value blocks.

        Args:
            left: Block taking 70% of the width.
            right: Block taking 30% of the width.

        Returns:
            The horizontal layout.
        """
        row = QHBoxLayout()
        row.addWidget(left, 7)
        row.addWidget(right, 3)
        return row

    def _build_games_tags(self) -> QFrame:
        """Build the rounded bordered tags of the compatible games."""
        container = QFrame()
        container.setStyleSheet(_PLAIN_FRAME_STYLE)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        games = self._manifest.get("compatible_games")
        if isinstance(games, str):
            entries = [games]
        elif isinstance(games, list):
            entries = [str(game) for game in games]
        else:
            entries = []

        for game in entries:
            tag = QFrame()
            tag.setStyleSheet("""
                QFrame {
                    background-color: #f6f6f6;
                    border: 1px solid #a8a8a8;
                    border-radius: 9px;
                }
                """)
            tag_layout = QHBoxLayout(tag)
            tag_layout.setContentsMargins(10, 3, 10, 3)
            label = QLabel(game)
            label.setStyleSheet("QLabel { color: #444444; font-size: 12px; }")
            tag_layout.addWidget(label)
            row.addWidget(tag)

        row.addStretch()
        return container

    @staticmethod
    def _build_text_edit(value: str, *, mono: bool = False, min_height: int = 70) -> QTextEdit:
        """Build a read-only text area showing a manifest field.

        Args:
            value: Text content of the area.
            mono: Render the content in monospace font.
            min_height: Minimum height in pixels.

        Returns:
            The text area.
        """
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(value)
        text_edit.setMinimumHeight(min_height)
        text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #fcfcfc;
                border: 1px solid #d5d5d5;
                border-radius: 4px;
                padding: 4px;
            }
            """)
        if mono:
            text_edit.setFont(_mono_font())
        return text_edit
