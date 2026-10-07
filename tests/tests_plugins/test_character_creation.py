"""Character creation workflow of the demo plugin.

End-to-end scenarios covering the functional requirements: optional
race/class, random/manual/mixed attribute generation, free or inherited
skills, filtered or automatic spells, race/class/attribute/skill based
bonuses and the plugin-declared step order.
"""

from pathlib import Path
from typing import Any

import pytest

from companion4soloplayer.core.creation import (
    Action,
    CharacterCreationContext,
    CharacterCreationPipeline,
    Effect,
    MappingInputProvider,
    Operator,
    build_workflow,
    load_creation_rules,
)
from companion4soloplayer.core.dice_roller import DiceRoller
from companion4soloplayer.plugins.demo_plugin import Plugin
from companion4soloplayer.plugins.demo_plugin.creation import (
    FourSixKeepBestStrategy,
    build_system,
    spell_available,
)
from companion4soloplayer.plugins.demo_plugin.data import DATA_DIR, load_data
from companion4soloplayer.utils.plugin_loader import PluginLoader
from companion4soloplayer.utils.yaml_loader import PyClassRef

PLUGINS_SRC = Path(__file__).resolve().parents[2] / "src" / "companion4soloplayer" / "plugins"

#: Answer keys of the reference character (see docs/character_creation.md).
DWARF_WIZARD: dict[str, Any] = {
    "identity.name": "Brom",
    "identity.background": "Orphaned smith",
    "race": "Dwarf",
    "class": "Wizard",
    "skills": ["Diplomacy", "Medicine"],
    "spells": ["Rune Ward"],
}


@pytest.fixture
def plugin() -> Plugin:
    """Return an instantiated demo plugin facade."""
    loaded = PluginLoader(plugins_dir=str(PLUGINS_SRC)).load_plugin("demo")
    assert loaded is not None
    return loaded  # type: ignore[return-value]


@pytest.fixture
def pipeline(plugin: Plugin) -> CharacterCreationPipeline:
    """Return the character creation pipeline of the demo system."""
    return plugin.create_character_creation()


def load_data_workflow() -> Any:
    """Load the workflow document declared by the plugin.

    Returns:
        The parsed ``datas/workflow.yaml`` document.
    """
    return load_data("workflow.yaml")


# ----------------------------------------------------------------------
# Assembly and declared data
# ----------------------------------------------------------------------


def test_plugin_exposes_the_creation_workflow(plugin: Plugin) -> None:
    """The facade builds and caches a reusable pipeline."""
    built = plugin.create_character_creation()
    assert isinstance(built, CharacterCreationPipeline)
    assert plugin.create_character_creation() is built


def test_workflow_order_comes_from_workflow_yaml(
    pipeline: CharacterCreationPipeline,
) -> None:
    """The step order is the one declared in datas/workflow.yaml."""
    assert [step.step_id for step in pipeline.steps] == [
        "identity",
        "race",
        "class",
        "attributes",
        "skills",
        "spells",
    ]


def test_workflow_ships_its_yaml_documents() -> None:
    """The plugin ships the workflow, rules and catalog documents."""
    names = (
        "workflow.yaml",
        "creation_rules.yaml",
        "races.yaml",
        "skills.yaml",
        "spells.yaml",
    )
    for name in names:
        assert (DATA_DIR / name).is_file()


def test_creation_rules_document_parses() -> None:
    """creation_rules.yaml yields unique, well-formed rule identifiers."""
    rules = load_creation_rules(DATA_DIR / "creation_rules.yaml")
    identifiers = [rule.id for rule in rules]
    assert len(identifiers) == len(set(identifiers))
    assert {"dwarf_hardy", "elf_frail", "wizard_mind", "sturdy", "arcane_initiate"} <= set(
        identifiers
    )
    dwarf = next(rule for rule in rules if rule.id == "dwarf_hardy")
    assert dwarf.when[0].operator is Operator.EQ
    assert dwarf.when[0].target == "choices.race"


def test_system_data_exposes_catalogs_and_strategies() -> None:
    """The system mapping carries the catalogs, attributes, strategies."""
    system = build_system()
    assert [race["name"] for race in system["races"]][:1] == ["Human"]
    assert [klass["name"] for klass in system["classes"]][:1] == ["Adventurer"]
    assert "Arcane Lore" in [skill["name"] for skill in system["skills"]]
    assert "Spark" in [spell["name"] for spell in system["spells"]]
    assert system["attributes"][0] == "strength"
    assert isinstance(system["strategies"]["classic_4d6"], FourSixKeepBestStrategy)


