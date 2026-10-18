"""Auto-sizing tooltip displaying the description of a UI element.

The :class:`DescriptionTooltip` is a small frameless window shown while
the cursor hovers a widget or an item of a list. Its size and position
are computed **automatically** from the text to display:

- the **width** grows with the length of the description, clamped
  between a minimum and a maximum (the text then wraps on several
  lines), and never exceeds the width of the screen;
- the **height** follows the number of wrapped lines, capped at the
  height of the screen so the tooltip always fits;
- the **position** follows the mouse cursor: the tooltip is displayed
  next to it, a small offset away in x and y (see the ``offset``
  argument), flipping to the other side of the cursor when it would
  otherwise be cut off by the screen edges, then clamping inside the
  screen, so the tooltip is never displayed out of view.

The look (style sheet), the size bounds and the spacing are
constructor arguments, so the widget can evolve (another theme,
another size, another offset...) and be reused in any other context of
the application. Two helpers install it on the widgets of the player
creation dialog:

- :func:`install_widget_tooltip` shows the description of a whole
  widget (an attribute field, for instance);
- :func:`install_list_tooltips` shows the description of the hovered
  item of a choice list (race, class, skills, spells...), keyed by
  option name.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import ClassVar

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QCursor, QGuiApplication, QHoverEvent, QMouseEvent, QScreen
from PySide6.QtWidgets import QLabel, QListWidget, QVBoxLayout, QWidget

#: Style sheet applied to every description tooltip by default.
DEFAULT_STYLE_SHEET = """
DescriptionTooltip {
    background-color: #2b2b2b;
    color: #f5f5f5;
    border: 1px solid #555555;
    border-radius: 4px;
}
"""


class DescriptionTooltip(QWidget):
    """Frameless tooltip sized and positioned around its text.

    The tooltip is a top-level window flagged ``Qt.ToolTip``: it never
    takes the focus, it stays above the other windows and it ignores
    the mouse, so it never interferes with the widget being hovered.

    Args:
        min_width: Width (pixels) below which the tooltip never goes,
            whatever the text.
        max_width: Width (pixels) above which the text wraps instead of
            stretching the tooltip further.
        offset: Offset (pixels) kept between the mouse cursor and the
            tooltip, in x and y.
        padding: Inner padding (pixels) between the text and the
            border.
        style_sheet: Qt style sheet applied to the tooltip; the default
            one (:data:`DEFAULT_STYLE_SHEET`) draws a dark rounded
            panel.
    """

    #: Shared instance created by :meth:`shared`.
    _shared: ClassVar[DescriptionTooltip | None] = None

    def __init__(
        self,
        *,
        min_width: int = 160,
        max_width: int = 380,
        offset: int = 16,
        padding: int = 8,
        style_sheet: str = DEFAULT_STYLE_SHEET,
    ) -> None:
        """Initialize the tooltip window.

        Args:
            min_width: Minimum width in pixels.
            max_width: Maximum width in pixels before wrapping.
            offset: Offset in pixels between the cursor and the tooltip.
            padding: Inner padding in pixels.
            style_sheet: Qt style sheet of the tooltip.
        """
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self._min_width = max(1, min_width)
        self._max_width = max(self._min_width, max_width)
        self._offset = max(0, offset)
        self._padding = max(0, padding)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setStyleSheet(style_sheet)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(self._padding, self._padding, self._padding, self._padding)
        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        layout.addWidget(self._label)
        self.hide()

    @classmethod
    def shared(cls) -> DescriptionTooltip:
        """Return the tooltip shared by the whole application.

        Returns:
            The single ``DescriptionTooltip`` instance, created on
            first use.
        """
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    @property
    def text(self) -> str:
        """Return the text currently displayed by the tooltip."""
        return self._label.text()

    def show_description(self, text: str, cursor: QPoint | None = None) -> None:
        """Display ``text`` next to the mouse cursor, fully on screen.

        The size is recomputed from the text (see
        :meth:`_preferred_size`) and the position from the cursor (see
        :meth:`_position_for`): the tooltip sits a small offset away
        from the cursor in x and y, so a short description yields a
        compact tooltip while a long one wraps instead of leaving the
        screen.

        Args:
            text: Description to display; a blank text hides the
                tooltip instead.
            cursor: Cursor position in global coordinates, used as the
                reference of the placement; the current cursor position
                when None.
        """
        if not text.strip():
            self.hide_description()
            return
        if cursor is None:
            cursor = QCursor.pos()
        screen = self._screen_for(cursor)
        available = screen.availableGeometry() if screen is not None else None
        self._label.setText(text)
        self.setFixedSize(self._preferred_size(text, available))
        self.move(self._position_for(self.size(), cursor, available))
        self.show()
        self.raise_()

    def hide_description(self) -> None:
        """Hide the tooltip."""
        self.hide()

    def _preferred_size(self, text: str, available: QRect | None) -> QSize:
        """Return the size best suited to ``text``.

        The width is the longest line of the text plus the padding,
        clamped between the minimum and the maximum width (and never
        wider than the screen); the height is the height of the text
        wrapped at that width, capped at the screen height.

        Args:
            text: Description to measure.
            available: Available screen area (None to only use the
                configured bounds).

        Returns:
            The computed size of the tooltip.
        """
        metrics = self._label.fontMetrics()
        lines = text.splitlines() or [text]
        natural = max(metrics.horizontalAdvance(line) for line in lines) + 2 * self._padding
        max_width = self._max_width
        if available is not None and not available.isEmpty():
            max_width = min(max_width, available.width())
        width = max(self._min_width, min(natural, max_width))
        wrapped = metrics.boundingRect(
            QRect(0, 0, max(1, width - 2 * self._padding), 100000),
            Qt.TextFlag.TextWordWrap,
            text,
        )
        height = wrapped.height() + 2 * self._padding
        if available is not None and not available.isEmpty():
            height = min(height, available.height())
        return QSize(width, height)

    def _position_for(
        self,
        size: QSize,
        cursor: QPoint,
        available: QRect | None,
    ) -> QPoint:
        """Return the global position best displaying the tooltip.

        The reference of the placement is the cursor: the tooltip sits
        :attr:`_offset` pixels away from it, below and to the right. When
        that would cross the right (resp. bottom) edge of the screen it
        flips to the left (resp. above) of the cursor, and the final
        position is clamped inside the screen so the tooltip is never
        cut off.

        Args:
            size: Size the tooltip is about to take.
            cursor: Cursor position in global coordinates.
            available: Available screen area (None skips the clamping).

        Returns:
            The global position of the tooltip.
        """
        x = cursor.x() + self._offset
        y = cursor.y() + self._offset
        if available is None or available.isEmpty():
            return QPoint(x, y)
        if x + size.width() > available.right() + 1:
            x = cursor.x() - self._offset - size.width()
        if y + size.height() > available.bottom() + 1:
            y = cursor.y() - self._offset - size.height()
        x = max(available.left(), min(x, available.right() + 1 - size.width()))
        y = max(available.top(), min(y, available.bottom() + 1 - size.height()))
        return QPoint(x, y)

    @staticmethod
    def _screen_for(cursor: QPoint) -> QScreen | None:
        """Return the screen displaying the given position.

        Args:
            cursor: Position in global coordinates.

        Returns:
            The screen holding the position, the primary screen when
            the position lies on no screen, or None when no screen
            exists.
        """
        screen = QGuiApplication.screenAt(cursor)
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen


class DescriptionTooltipFilter(QObject):
    """Route the hover events of a widget to a description tooltip.

    The filter resolves the description to display through a callable
    (so a refreshed option list keeps matching tooltips), places the
    tooltip at the position of the mouse cursor and hides it when the
    cursor leaves or hovers an element without description.

    Args:
        tooltip: Tooltip receiving the descriptions.
        describe: Callable returning the description to display for
            the hovered position (in the coordinates of the watched
            object); an empty string hides the tooltip.
    """

    def __init__(
        self,
        tooltip: DescriptionTooltip,
        describe: Callable[[QObject, QPoint], str],
    ) -> None:
        """Initialize the filter.

        Args:
            tooltip: Tooltip receiving the descriptions.
            describe: Description resolver for a hovered position.
        """
        super().__init__(tooltip)
        self._tooltip = tooltip
        self._describe = describe

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Show or hide the tooltip according to the hover events.

        Args:
            watched: Widget or viewport the event belongs to.
            event: Delivered event.

        Returns:
            False: the event keeps its normal processing.
        """
        kind = event.type()
        if kind in (QEvent.Type.MouseMove, QEvent.Type.HoverMove) and isinstance(
            event, QMouseEvent | QHoverEvent
        ):
            position = event.position().toPoint()
            self._apply(watched, position)
        elif kind in (QEvent.Type.Enter, QEvent.Type.HoverEnter):
            self._apply(watched, QPoint())
        elif kind in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
            self._tooltip.hide_description()
        return False

    def _apply(self, watched: QObject, position: QPoint) -> None:
        """Show the description resolved for ``position``, or hide it.

        The tooltip is placed at the position of the mouse cursor, in
        global coordinates, plus the offset of the tooltip.

        Args:
            watched: Widget or viewport hovered.
            position: Cursor position in the coordinates of the watched
                object.
        """
        text = self._describe(watched, position)
        if not text:
            self._tooltip.hide_description()
            return
        if isinstance(watched, QWidget) and not position.isNull():
            cursor = watched.mapToGlobal(position)
        else:  # no position in the event: rely on the OS cursor
            cursor = QCursor.pos()
        self._tooltip.show_description(text, cursor)


