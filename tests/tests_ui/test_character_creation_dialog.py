"""UI tests for the dynamic player creation dialog (Manage > Player).

The dialog is built from the creation pipeline of the demo plugin (the
step order declared by ``datas/workflow.yaml``): sections, field count
and widget kinds must match the workflow, every widget starts empty,
Validate runs the pipeline and Cancel discards everything.
"""

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QMessageBox
from pytestqt.qtbot import QtBot

from companion4soloplayer.core.creation import CharacterCreationPipeline, InputKind
from companion4soloplayer.core.creation.inputs import InputField
from companion4soloplayer.plugins.demo_plugin import Plugin
from companion4soloplayer.ui.builder import CharacterCreationDialog
from companion4soloplayer.ui.builder.fields import (
    ChoiceField,
    DiceField,
    FieldWidget,
    TextField,
)
from companion4soloplayer.ui.main_window import MainWindow

#: Attribute keys of the demo workflow, in declaration order.
ATTRIBUTE_KEYS: tuple[str, ...] = (
    "attributes.strength",
    "attributes.dexterity",
    "attributes.constitution",
    "attributes.intelligence",
    "attributes.wisdom",
    "attributes.charisma",
)


@pytest.fixture
def pipeline() -> CharacterCreationPipeline:
    """Return the creation pipeline assembled by the demo plugin."""
    return Plugin().create_character_creation()


def _rows(dialog: CharacterCreationDialog) -> dict[str, tuple[InputField, FieldWidget]]:
    """Index the rows of the dialog by answer key.

    Args:
        dialog: Dialog under test.

    Returns:
        The ``(field, widget)`` pair of every rendered row.
    """
    return {
        field.key: (field, widget) for section in dialog.sections for field, widget in section.rows
    }


def _select(choice: ChoiceField, label: str) -> None:
    """Select one option in a choice list.

    Args:
        choice: Choice widget to update.
        label: Option to select.
    """
    labels = [choice.list.item(row).text() for row in range(choice.list.count())]
    choice.list.item(labels.index(label)).setSelected(True)