def test_four_six_keep_best_strategy_range() -> None:
    """The classic 4d6-keep-3 method stays in the 3..18 range."""
    strategy = FourSixKeepBestStrategy()
    for seed in range(5):
        assert 3 <= strategy.roll("strength", DiceRoller(seed=seed)) <= 18


# ----------------------------------------------------------------------
# Full scenarios
# ----------------------------------------------------------------------


def test_dwarf_wizard_full_run(pipeline: CharacterCreationPipeline) -> None:
    """A Dwarf Wizard gets racial and class bonuses, skills and spells."""
    context = pipeline.create_context()
    report = pipeline.run(context, MappingInputProvider(DWARF_WIZARD))
    assert report.ok
    assert report.completed

    # Race bonus: +2 constitution on top of the rolled base.
    base_con = context.peek("values.attributes.constitution")
    assert isinstance(base_con, int)
    assert context.effective("values.attributes.constitution") == base_con + 2

    # Class bonus: +2 intelligence.
    base_int = context.peek("values.attributes.intelligence")
    assert isinstance(base_int, int)
    assert context.effective("values.attributes.intelligence") == base_int + 2

    # Inherited skills layered over the free picks.
    assert context.peek("values.skills") == ["Diplomacy", "Medicine"]
    skills = context.effective("values.skills")
    assert "Stonewise" in skills  # from the race
    assert "Arcane Lore" in skills  # from the class

    # Free spell pick + automatic grants (grimoire and skill bonus).
    spells = context.effective("values.spells")
    assert "Rune Ward" in spells  # picked, requires Arcane Lore
    assert {"Spark", "Mend", "Light"} <= set(spells)

    # The export exposes the effective values.
    exported = context.export()
    assert exported["choices"]["identity"]["name"] == "Brom"
    assert exported["values"]["attributes"]["constitution"] == base_con + 2
    assert set(report.rules_fired) >= {"dwarf_hardy", "wizard_mind", "arcane_initiate"}


def test_elf_gets_a_bonus_and_a_malus(pipeline: CharacterCreationPipeline) -> None:
    """The Elf race applies both +2 dexterity and -1 constitution."""
    answers = dict(DWARF_WIZARD, race="Elf")
    context = pipeline.create_context()
    report = pipeline.run(context, MappingInputProvider(answers))
    assert report.ok
    assert context.effective("values.attributes.dexterity") == (
        context.peek("values.attributes.dexterity") + 2
    )
    assert context.effective("values.attributes.constitution") == (
        context.peek("values.attributes.constitution") - 1
    )
    assert "Stealth" in context.effective("values.skills")
    assert "elf_frail" in report.rules_fired


def test_race_and_class_are_optional(pipeline: CharacterCreationPipeline) -> None:
    """A character without race and class skips every such bonus."""
    answers = {
        "identity.name": "Rook",
        "identity.background": "",
        "skills": ["Athletics", "Medicine"],
        "spells": ["Light"],
    }
    context = pipeline.create_context()
    report = pipeline.run(context, MappingInputProvider(answers))
    assert report.ok
    assert context.peek("choices.race") is None
    assert context.peek("choices.class") is None
    assert "dwarf_hardy" not in report.rules_fired
    assert "wizard_mind" not in report.rules_fired
    # Athletics (free pick) still grants its own bonus through the rules.
    assert "iron_body" in report.rules_fired
    assert context.effective("values.attributes.constitution") == context.peek(
        "values.attributes.constitution"
    )


def test_system_without_races_skips_the_race_step() -> None:
    """Without a race catalog the race step is reported as skipped."""
    workflow = load_data_workflow()
    system = build_system()
    del system["races"]
    pipeline = build_workflow(
        workflow,
        system=system,
        base_module="companion4soloplayer.plugins.demo_plugin",
    )
    answers = {
        "identity.name": "Nix",
        "class": "Scout",
        "skills": ["Stealth", "Perception"],
        "spells": ["Light"],
    }
    report = pipeline.run(pipeline.create_context(), MappingInputProvider(answers))
    assert report.ok
    statuses = {result.step_id: result.status for result in report.results}
    assert statuses["race"].value == "skipped"


# ----------------------------------------------------------------------
# Alternate configurations (requirement: order and modes vary per system)
# ----------------------------------------------------------------------


def character_workflow_step(step_id: str, **params: Any) -> PyClassRef:
    """Build a core step reference for a test workflow.

    Args:
        step_id: Identifier of the step.
        **params: Constructor parameters of the step.

    Returns:
        The class reference.
    """
    class_paths = {
        "identity": "companion4soloplayer.core.creation:IdentityStep",
        "race": "companion4soloplayer.core.creation:SelectionStep",
        "class": "companion4soloplayer.core.creation:SelectionStep",
        "attributes": "companion4soloplayer.core.creation:AttributeGenerationStep",
        "skills": "companion4soloplayer.core.creation:SkillSelectionStep",
        "spells": "companion4soloplayer.core.creation:SpellSelectionStep",
    }
    return PyClassRef(path=class_paths[step_id], params={"step_id": step_id, **params})