def install_widget_tooltip(
    widget: QWidget,
    description: str | Callable[[], str],
    *,
    tooltip: DescriptionTooltip | None = None,
) -> DescriptionTooltipFilter:
    """Show a description while the cursor hovers the given widget.

    The tooltip appears next to the mouse cursor and hides again when
    the cursor leaves the widget. A callable description is resolved on
    every hover, so a value refreshed by the application (a help text
    recomputed with the state, for instance) is always the one
    displayed.

    Args:
        widget: Widget receiving the hover events.
        description: Help text, or callable returning it.
        tooltip: Tooltip to use; the shared one by default.

    Returns:
        The installed event filter (kept alive by the widget).
    """
    resolved = tooltip or DescriptionTooltip.shared()

    def describe(watched: QObject, _position: QPoint) -> str:
        """Return the description of the watched widget."""
        return description() if callable(description) else description

    tooltip_filter = DescriptionTooltipFilter(resolved, describe)
    widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    widget.setMouseTracking(True)
    widget.installEventFilter(tooltip_filter)
    return tooltip_filter


def install_list_tooltips(
    list_widget: QListWidget,
    descriptions: Mapping[str, str] | Callable[[], Mapping[str, str]],
    *,
    tooltip: DescriptionTooltip | None = None,
) -> DescriptionTooltipFilter:
    """Show the description of the hovered item of a choice list.

    Moving the cursor over an option shows its description (when the
    catalog declares one) next to the cursor; moving to another item
    refreshes the tooltip, and hovering an item without description (or
    leaving the list) hides it.

    Args:
        list_widget: List whose items get a tooltip.
        descriptions: Description per option name, or callable
            returning it (used when the option list is refreshed while
            the form is filled).
        tooltip: Tooltip to use; the shared one by default.

    Returns:
        The installed event filter (kept alive by the list).
    """
    resolved = tooltip or DescriptionTooltip.shared()
    target = list_widget
    viewport = list_widget.viewport()

    def _mapping() -> Mapping[str, str]:
        """Return the current description mapping."""
        return descriptions() if callable(descriptions) else descriptions

    def _local(watched: QObject, position: QPoint) -> QPoint:
        """Return the position in the coordinates of the list viewport."""
        if position.isNull():
            return viewport.mapFromGlobal(QCursor.pos())
        if watched is viewport or not isinstance(watched, QWidget):
            return position
        return viewport.mapFrom(watched, position)

    def describe(watched: QObject, position: QPoint) -> str:
        """Return the description of the hovered item."""
        item = target.itemAt(_local(watched, position))
        if item is None:
            return ""
        return _mapping().get(item.text(), "")

    tooltip_filter = DescriptionTooltipFilter(resolved, describe)
    for watched in (list_widget, viewport):
        watched.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        watched.setMouseTracking(True)
        watched.installEventFilter(tooltip_filter)
    return tooltip_filter
