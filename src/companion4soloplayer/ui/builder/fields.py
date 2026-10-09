"""Field widgets rendered by the dynamic player creation dialog.

Each widget edits exactly one
:class:`~companion4soloplayer.core.creation.inputs.InputField`:

=====================  ==========================================
Widget                 Field kind
=====================  ==========================================
:class:`TextField`     ``TEXT`` (player name...)
:class:`TextAreaField` ``TEXTAREA`` (background...)
:class:`NumberField`   ``NUMBER`` (manually assigned attribute)
:class:`DiceField`     ``DICE`` (attribute rolled with a die)
:class:`ChoiceField`   ``CHOICE`` / ``CHOICES`` (race, class,
                       skills, spells...)
=====================  ==========================================

Every widget starts **empty**: the dialog never pre-fills an answer.
A widget emits :attr:`FieldWidget.changed` when the value edited by
the player changes, which lets the dialog re-evaluate the dependent
option lists (for example the spells filtered by the chosen class).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QIntValidator, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from companion4soloplayer.core.creation.inputs import InputField, InputKind

#: Edge length (pixels) of the generated die icon.
DICE_ICON_SIZE = 24

#: Width reserved to the field labels inside a section.
LABEL_WIDTH = 160


def dice_icon(size: int = DICE_ICON_SIZE) -> QIcon:
    """Draw a six-sided die icon (no bundled asset required).

    The icon is a rounded square showing the five pips of the "5"
    face, drawn programmatically so the application ships no external
    asset for the die buttons.

    Args:
        size: Edge length of the square icon, in pixels.

    Returns:
        The generated icon.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin = max(1.0, size * 0.08)
        painter.setPen(QPen(QColor("#37474f"), max(1.0, size / 12)))
        painter.setBrush(QColor("#fafafa"))
        painter.drawRoundedRect(
            QRectF(margin, margin, size - 2 * margin, size - 2 * margin),
            size * 0.2,
            size * 0.2,
        )
        painter.setBrush(QColor("#37474f"))
        pip = size * 0.12
        half = size / 2
        spread = size * 0.26
        for x, y in (
            (half - spread, half - spread),
            (half + spread, half - spread),
            (half, half),
            (half - spread, half + spread),
            (half + spread, half + spread),
        ):
            painter.drawEllipse(QRectF(x - pip / 2, y - pip / 2, pip, pip))
    finally:
        painter.end()
    return QIcon(pixmap)


class FieldWidget(QWidget):
    """Base class of the widgets editing one :class:`InputField`.

    Subclasses must override :meth:`value`.

    Args:
        field: Field described by the creation step.
        parent: Owning widget.

    Signals:
        changed: Emitted when the value edited by the player changes.
    """

    changed = Signal()

    def __init__(self, field: InputField, parent: QWidget | None = None) -> None:
        """Initialize the widget.

        Args:
            field: Field described by the creation step.
            parent: Owning widget.
        """
        super().__init__(parent)
        self._field = field

    @property
    def field(self) -> InputField:
        """Return the field edited by this widget."""
        return self._field

    def _emit_changed(self, _text: str = "") -> None:
        """Emit :attr:`changed` (adapter for the ``textChanged`` signal).

        Args:
            _text: Text supplied by the Qt signal (ignored).
        """
        self.changed.emit()

    def value(self) -> Any:
        """Return the current answer, or None when nothing is filled.

        Returns:
            The value collected for the field key.

        Raises:
            NotImplementedError: In the base class; subclasses
                implement the value of their widget.
        """
        raise NotImplementedError("FieldWidget subclasses must implement value()")

    def set_options(self, options: Sequence[str]) -> None:
        """Update the option list of the widget.

        The default implementation ignores the update: only the choice
        widgets display options.

        Args:
            options: New option list.
        """