def test_manual_attribute_workflow() -> None:
    """Manual mode asks every attribute (requirement 3, manual side)."""
    workflow = {
        "steps": [character_workflow_step("attributes", mode="manual", min_value=3, max_value=18)]
    }
    pipeline = build_workflow(workflow, system=build_system())
    answers = {
        f"attributes.{name}": 10 + index for index, name in enumerate(build_system()["attributes"])
    }
    context = pipeline.create_context()
    report = pipeline.run(context, MappingInputProvider(answers))
    assert report.ok
    assert context.get("values.attributes.strength") == 10
    assert context.get("values.attributes.charisma") == 15


def test_mixed_attribute_workflow() -> None:
    """Mixed mode asks some attributes and rolls the others."""
    workflow = {
        "steps": [
            character_workflow_step(
                "attributes",
                mode="mixed",
                strategy="classic_4d6",
                manual_attributes=["strength"],
                min_value=3,
                max_value=18,
            )
        ]
    }
    pipeline = build_workflow(workflow, system=build_system())
    context = pipeline.create_context()
    report = pipeline.run(context, MappingInputProvider({"attributes.strength": 9}))
    assert report.ok
    assert context.get("values.attributes.strength") == 9
    rolled = context.get("values.attributes.dexterity")
    assert isinstance(rolled, int)
    assert 3 <= rolled <= 18


def test_inherited_skills_and_automatic_spells_workflow() -> None:
    """Inherited skills and automatic spells ask no question."""
    workflow = {
        "steps": [
            character_workflow_step("race", target="choices.race", catalog="races"),
            character_workflow_step("class", target="choices.class", catalog="classes"),
            character_workflow_step("skills", mode="inherited"),
            character_workflow_step("spells", mode="auto"),
        ]
    }
    pipeline = build_workflow(
        workflow,
        rules=load_creation_rules(DATA_DIR / "creation_rules.yaml"),
        system=build_system(),
        base_module="companion4soloplayer.plugins.demo_plugin",
    )
    answers = {"race": "Elf", "class": "Wizard"}
    context = pipeline.create_context()
    report = pipeline.run(context, MappingInputProvider(answers))
    assert report.ok
    statuses = {result.step_id: result.status for result in report.results}
    assert statuses["skills"].value == "skipped"
    assert statuses["spells"].value == "skipped"
    # Only the grants remain: no free pick, no spell question.
    assert context.peek("values.skills") is None
    assert context.effective("values.skills") == ["Stealth", "Arcane Lore"]
    assert context.effective("values.spells") == ["Spark", "Mend", "Light"]


def test_minimal_workflow_without_optional_steps() -> None:
    """A system declaring only identity and attributes still runs."""
    workflow = {
        "steps": [
            character_workflow_step("identity"),
            character_workflow_step("attributes", strategy="3d6", min_value=3, max_value=18),
        ]
    }
    pipeline = build_workflow(workflow, system=build_system())
    context = pipeline.create_context()
    report = pipeline.run(
        context,
        MappingInputProvider({"identity.name": "Solo", "identity.background": "None"}),
    )
    assert report.ok
    assert report.completed
    assert [step.step_id for step in pipeline.steps] == ["identity", "attributes"]


# ----------------------------------------------------------------------
# Spell filter
# ----------------------------------------------------------------------


def test_spell_available_filters_by_class_level_and_skill() -> None:
    """The filter applies the class, level and skill requirements."""
    context = CharacterCreationContext()
    wizard_spell = {"name": "Spark", "level": 1, "classes": ["Wizard"]}
    classless = {"name": "Light", "level": 1, "classes": []}
    high_level = {"name": "Fireball", "level": 2, "classes": ["Wizard"]}
    skilled = {
        "name": "Rune Ward",
        "level": 1,
        "classes": [],
        "requires_skill": "Arcane Lore",
    }

    # Without a chosen class, only classless spells stay available.
    assert spell_available(classless, context) is True
    assert spell_available(wizard_spell, context) is False

    context.set("choices.class", "Wizard")
    assert spell_available(wizard_spell, context) is True
    assert spell_available(high_level, context) is False

    assert spell_available(skilled, context) is False
    context.record("values.skills", Effect("values.skills", Action.GRANT, "Arcane Lore"))
    assert spell_available(skilled, context) is True
