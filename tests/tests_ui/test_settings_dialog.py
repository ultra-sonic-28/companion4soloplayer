"""
Tests for the Settings dialog.

Focuses on the qt_material theme selection: the combo box lists the themes
shipped with Qt-Material, pre-selects the one stored in the configuration,
previews a new selection live through the ``theme_changed`` signal and
persists it in ``config.toml`` only when the dialog is saved.
"""

from pathlib import Path

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog
from pytestqt.qtbot import QtBot
from qt_material import list_themes  # type: ignore[import-untyped]

from companion4soloplayer.ui import main_window as main_window_module
from companion4soloplayer.ui.dialogs.settings_dialog import SettingsDialog
from companion4soloplayer.ui.main_window import MainWindow
from companion4soloplayer.utils.config_manager import ConfigManager


def _other_theme(current: str) -> str:
    """Return a qt_material theme name different from the one passed in."""
    return str(next(theme for theme in list_themes() if theme != current))


def _open_dialog(qtbot: QtBot, config: ConfigManager | None) -> SettingsDialog:
    """Create a dialog bound to the given configuration and track it."""
    dialog = SettingsDialog(config=config)
    qtbot.addWidget(dialog)
    return dialog


def _settings_actions(window: MainWindow) -> list[QAction]:
    """Return the Manage > Settings menu actions of a window."""
    return [action for action in window.findChildren(QAction) if action.text() == "&Settings"]


def test_theme_combo_lists_qt_material_themes(qtbot: QtBot, tmp_path: Path) -> None:
    """The combo box offers every theme returned by list_themes()."""
    dialog = _open_dialog(qtbot, ConfigManager(tmp_path / "config.toml"))

    texts = [dialog.theme_combo.itemText(i) for i in range(dialog.theme_combo.count())]

    assert texts == list_themes()


def test_theme_combo_selects_theme_from_config(qtbot: QtBot, tmp_path: Path) -> None:
    """The theme stored in config.toml is the selected entry."""
    path = tmp_path / "config.toml"
    config = ConfigManager(path)
    config.appearance()["theme"] = "dark_teal.xml"
    config.save()

    dialog = _open_dialog(qtbot, ConfigManager(path))

    assert dialog.theme_combo.currentText() == "dark_teal.xml"
    assert dialog.get_settings()["theme"] == "dark_teal.xml"


def test_theme_combo_defaults_to_light_blue(qtbot: QtBot, tmp_path: Path) -> None:
    """A file without [appearance] pre-selects the default theme."""
    path = tmp_path / "config.toml"
    path.write_text("[window]\nx = 1\n", encoding="utf-8")

    dialog = _open_dialog(qtbot, ConfigManager(path))

    assert dialog.theme_combo.currentText() == "light_blue.xml"


def test_theme_combo_without_configuration_uses_default(qtbot: QtBot) -> None:
    """Without any configuration the default theme is selected."""
    dialog = _open_dialog(qtbot, None)

    assert dialog.theme_combo.currentText() == "light_blue.xml"


def test_unknown_configured_theme_is_still_displayed(
    qtbot: QtBot, tmp_path: Path
) -> None:
    """A theme missing from list_themes() stays visible instead of being dropped."""
    config = ConfigManager(tmp_path / "config.toml")
    config.appearance()["theme"] = "removed_theme.xml"
    config.save()

    dialog = _open_dialog(qtbot, config)

    assert dialog.theme_combo.currentText() == "removed_theme.xml"
    assert dialog.theme_combo.count() == len(list_themes()) + 1


def test_selecting_a_theme_emits_theme_changed(qtbot: QtBot, tmp_path: Path) -> None:
    """Changing the combo box reports the new theme for a live preview."""
    dialog = _open_dialog(qtbot, ConfigManager(tmp_path / "config.toml"))
    chosen = _other_theme(dialog.theme_combo.currentText())

    with qtbot.waitSignal(dialog.theme_changed, timeout=1000) as blocker:
        dialog.theme_combo.setCurrentText(chosen)

    assert blocker.args == [chosen]


def test_saving_the_dialog_writes_the_theme_to_config(
    qtbot: QtBot, tmp_path: Path
) -> None:
    """Clicking Save stores the selected theme in config.toml."""
    path = tmp_path / "config.toml"
    config = ConfigManager(path)
    dialog = _open_dialog(qtbot, config)
    chosen = _other_theme(dialog.theme_combo.currentText())
    dialog.theme_combo.setCurrentText(chosen)

    dialog.save_button.click()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert ConfigManager(path).theme() == chosen


def test_cancelling_the_dialog_keeps_the_stored_theme(
    qtbot: QtBot, tmp_path: Path
) -> None:
    """Clicking Cancel leaves the theme of config.toml untouched."""
    path = tmp_path / "config.toml"
    config = ConfigManager(path)
    stored = config.theme()
    dialog = _open_dialog(qtbot, config)
    dialog.theme_combo.setCurrentText(_other_theme(stored))

    dialog.cancel_button.click()

    assert dialog.result() == QDialog.DialogCode.Rejected
    assert ConfigManager(path).theme() == stored


def test_settings_menu_applies_the_selected_theme_live(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Manage > Settings repaints the application and saves the new theme."""
    path = tmp_path / "config.toml"
    config = ConfigManager(path)
    window = MainWindow(config=config)
    qtbot.addWidget(window)

    applied: list[str] = []
    monkeypatch.setattr(
        main_window_module, "apply_stylesheet", lambda app, theme="": applied.append(theme)
    )

    chosen = _other_theme(config.theme())

    def save_from_dialog(dialog: SettingsDialog) -> bool:
        """Simulate the user picking a theme and clicking Save."""
        dialog.theme_combo.setCurrentText(chosen)
        dialog.accept()
        return True

    monkeypatch.setattr(SettingsDialog, "exec", save_from_dialog)

    actions = _settings_actions(window)
    assert len(actions) == 1
    actions[0].trigger()

    # Live preview as soon as the theme is picked, then the stored theme...
    assert applied[0] == chosen
    assert applied[-1] == chosen
    # ...and the choice persisted in config.toml.
    assert ConfigManager(path).theme() == chosen


def test_cancelling_settings_undoes_the_theme_preview(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A cancelled dialog restores the theme stored in the configuration."""
    path = tmp_path / "config.toml"
    config = ConfigManager(path)
    window = MainWindow(config=config)
    qtbot.addWidget(window)

    applied: list[str] = []
    monkeypatch.setattr(
        main_window_module, "apply_stylesheet", lambda app, theme="": applied.append(theme)
    )

    chosen = _other_theme(config.theme())

    def cancel_from_dialog(dialog: SettingsDialog) -> bool:
        """Simulate the user picking a theme and clicking Cancel."""
        dialog.theme_combo.setCurrentText(chosen)
        dialog.reject()
        return False

    monkeypatch.setattr(SettingsDialog, "exec", cancel_from_dialog)

    actions = _settings_actions(window)
    assert len(actions) == 1
    actions[0].trigger()

    # The preview is applied live, then undone with the stored theme...
    assert applied[0] == chosen
    assert applied[-1] == config.theme()
    # ...and the file was never rewritten.
    assert ConfigManager(path).theme() == config.theme()