class TextField(FieldWidget):
    """Single-line text edit (player name, background...)."""

    def __init__(self, field: InputField, parent: QWidget | None = None) -> None:
        """Initialize the text field.

        Args:
            field: Field described by the creation step.
            parent: Owning widget.
        """
        super().__init__(field, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(field.label)
        self.label.setMinimumWidth(LABEL_WIDTH)
        self.edit = QLineEdit()
        self.edit.setAccessibleName(field.label)
        self.edit.setClearButtonEnabled(True)
        layout.addWidget(self.label)
        layout.addWidget(self.edit, stretch=1)
        self.edit.textChanged.connect(self._emit_changed)

    def value(self) -> str | None:
        """Return the trimmed text.

        Returns:
            The text of the edit, or None when it is blank.
        """
        text = self.edit.text().strip()
        return text or None


class TextAreaField(FieldWidget):
    """Multi-line text edit (long free-form answers: background...)."""

    def __init__(self, field: InputField, parent: QWidget | None = None) -> None:
        """Initialize the text area.

        Args:
            field: Field described by the creation step.
            parent: Owning widget.
        """
        super().__init__(field, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(field.label)
        layout.addWidget(self.label)
        self.edit = QPlainTextEdit()
        self.edit.setAccessibleName(field.label)
        self.edit.setFixedHeight(72)
        layout.addWidget(self.edit)
        self.edit.textChanged.connect(self._emit_changed)

    def value(self) -> str | None:
        """Return the trimmed text.

        Returns:
            The text of the area, or None when it is blank.
        """
        text = self.edit.toPlainText().strip()
        return text or None


class NumberField(FieldWidget):
    """Single-line numeric edit (manually assigned attribute)."""

    def __init__(self, field: InputField, parent: QWidget | None = None) -> None:
        """Initialize the numeric field.

        Args:
            field: Field described by the creation step.
            parent: Owning widget.
        """
        super().__init__(field, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(field.label)
        self.label.setMinimumWidth(LABEL_WIDTH)
        self.edit = QLineEdit()
        self.edit.setAccessibleName(field.label)
        lower = field.min_value if field.min_value is not None else -2_000_000_000
        upper = field.max_value if field.max_value is not None else 2_000_000_000
        self.edit.setValidator(QIntValidator(lower, upper, self.edit))
        layout.addWidget(self.label)
        layout.addWidget(self.edit, stretch=1)
        self.edit.textChanged.connect(self._emit_changed)

    def value(self) -> int | None:
        """Return the entered number.

        Returns:
            The parsed integer, or None when the edit is empty or does
            not hold a valid integer.
        """
        text = self.edit.text().strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None


class DiceField(FieldWidget):
    """Label, rolled value and die button (generated attribute).

    The die button is only active when the field declares a ``roll``
    callable, so a game system without dice never shows an active die.
    """

    def __init__(self, field: InputField, parent: QWidget | None = None) -> None:
        """Initialize the dice field.

        Args:
            field: Field described by the creation step.
            parent: Owning widget.
        """
        super().__init__(field, parent)
        self._value: int | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(field.label)
        self.label.setMinimumWidth(LABEL_WIDTH)
        self.value_label = QLabel("")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setMinimumWidth(40)
        self.die_button = QPushButton()
        self.die_button.setIcon(dice_icon())
        self.die_button.setIconSize(QSize(18, 18))
        self.die_button.setToolTip(f"Roll {field.label}")
        self.die_button.setAccessibleName(f"Roll {field.label}")
        self.die_button.setFixedSize(QSize(32, 28))
        self.die_button.setEnabled(field.roll is not None)
        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.value_label)
        layout.addWidget(self.die_button)

    def value(self) -> int | None:
        """Return the rolled value.

        Returns:
            The dice result, or None when the die was not rolled.
        """
        return self._value

    def set_rolled_value(self, value: int) -> None:
        """Store and display a rolled value.

        Args:
            value: Dice result to display.
        """
        self._value = int(value)
        self.value_label.setText(str(value))
        self.changed.emit()


class ChoiceField(FieldWidget):
    """Labelled option list, single or multiple selection."""

    def __init__(self, field: InputField, parent: QWidget | None = None) -> None:
        """Initialize the choice field.

        Args:
            field: Field described by the creation step; its kind
                selects the single or multiple selection mode.
            parent: Owning widget.
        """
        super().__init__(field, parent)
        self._options: tuple[str, ...] = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(field.label)
        layout.addWidget(self.label)
        self.list = QListWidget()
        self.list.setAccessibleName(field.label)
        mode = (
            QAbstractItemView.SelectionMode.SingleSelection
            if field.kind is InputKind.CHOICE
            else QAbstractItemView.SelectionMode.MultiSelection
        )
        self.list.setSelectionMode(mode)
        layout.addWidget(self.list)
        self.set_options(field.options)
        self.list.itemSelectionChanged.connect(self.changed.emit)

    @property
    def options(self) -> tuple[str, ...]:
        """Return the options currently listed by the widget."""
        return self._options

    def set_options(self, options: Sequence[str]) -> None:
        """Replace the option list, keeping the still-available picks.

        Args:
            options: New option list; a pick no longer offered is
                dropped from the selection.
        """
        new_options = tuple(options)
        if new_options == self._options:
            return
        selected = {item.text() for item in self.list.selectedItems()}
        self.list.blockSignals(True)
        self.list.clear()
        for option in new_options:
            item = QListWidgetItem(option)
            if option in selected:
                item.setSelected(True)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._options = new_options

    def value(self) -> str | list[str] | None:
        """Return the current selection.

        Returns:
            The picked option for a single-choice field (None when
            nothing is selected), or the list of picked options for a
            multiple-choice field (empty when nothing is selected).
        """
        selected = [item.text() for item in self.list.selectedItems()]
        if self._field.kind is InputKind.CHOICES:
            return selected
        return selected[0] if selected else None


def create_field_widget(field: InputField, parent: QWidget | None = None) -> FieldWidget:
    """Create the widget editing the given field.

    Args:
        field: Field described by a creation step.
        parent: Owning widget.

    Returns:
        The widget matching the kind of the field.

    Raises:
        ValueError: If the field kind has no widget implementation.
    """
    widget_class = {
        InputKind.TEXT: TextField,
        InputKind.TEXTAREA: TextAreaField,
        InputKind.NUMBER: NumberField,
        InputKind.DICE: DiceField,
        InputKind.CHOICE: ChoiceField,
        InputKind.CHOICES: ChoiceField,
    }.get(field.kind)
    if widget_class is None:
        raise ValueError(f"No widget implemented for input kind {field.kind!r}")
    return widget_class(field, parent)