def test_sections_follow_the_workflow_order(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """One section per workflow step, in the order of workflow.yaml."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)

    assert [section.step_id for section in dialog.sections] == [
        "identity",
        "race",
        "class",
        "attributes",
        "skills",
        "spells",
    ]
    assert [len(section.rows) for section in dialog.sections] == [2, 1, 1, 6, 1, 1]
    assert [section.box.title() for section in dialog.sections] == [
        section.step_id for section in dialog.sections
    ]
    assert dialog.windowTitle() == "Create Player"
    assert dialog.validate_button.text() == "Validate"
    assert dialog.cancel_button.text() == "Cancel"


def test_fields_match_the_declared_data_types(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """Text for the identity, dice for the attributes, lists for the choices."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)
    rows = _rows(dialog)

    name = rows["identity.name"][1]
    assert isinstance(name, TextField)
    background = rows["identity.background"][1]
    assert isinstance(background, TextField)

    race = rows["race"]
    assert race[0].kind is InputKind.CHOICE
    assert isinstance(race[1], ChoiceField)
    assert race[0].options == ("Human", "Dwarf", "Elf", "Gnome")
    assert rows["class"][0].options == (
        "Adventurer",
        "Scout",
        "Bruiser",
        "Scholar",
        "Wizard",
        "Archer",
    )

    for key in ATTRIBUTE_KEYS:
        field, widget = rows[key]
        assert field.kind is InputKind.DICE
        assert isinstance(widget, DiceField)
        assert widget.die_button.isEnabled()
        assert not widget.die_button.icon().isNull()

    skills = rows["skills"]
    assert skills[0].kind is InputKind.CHOICES
    assert isinstance(skills[1], ChoiceField)
    assert skills[0].min_count == 2
    assert skills[0].max_count == 4
    assert len(skills[0].options) == 10

    # The spell filter only lets the classless spells through at first.
    spells = rows["spells"]
    assert spells[0].kind is InputKind.CHOICES
    assert spells[0].options == ("Light",)


def test_dialog_starts_with_empty_information(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """No widget holds a value when the dialog is built."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)

    values = {key: widget.value() for key, (_field, widget) in _rows(dialog).items()}
    assert values["identity.name"] is None
    assert values["identity.background"] is None
    assert values["race"] is None
    assert values["class"] is None
    assert all(values[key] is None for key in ATTRIBUTE_KEYS)
    assert values["skills"] == []
    assert values["spells"] == []
    assert not dialog.error_label.isVisibleTo(dialog)


def test_die_button_rolls_and_records_the_value(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """Clicking the die rolls the strategy and stores the answer."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)

    field, dice = _rows(dialog)["attributes.strength"]
    assert isinstance(dice, DiceField)
    assert dice.value() is None
    assert dice.value_label.text() == ""

    dice.die_button.click()

    value = dice.value()
    assert value is not None
    assert 3 <= value <= 18
    assert dice.value_label.text() == str(value)
    assert dialog.answers["attributes.strength"] == value
    assert field.key == "attributes.strength"


def test_validate_displays_the_error_of_the_first_failed_step(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """Validate on an empty form keeps the dialog open and shows why."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    dialog.validate_button.click()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.report is None
    assert dialog.context is None
    assert dialog.error_label.isVisible()
    assert "identity.name" in dialog.error_label.text()


def test_validate_creates_the_character(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """A filled form runs the six workflow steps and yields a character."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)
    rows = _rows(dialog)

    name = rows["identity.name"][1]
    assert isinstance(name, TextField)
    name.edit.setText("Brom")

    race = rows["race"][1]
    assert isinstance(race, ChoiceField)
    _select(race, "Dwarf")

    character_class = rows["class"][1]
    assert isinstance(character_class, ChoiceField)
    _select(character_class, "Wizard")

    for key in ATTRIBUTE_KEYS:
        dice = rows[key][1]
        assert isinstance(dice, DiceField)
        dice.die_button.click()

    skills = rows["skills"][1]
    assert isinstance(skills, ChoiceField)
    _select(skills, "Athletics")
    _select(skills, "Medicine")

    spells = rows["spells"][1]
    assert isinstance(spells, ChoiceField)
    _select(spells, "Spark")

    dialog.validate_button.click()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.report is not None
    assert dialog.report.ok
    assert dialog.report.completed
    context = dialog.context
    assert context is not None
    assert context.peek("choices.identity.name") == "Brom"
    assert context.peek("choices.race") == "Dwarf"
    assert context.peek("choices.class") == "Wizard"
    assert context.peek("choices.skills") == ["Athletics", "Medicine"]
    assert context.peek("choices.spells") == ["Spark"]
    strength = context.get("values.attributes.strength")
    assert isinstance(strength, int)
    assert 3 <= strength <= 18
    # The Dwarf/Wizard rules fired during the run.
    assert "dwarf_hardy" in dialog.report.rules_fired
    assert "wizard_arcana" in dialog.report.rules_fired


def test_choice_lists_refresh_when_a_selection_changes(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """Picking a class re-evaluates the spell filter of the dialog."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)
    rows = _rows(dialog)

    spells = rows["spells"][1]
    assert isinstance(spells, ChoiceField)
    assert spells.options == ("Light",)

    character_class = rows["class"][1]
    assert isinstance(character_class, ChoiceField)
    _select(character_class, "Wizard")

    assert "Spark" in spells.options
    assert "Rune Ward" in spells.options  # granted Arcane Lore by the class
    assert "Fireball" not in spells.options  # level 2, not a starting spell

    _select(character_class, "Adventurer")
    assert spells.options == ("Light",)


def test_cancel_discards_the_dialog(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """Cancel rejects the dialog and keeps no report."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)
    rows = _rows(dialog)

    name = rows["identity.name"][1]
    assert isinstance(name, TextField)
    name.edit.setText("Brom")

    dialog.cancel_button.click()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.report is None
    assert dialog.context is None


def test_manage_player_menu_sits_above_plugins(qtbot: QtBot) -> None:
    """Manage > Player is the first entry, right above Plugins."""
    window = MainWindow()
    qtbot.addWidget(window)

    manage = next(
        action for action in window.menuBar().actions() if action.text() == "&Manage"
    ).menu()
    assert manage is not None
    texts = [action.text() for action in manage.actions()]
    assert texts[:2] == ["&Player", "&Plugins"]


def test_player_menu_action_opens_the_dialog(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Player action loads the first plugin and opens the dialog."""
    window = MainWindow()
    qtbot.addWidget(window)

    calls: list[int] = []

    def fake_exec(self: CharacterCreationDialog) -> int:
        """Record the call and close the dialog immediately."""
        calls.append(1)
        return 0

    monkeypatch.setattr(CharacterCreationDialog, "exec", fake_exec)

    player_actions = [
        action for action in window.findChildren(QAction) if action.text() == "&Player"
    ]
    assert len(player_actions) == 1
    player_actions[0].trigger()

    assert calls == [1]
    assert window.status_bar.currentMessage() == "Plugin 'demo' loaded"


def test_player_menu_reports_when_no_plugin_is_available(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without any plugin the action explains what to do first."""
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window._plugin_loader, "discover_plugins", lambda: [])

    captured: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: captured.append(str(args[1])),
    )

    window._show_player()

    assert captured == ["Player"]
