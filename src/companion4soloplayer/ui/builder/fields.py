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
:class:`ReadOnlyField` ``READONLY`` (value assigned by the game
                       system, saving throws...)
=====================  ==========================================

Every widget starts **empty**: the dialog never pre-fills an answer.
The read-only widget is the exception: it displays the value carried
by its field (``InputField.value``), refreshed by the dialog whenever
the state changes, and contributes no answer.

A widget emits :attr:`FieldWidget.changed` when the value edited by
the player changes, which lets the dialog re-evaluate the dependent
option lists (for example the spells filtered by the chosen class).

Hovering an element shows its help text in a
:class:`~companion4soloplayer.ui.widgets.tooltip.DescriptionTooltip`:
the whole widget for a field declaring ``InputField.description`` (an
attribute), and the hovered item of a choice list for the
``InputField.option_descriptions`` pairs (races, classes, skills,
spells...).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
from companion4soloplayer.ui.widgets.tooltip import (
    DescriptionTooltipFilter,
    install_list_tooltips,
    install_widget_tooltip,
)

#: Edge length (pixels) of the generated die icon.
DICE_ICON_SIZE = 24

#: Width reserved to the field labels inside a section.
LABEL_WIDTH = 160

#: Number of option rows a choice list must display without scrolling.
CHOICE_LIST_VISIBLE_ROWS = 4


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
            field: Field described by the creation step; its
                description, when declared, is shown while the cursor
                hovers the widget (see
                :func:`~companion4soloplayer.ui.widgets.tooltip.install_widget_tooltip`).
            parent: Owning widget.
        """
        super().__init__(parent)
        self._field = field
        self._description_tooltip: DescriptionTooltipFilter | None = None
        if field.description:
            self._description_tooltip = install_widget_tooltip(self, field.description)

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


class ReadOnlyField(FieldWidget):
    """Label and computed value the player cannot edit.

    Used by the blocks whose values the game system assigns itself
    (the saving throws granted by the chosen class, for instance): the
    dialog shows the effective value recomputed by the step after each
    change, and the widget collects no answer.
    """

    def __init__(self, field: InputField, parent: QWidget | None = None) -> None:
        """Initialize the read-only field.

        Args:
            field: Field described by the creation step; its
                ``value`` is displayed as-is.
            parent: Owning widget.
        """
        super().__init__(field, parent)
        self._value: int | str | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(field.label)
        self.label.setMinimumWidth(LABEL_WIDTH)
        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setMinimumWidth(40)
        self.value_label.setAccessibleName(field.label)
        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.value_label)
        self.set_value(field.value)

    @property
    def displayed_value(self) -> int | str | None:
        """Return the value currently displayed by the widget."""
        return self._value

    def value(self) -> int | str | None:
        """Return the displayed value.

        Returns:
            The computed value shown by the widget. The dialog skips
            read-only fields when it collects the answers, so this
            value is informational only.
        """
        return self._value

    def set_value(self, value: int | str | None) -> None:
        """Display a freshly computed value.

        Args:
            value: Value to display (None empties the widget).
        """
        if value == self._value:
            return
        self._value = value
        self.value_label.setText("" if value is None else str(value))


class ChoiceField(FieldWidget):
    """Labelled option list, single or multiple selection.

    The list keeps a fixed height showing at least
    :data:`CHOICE_LIST_VISIBLE_ROWS` rows (four), so a catalog of race,
    class, skills or spells is readable without scrolling inside the
    list; a shorter catalog simply leaves empty rows below.

    Hovering an option shows its description (when the field declares
    one, see ``InputField.option_descriptions``) in a
    :class:`~companion4soloplayer.ui.widgets.tooltip.DescriptionTooltip`
    next to the item; options without description show nothing.
    """

    def __init__(self, field: InputField, parent: QWidget | None = None) -> None:
        """Initialize the choice field.

        Args:
            field: Field described by the creation step; its kind
                selects the single or multiple selection mode.
            parent: Owning widget.
        """
        super().__init__(field, parent)
        self._options: tuple[str, ...] = ()
        self._option_descriptions: dict[str, str] = dict(field.option_descriptions)
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
        self._apply_list_height()
        self.list.itemSelectionChanged.connect(self.changed.emit)
        self._list_tooltip = install_list_tooltips(self.list, lambda: self._option_descriptions)

    @property
    def options(self) -> tuple[str, ...]:
        """Return the options currently listed by the widget."""
        return self._options

    @property
    def option_descriptions(self) -> dict[str, str]:
        """Return the description currently shown when hovering an option.

        Returns:
            The description of every described option, refreshed by
            :meth:`set_option_descriptions` when the dialog re-evaluates
            the form.
        """
        return dict(self._option_descriptions)

    def set_option_descriptions(
        self, option_descriptions: Sequence[tuple[str, str]] | Mapping[str, str]
    ) -> None:
        """Replace the description shown when an option is hovered.

        Args:
            option_descriptions: ``(option, description)`` pairs (or
                mapping) of the new descriptions.
        """
        self._option_descriptions = dict(option_descriptions)

    def _apply_list_height(self) -> None:
        """Give the list a fixed height of :data:`CHOICE_LIST_VISIBLE_ROWS` rows.

        The row height comes from the font metrics of the list, or
        from the first row when the list already holds options, so the
        four rows stay readable whatever the platform style.
        """
        row_height = self.list.fontMetrics().height() + 4
        if self.list.count() > 0:
            row_height = max(row_height, self.list.sizeHintForRow(0))
        border = 2 * self.list.frameWidth()
        self.list.setFixedHeight(row_height * CHOICE_LIST_VISIBLE_ROWS + border + 6)

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
        self._apply_list_height()

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
        InputKind.READONLY: ReadOnlyField,
    }.get(field.kind)
    if widget_class is None:
        raise ValueError(f"No widget implemented for input kind {field.kind!r}")
    return widget_class(field, parent)
