"""UI tests for the reusable description tooltip widget.

The :class:`~companion4soloplayer.ui.widgets.tooltip.DescriptionTooltip`
computes its own size (width clamped between the configured bounds, text
wrapping, height fitting the screen) and its own position (following the
mouse cursor with an offset, flipping near the screen edges so it is never
cut off), is installed on the widgets and choice lists of the creation
dialog, and takes its default style from the ``[tooltip]`` table of the
user configuration.
"""

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QListWidget, QWidget
from pytestqt.qtbot import QtBot

from companion4soloplayer.ui.widgets.tooltip import (
    DescriptionTooltip,
    build_style_sheet,
    configured_style_sheet,
    install_list_tooltips,
    install_widget_tooltip,
)
from companion4soloplayer.utils.config_manager import ConfigManager, TooltipCornerType

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


def test_build_style_sheet_round_corners_uses_the_radius() -> None:
    """``round`` applies the configured radius to the corners."""
    sheet = build_style_sheet("#ffffff", "#000000", "#3b3a98", 2, 5, "round")

    assert "background-color: #ffffff;" in sheet
    assert "color: #000000;" in sheet
    assert "border: 2px solid #3b3a98;" in sheet
    assert "border-radius: 5px;" in sheet


def test_build_style_sheet_square_corners_ignore_the_radius() -> None:
    """``square`` keeps right angles, whatever the radius."""
    sheet = build_style_sheet(
        "#101010",
        "#eeeeee",
        "#ff0000",
        4,
        10,
        TooltipCornerType.SQUARE,
    )

    assert "border: 4px solid #ff0000;" in sheet
    assert "border-radius: 0px;" in sheet


def test_configured_style_sheet_reads_the_tooltip_table(tmp_path: Path) -> None:
    """The style sheet is built from the [tooltip] configuration."""
    path = tmp_path / "config.toml"
    config = ConfigManager(path)
    settings = config.tooltip()
    settings["background_color"] = "#101010"
    settings["text_color"] = "#eeeeee"
    settings["border_color"] = "#ff0000"
    settings["border_size"] = 4
    settings["border_radius"] = 10
    settings["corner_type"] = "square"
    config.save()

    sheet = configured_style_sheet(ConfigManager(path))

    assert "background-color: #101010;" in sheet
    assert "color: #eeeeee;" in sheet
    assert "border: 4px solid #ff0000;" in sheet
    # square corners: the radius is not applied.
    assert "border-radius: 0px;" in sheet


def test_configured_style_sheet_falls_back_on_the_defaults(tmp_path: Path) -> None:
    """A file without [tooltip] yields the documented default style."""
    path = tmp_path / "config.toml"
    path.write_text("[window]\nx = 10\n", encoding="utf-8")

    sheet = configured_style_sheet(ConfigManager(path))

    assert "background-color: #ffffff;" in sheet
    assert "color: #000000;" in sheet
    assert "border: 2px solid #3b3a98;" in sheet
    assert "border-radius: 5px;" in sheet


def test_tooltip_takes_the_configured_style_by_default() -> None:
    """A tooltip without explicit style sheet applies the config one."""
    tooltip = DescriptionTooltip()

    sheet = tooltip.styleSheet()
    assert "QFrame#tooltipFrame" in sheet
    assert "background-color:" in sheet
    assert "border:" in sheet


def test_tooltip_accepts_an_explicit_style_sheet() -> None:
    """An explicit style sheet still overrides the configured default."""
    custom = "DescriptionTooltip { background-color: #123456; }"
    tooltip = DescriptionTooltip(style_sheet=custom)

    assert tooltip.styleSheet() == custom


def test_tooltip_applies_config_edits_on_next_display(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editing the [tooltip] table applies on the next hover display.

    The shared tooltip must not freeze the style sheet built at
    construction: a value written to ``config.toml`` while the
    application is running is re-read the next time the tooltip pops up.
    """
    from companion4soloplayer.utils import config_manager as config_manager_module

    path = tmp_path / "config.toml"
    config = ConfigManager(path)
    config.tooltip()["background_color"] = "#00ff00"
    config.save()
    monkeypatch.setattr(config_manager_module, "default_config_path", lambda: path)

    tooltip = DescriptionTooltip()
    qtbot.addWidget(tooltip)
    assert "#00ff00" in tooltip.styleSheet()

    # The user edits the file while the application keeps running.
    editor = ConfigManager(path)
    editor.tooltip()["background_color"] = "#0000ff"
    editor.save()

    tooltip.hide_description()
    tooltip.show_description(SHORT_TEXT, QPoint(10, 10))

    assert "#0000ff" in tooltip.styleSheet()


def test_explicit_style_sheet_is_never_overwritten_by_the_config(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A style sheet given at construction survives the config reloads."""
    from companion4soloplayer.utils import config_manager as config_manager_module

    path = tmp_path / "config.toml"
    ConfigManager(path)
    monkeypatch.setattr(config_manager_module, "default_config_path", lambda: path)

    custom = "DescriptionTooltip { background-color: #123456; }"
    tooltip = DescriptionTooltip(style_sheet=custom)
    qtbot.addWidget(tooltip)

    tooltip.hide_description()
    tooltip.show_description(SHORT_TEXT, QPoint(10, 10))

    assert tooltip.styleSheet() == custom
