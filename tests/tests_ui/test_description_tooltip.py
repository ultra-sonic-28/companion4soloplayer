"""UI tests for the reusable description tooltip widget.

The :class:`~companion4soloplayer.ui.widgets.tooltip.DescriptionTooltip`
computes its own size (width clamped between the configured bounds, text
wrapping, height fitting the screen) and its own position (next to the
anchor, flipping near the screen edges so it is never cut off), and is
installed on the widgets and choice lists of the creation dialog.
"""

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QListWidget, QWidget
from pytestqt.qtbot import QtBot

from companion4soloplayer.ui.widgets.tooltip import (
    DescriptionTooltip,
    install_list_tooltips,
    install_widget_tooltip,
)

#: Description short enough to fit on a single line.
SHORT_TEXT = "Raw muscle."

#: Description long enough to wrap over several lines.
LONG_TEXT = (
    "Strength measures the muscle and physical power of your character, "
    "including hand-to-hand combat, athletics and feats that rely on raw "
    "brawn. It governs the damage dealt with melee weapons and it is the "
    "driving force behind many physical actions during an adventure."
)


def _mouse_move(widget: QWidget, position: QPoint) -> None:
    """Send a mouse move event to the given widget.

    Args:
        widget: Receiver of the event.
        position: Cursor position in the coordinates of the widget.
    """
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(position),
        QPointF(widget.mapToGlobal(position)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)


def test_short_description_yields_a_compact_tooltip(qtbot: QtBot) -> None:
    """A short description stays between the minimum and maximum width."""
    tooltip = DescriptionTooltip(min_width=160, max_width=380)
    qtbot.addWidget(tooltip)
    tooltip.show_description(SHORT_TEXT, QPoint(10, 10))

    size = tooltip.size()
    assert 160 <= size.width() <= 380
    assert size.height() > 0
    assert tooltip.isVisible()
    assert tooltip.text == SHORT_TEXT


def test_long_description_wraps_instead_of_stretching(qtbot: QtBot) -> None:
    """A long description wraps at the maximum width, growing in height."""
    tooltip = DescriptionTooltip(min_width=160, max_width=380)
    qtbot.addWidget(tooltip)
    tooltip.show_description(LONG_TEXT, QPoint(10, 10))
    long_size = tooltip.size()

    tooltip.show_description(SHORT_TEXT, QPoint(10, 10))
    short_size = tooltip.size()

    # The width never crosses the maximum, while the wrapped text makes
    # the tooltip taller than the single-line one.
    assert long_size.width() <= 380
    assert long_size.height() > short_size.height()


def test_tooltip_follows_the_cursor_with_an_offset(qtbot: QtBot) -> None:
    """The tooltip sits a small offset away from the cursor, in x and y."""
    offset = 16
    tooltip = DescriptionTooltip(offset=offset)
    qtbot.addWidget(tooltip)
    screen = QApplication.primaryScreen()
    assert screen is not None
    # A cursor position in the middle of the screen: no edge to avoid.
    cursor = screen.availableGeometry().center()

    tooltip.show_description(SHORT_TEXT, cursor)

    geometry = tooltip.geometry()
    assert geometry.topLeft() == cursor + QPoint(offset, offset)


def test_tooltip_is_never_cut_off_by_the_screen_edges(qtbot: QtBot) -> None:
    """Whatever the cursor position, the tooltip stays inside the screen."""
    tooltip = DescriptionTooltip(min_width=160, max_width=380)
    qtbot.addWidget(tooltip)
    screen = QApplication.primaryScreen()
    assert screen is not None
    available = screen.availableGeometry()

    for cursor in (
        available.topLeft(),
        available.bottomRight() - QPoint(80, 20),
        available.center(),
    ):
        tooltip.show_description(LONG_TEXT, cursor)
        geometry = tooltip.geometry()
        assert available.contains(geometry), f"{geometry} outside {available}"


def test_blank_description_hides_the_tooltip(qtbot: QtBot) -> None:
    """Displaying a blank text hides the tooltip instead."""
    tooltip = DescriptionTooltip()
    qtbot.addWidget(tooltip)
    tooltip.show_description(SHORT_TEXT, QPoint(10, 10))
    assert tooltip.isVisible()

    tooltip.show_description("   ", QPoint(10, 10))
    assert not tooltip.isVisible()


def test_shared_tooltip_is_unique() -> None:
    """The application relies on one shared tooltip instance."""
    assert DescriptionTooltip.shared() is DescriptionTooltip.shared()


def test_widget_tooltip_follows_the_hover(qtbot: QtBot) -> None:
    """Hovering a widget shows its description; leaving hides it."""
    tooltip = DescriptionTooltip()
    qtbot.addWidget(tooltip)
    widget = QWidget()
    qtbot.addWidget(widget)
    widget.resize(120, 40)
    widget.show()
    install_widget_tooltip(widget, SHORT_TEXT, tooltip=tooltip)

    _mouse_move(widget, QPoint(10, 10))
    assert tooltip.isVisible()
    assert tooltip.text == SHORT_TEXT

    QApplication.sendEvent(widget, QEvent(QEvent.Type.Leave))
    assert not tooltip.isVisible()


def test_widget_tooltip_without_description_stays_hidden(qtbot: QtBot) -> None:
    """Hovering a widget declaring no description shows nothing."""
    tooltip = DescriptionTooltip()
    qtbot.addWidget(tooltip)
    widget = QWidget()
    qtbot.addWidget(widget)
    widget.resize(120, 40)
    widget.show()
    install_widget_tooltip(widget, "", tooltip=tooltip)

    _mouse_move(widget, QPoint(10, 10))
    assert not tooltip.isVisible()


def test_list_tooltips_show_the_hovered_item_description(qtbot: QtBot) -> None:
    """Hovering a list item shows its description, keyed by option."""
    tooltip = DescriptionTooltip()
    qtbot.addWidget(tooltip)
    list_widget = QListWidget()
    qtbot.addWidget(list_widget)
    for option in ("Dwarf", "Elf", "Human"):
        list_widget.addItem(option)
    list_widget.resize(160, 120)
    list_widget.show()
    install_list_tooltips(
        list_widget,
        {"Dwarf": "Stout mountain folk.", "Elf": "Graceful woodland folk."},
        tooltip=tooltip,
    )

    viewport = list_widget.viewport()
    _mouse_move(viewport, list_widget.visualItemRect(list_widget.item(0)).center())
    assert tooltip.isVisible()
    assert tooltip.text == "Stout mountain folk."

    # Moving to another described item refreshes the tooltip.
    _mouse_move(viewport, list_widget.visualItemRect(list_widget.item(1)).center())
    assert tooltip.text == "Graceful woodland folk."

    # An item without description hides it.
    _mouse_move(viewport, list_widget.visualItemRect(list_widget.item(2)).center())
    assert not tooltip.isVisible()
