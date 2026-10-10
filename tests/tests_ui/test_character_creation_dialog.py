"""UI tests for the dynamic player creation dialog (Manage > Player).

The dialog is built from the creation pipeline of the demo plugin (the
step order declared by ``datas/workflow.yaml``): sections, field count
and widget kinds must match the workflow, every widget starts empty,
the shape of the form follows the answers (empty skill list at first,
spells block appearing only for a spellcasting race/class), Validate
runs the pipeline and Cancel discards everything.
"""

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QGridLayout, QMessageBox, QWidget
from pytestqt.qtbot import QtBot

from companion4soloplayer.core.creation import (
    CharacterCreationPipeline,
    InputKind,
    build_workflow,
    load_creation_rules,
)
from companion4soloplayer.core.creation.inputs import InputField
from companion4soloplayer.plugins.demo_plugin import Plugin
from companion4soloplayer.plugins.demo_plugin.creation import build_system
from companion4soloplayer.plugins.demo_plugin.data import DATA_DIR, load_data
from companion4soloplayer.ui.builder import CharacterCreationDialog
from companion4soloplayer.ui.builder.fields import (
    CHOICE_LIST_VISIBLE_ROWS,
    ChoiceField,
    DiceField,
    FieldWidget,
    TextAreaField,
    TextField,
)
from companion4soloplayer.ui.dialogs.plugins_dialog import PluginsDialog
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


def _grid_containing(widget: QWidget) -> QGridLayout:
    """Return the grid layout of the dialog holding ``widget``.

    Args:
        widget: Widget placed in the grid.

    Returns:
        The enclosing grid layout.
    """
    for layout in widget.window().findChildren(QGridLayout):
        if layout.indexOf(widget) != -1:
            return layout
    raise AssertionError(f"No grid layout holds {widget!r}")


def test_sections_follow_the_workflow_order(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """One section per workflow step describing data, in workflow order.

    At start the spells step describes nothing (no spellcasting
    race/class chosen yet), so only five sections are rendered.
    """
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)

    assert [section.step_id for section in dialog.sections] == [
        "identity",
        "race",
        "class",
        "attributes",
        "skills",
    ]
    assert [len(section.rows) for section in dialog.sections] == [2, 1, 1, 6, 1]
    assert [section.box.title() for section in dialog.sections] == [
        section.step_id for section in dialog.sections
    ]
    assert all(not section.box.isHidden() for section in dialog.sections)
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
    assert isinstance(background, TextAreaField)
    assert background.field.kind is InputKind.TEXTAREA

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
    # No race/class chosen yet: the skills block is shown with an empty list.
    assert skills[0].options == ()
    assert skills[1].options == ()

    # No spellcasting race/class chosen yet: no spells block at all.
    assert "spells" not in rows


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
    assert "spells" not in values  # no spells block at first
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

    background = rows["identity.background"][1]
    assert isinstance(background, TextAreaField)
    background.edit.setPlainText("Orphaned smith\nof the far north")

    race = rows["race"][1]
    assert isinstance(race, ChoiceField)
    _select(race, "Dwarf")

    # Choosing a race opens the skill catalog.
    skills = _rows(dialog)["skills"][1]
    assert isinstance(skills, ChoiceField)
    assert len(skills.options) == 10

    character_class = _rows(dialog)["class"][1]
    assert isinstance(character_class, ChoiceField)
    _select(character_class, "Wizard")

    for key in ATTRIBUTE_KEYS:
        dice = rows[key][1]
        assert isinstance(dice, DiceField)
        dice.die_button.click()

    rows = _rows(dialog)  # the Wizard class materialized the spells block
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
    assert context.peek("choices.identity.background") == "Orphaned smith\nof the far north"
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


def test_choice_lists_and_blocks_follow_the_selections(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """Selections open the skill catalog and show or hide the spells."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)

    # At start the skills list is empty and no spells block exists.
    skills = _rows(dialog)["skills"][1]
    assert isinstance(skills, ChoiceField)
    assert skills.options == ()
    assert "spells" not in _rows(dialog)

    # A race opens the skill catalog; a non-casting race adds no spells.
    race = _rows(dialog)["race"][1]
    assert isinstance(race, ChoiceField)
    _select(race, "Dwarf")
    assert len(skills.options) == 10
    assert "spells" not in _rows(dialog)

    # A spellcasting class materializes the spells block, filtered.
    character_class = _rows(dialog)["class"][1]
    assert isinstance(character_class, ChoiceField)
    _select(character_class, "Wizard")
    spells = _rows(dialog)["spells"][1]
    assert isinstance(spells, ChoiceField)
    assert {"Light", "Spark", "Mend"} <= set(spells.options)
    assert "Rune Ward" in spells.options  # granted Arcane Lore by the class
    assert "Fireball" not in spells.options  # level 2, not a starting spell

    # Switching to a non-casting class hides the block again.
    _select(character_class, "Adventurer")
    spells_section = {section.step_id: section for section in dialog.sections}["spells"]
    assert spells_section.box.isHidden()


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

    background = rows["identity.background"][1]
    assert isinstance(background, TextAreaField)
    background.edit.setPlainText("A background")

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


def test_player_menu_is_greyed_out_until_a_plugin_is_loaded(qtbot: QtBot) -> None:
    """Manage > Player is disabled while no plugin is loaded."""
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._player_action.isEnabled() is False


def test_player_menu_follows_the_plugin_load_state(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loading a plugin enables Player; unloading greys it out again."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert window._player_action.isEnabled() is False

    # Simulate the user toggling the plugin from the dialog opened by
    # Manage > Plugins (the window wires that dialog to the Player
    # entry): the first opening loads the plugin, the next unloads it.
    plugin_name = window._plugin_loader.discover_plugins()[0]
    monkeypatch.setattr(
        PluginsDialog,
        "exec",
        lambda self: self._toggle_plugin(plugin_name),
    )

    window._show_plugin()
    assert window._player_action.isEnabled() is True

    window._show_plugin()
    assert window._player_action.isEnabled() is False


def test_player_menu_refreshes_when_the_manage_menu_opens(qtbot: QtBot) -> None:
    """Opening Manage re-checks the state, whatever loaded the plugin."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert window._player_action.isEnabled() is False

    # A plugin loaded outside of the dialogs still lights the entry up
    # as soon as the user opens the Manage menu.
    window._plugin_loader.load_plugin("demo")
    manage = next(
        action for action in window.menuBar().actions() if action.text() == "&Manage"
    ).menu()
    assert manage is not None
    manage.aboutToShow.emit()

    assert window._player_action.isEnabled() is True


def test_player_menu_action_opens_the_dialog(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Player action opens the dialog of the loaded plugin."""
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

    # Without a loaded plugin the entry is greyed out and inert.
    assert player_actions[0].isEnabled() is False
    player_actions[0].trigger()
    assert calls == []

    # Loading a plugin through Manage > Plugins makes it available.
    plugin_name = window._plugin_loader.discover_plugins()[0]
    monkeypatch.setattr(
        PluginsDialog,
        "exec",
        lambda self: self._toggle_plugin(plugin_name),
    )
    window._show_plugin()
    assert player_actions[0].isEnabled() is True

    player_actions[0].trigger()

    assert calls == [1]


def test_player_menu_reports_when_no_plugin_is_available(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without any plugin the action explains what to do first."""
    window = MainWindow()
    qtbot.addWidget(window)

    captured: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: captured.append(str(args[1])),
    )

    window._show_player()

    assert captured == ["Player"]
    assert window._player_action.isEnabled() is False


def test_sections_are_arranged_on_two_columns(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """Multi-field sections span the row; single-field ones pair up."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)
    sections = {section.step_id: section for section in dialog.sections}
    grid = _grid_containing(sections["identity"].box)

    def cell_of(step_id: str) -> tuple[int, int, int]:
        """Return the (row, column, column span) of a section."""
        box = sections[step_id].box
        row, column, _row_span, column_span = grid.getItemPosition(grid.indexOf(box))
        return row, column, column_span

    # identity takes the first row; race and class share the second.
    assert cell_of("identity") == (0, 0, 2)
    assert cell_of("race") == (1, 0, 1)
    assert cell_of("class") == (1, 1, 1)
    # attributes takes the third row; skills alone on the fourth (the
    # spells block is not rendered without a spellcasting choice).
    assert cell_of("attributes") == (2, 0, 2)
    assert cell_of("skills") == (3, 0, 1)
    assert "spells" not in sections

    # The identity block keeps its own single-column stack.
    assert not isinstance(sections["identity"].box.layout(), QGridLayout)

    # A spellcasting class pairs the spells block next to the skills.
    character_class = sections["class"].rows[0][1]
    assert isinstance(character_class, ChoiceField)
    _select(character_class, "Wizard")
    sections = {section.step_id: section for section in dialog.sections}
    assert cell_of("spells") == (3, 1, 1)


def test_attributes_block_spreads_over_two_equal_columns(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """The six attributes are split 3/3 over the two columns."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)
    attributes = {s.step_id: s for s in dialog.sections}["attributes"].box
    layout = attributes.layout()
    assert isinstance(layout, QGridLayout)

    def label_at(row: int, column: int) -> str:
        """Return the attribute label shown at a grid cell."""
        item = layout.itemAtPosition(row, column)
        assert item is not None
        widget = item.widget()
        assert isinstance(widget, DiceField)
        return widget.label.text()

    assert label_at(0, 0) == "strength"
    assert label_at(1, 0) == "dexterity"
    assert label_at(2, 0) == "constitution"
    assert label_at(0, 1) == "intelligence"
    assert label_at(1, 1) == "wisdom"
    assert label_at(2, 1) == "charisma"
    # Equal distribution: no third row.
    assert layout.itemAtPosition(3, 0) is None
    assert layout.itemAtPosition(3, 1) is None


def test_dialog_minimum_size(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """The dialog is at least 860 x 640 pixels."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)

    # setMinimumSize pins the floor; the content may ask for more.
    minimum = dialog.minimumSize()
    assert minimum.width() >= 860
    assert minimum.height() >= 640


def test_choice_lists_show_at_least_four_rows(
    qtbot: QtBot,
    pipeline: CharacterCreationPipeline,
) -> None:
    """Race, class, skills and spells lists fit at least 4 options."""
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)
    character_class = _rows(dialog)["class"][1]
    assert isinstance(character_class, ChoiceField)
    _select(character_class, "Wizard")

    for key in ("race", "class", "skills", "spells"):
        choice = _rows(dialog)[key][1]
        assert isinstance(choice, ChoiceField)
        row_height = choice.list.fontMetrics().height()
        # setFixedHeight pins the minimum (and maximum) height.
        assert choice.list.minimumHeight() >= row_height * CHOICE_LIST_VISIBLE_ROWS


def test_system_without_skills_or_spells_has_no_blocks(qtbot: QtBot) -> None:
    """A game system without skills/spells never renders those blocks."""
    system = build_system()
    del system["skills"]
    del system["spells"]
    pipeline = build_workflow(
        load_data("workflow.yaml"),
        rules=load_creation_rules(DATA_DIR / "creation_rules.yaml"),
        system=system,
        base_module="companion4soloplayer.plugins.demo_plugin",
    )
    dialog = CharacterCreationDialog(pipeline)
    qtbot.addWidget(dialog)

    step_ids = [section.step_id for section in dialog.sections]
    assert "skills" not in step_ids
    assert "spells" not in step_ids

    # Even spellcasting choices never bring the blocks back.
    race = _rows(dialog)["race"][1]
    assert isinstance(race, ChoiceField)
    _select(race, "Elf")
    character_class = _rows(dialog)["class"][1]
    assert isinstance(character_class, ChoiceField)
    _select(character_class, "Wizard")
    step_ids = [section.step_id for section in dialog.sections]
    assert "skills" not in step_ids
    assert "spells" not in step_ids
