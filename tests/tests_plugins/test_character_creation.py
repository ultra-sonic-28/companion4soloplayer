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
    Condition,
    CreationRule,
    Effect,
    InputKind,
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
    can_cast_spells,
    load_attributes,
    skill_available,
    spell_available,
)
from companion4soloplayer.plugins.demo_plugin.data import DATA_DIR, load_data
from companion4soloplayer.utils.plugin_loader import PluginLoader
from companion4soloplayer.utils.yaml_loader import PyClassRef

PLUGINS_SRC = Path(__file__).resolve().parents[2] / "src" / "companion4soloplayer" / "plugins"

#: Answer keys of the reference character (see docs/character_creation.md):
#: ``Diplomacy`` is a general skill and ``Arcane Lore`` a Wizard class
#: skill, both available to a Dwarf Wizard.
DWARF_WIZARD: dict[str, Any] = {
    "identity.name": "Brom",
    "identity.background": "Orphaned smith",
    "race": "Dwarf",
    "class": "Wizard",
    "skills": ["Diplomacy", "Arcane Lore"],
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
    """The step order is the one declared in datas/workflow.yaml.

    The attribute step declares ``block: "*"``: it is expanded into one
    step per ``attributes.yaml`` block (``attributes``, ``save``), in
    declaration order.
    """
    assert [step.step_id for step in pipeline.steps] == [
        "identity",
        "race",
        "class",
        "attributes",
        "save",
        "skills",
        "spells",
    ]


def test_workflow_ships_its_yaml_documents() -> None:
    """The plugin ships the workflow, rules and catalog documents."""
    names = (
        "workflow.yaml",
        "creation_rules.yaml",
        "attributes.yaml",
        "classes.yaml",
        "races.yaml",
        "skills.yaml",
        "spells.yaml",
        "traits.yaml",
    )
    for name in names:
        assert (DATA_DIR / name).is_file()


def test_creation_rules_document_parses() -> None:
    """creation_rules.yaml yields unique, well-formed rule identifiers."""
    rules = load_creation_rules(DATA_DIR / "creation_rules.yaml")
    identifiers = [rule.id for rule in rules]
    assert len(identifiers) == len(set(identifiers))
    assert {"dwarf_hardy", "elf_frail", "wizard_mind", "sturdy", "iron_body"} <= set(identifiers)
    dwarf = next(rule for rule in rules if rule.id == "dwarf_hardy")
    assert dwarf.when[0].operator is Operator.EQ
    assert dwarf.when[0].target == "choices.race"


def test_system_data_exposes_catalogs_and_strategies() -> None:
    """The system mapping carries the catalogs, blocks, strategies.

    ``attribute_blocks`` maps every ``attributes.yaml`` level-1 entry to
    its block (``attributes``, ``save``); the first block is mirrored
    under the legacy ``attributes`` / ``attributes_title`` keys.
    """
    system = build_system()
    assert [race["name"] for race in system["races"]][:1] == ["Human"]
    assert [klass["name"] for klass in system["classes"]][:1] == ["Warrior"]
    assert "Arcane Lore" in [skill["name"] for skill in system["skills"]]
    assert "Spark" in [spell["name"] for spell in system["spells"]]
    assert list(system["attribute_blocks"]) == ["attributes", "save"]
    assert system["attribute_blocks"]["save"]["title"] == "Saving Throws"
    assert [entry["id"] for entry in system["attribute_blocks"]["save"]["list"]] == [
        "magic",
        "poison",
    ]
    assert system["attributes"][0]["id"] == "strength"
    assert system["attributes"][0]["name"] == "Strength"
    assert [entry["id"] for entry in system["attributes"]][-1] == "charisma"
    assert system["attributes_title"] == "Attributes"
    assert isinstance(system["strategies"]["classic_4d6"], FourSixKeepBestStrategy)


def test_attributes_document_drives_ids_names_and_order() -> None:
    """datas/attributes.yaml declares one block per level-1 entry."""
    blocks = load_attributes()
    assert [block["id"] for block in blocks] == ["attributes", "save"]
    attributes = blocks[0]
    assert attributes["title"] == "Attributes"
    assert [entry["id"] for entry in attributes["list"]] == [
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    ]
    assert [entry["name"] for entry in attributes["list"]] == [
        "Strength",
        "Dexterity",
        "Constitution",
        "Intelligence",
        "Wisdom",
        "Charisma",
    ]
    assert all(isinstance(entry["description"], str) for entry in attributes["list"])
    save = blocks[1]
    assert save["title"] == "Saving Throws"
    assert [entry["id"] for entry in save["list"]] == ["magic", "poison"]
    assert [entry["name"] for entry in save["list"]] == ["Magic", "Poison"]


def test_steps_describe_an_empty_start_and_wait_for_the_right_choices(
    pipeline: CharacterCreationPipeline,
) -> None:
    """At start: empty skill list, no spells; choices unlock the blocks."""
    context = pipeline.create_context()
    skills = next(step for step in pipeline.steps if step.step_id == "skills")
    spells = next(step for step in pipeline.steps if step.step_id == "spells")

    # No race/class chosen: the skills block describes an empty list.
    skill_fields = skills.describe_inputs(context)
    assert len(skill_fields) == 1
    assert skill_fields[0].options == ()
    # ... and no spellcasting choice means no spells block at all.
    assert spells.describe_inputs(context) == ()

    # A race opens the skill catalog: the 6 general skills plus the
    # racial ones (Stonewise and Infravision for a Dwarf); class skills
    # still wait for a class and monster skills never show up. The list
    # comes back sorted alphabetically.
    context.set("choices.race", "Dwarf")
    assert skills.describe_inputs(context)[0].options == (
        "Agriculture",
        "Carpentry",
        "Diplomacy",
        "Fishing",
        "Infravision",
        "Mining",
        "Stonewise",
        "Swimming",
    )
    assert spells.describe_inputs(context) == ()

    # A spellcasting class materializes the spells block with every
    # level-1 spell of that class, sorted alphabetically too.
    context.set("choices.class", "Wizard")
    assert len(skills.describe_inputs(context)[0].options) == 10
    spell_fields = spells.describe_inputs(context)
    assert len(spell_fields) == 1
    assert spell_fields[0].options == (
        "Frost Touch",
        "Light",
        "Nature's Whisper",
        "Rune Ward",
        "Spark",
    )

    # A non-casting combination hides it again.
    context.set("choices.race", "Human")
    context.set("choices.class", "Warrior")
    assert spells.describe_inputs(context) == ()


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

    # Free picks stand alone: skills.yaml declares the class/race
    # abilities of the catalog, no rule grants them anymore.
    assert context.peek("values.skills") == ["Diplomacy", "Arcane Lore"]
    assert context.effective("values.skills") == ["Diplomacy", "Arcane Lore"]

    # Free spell pick only: Rune Ward is a level-1 spell of the Wizard.
    assert context.peek("values.spells") == ["Rune Ward"]
    assert context.effective("values.spells") == ["Rune Ward"]

    # The export exposes the effective values.
    exported = context.export()
    assert exported["choices"]["identity"]["name"] == "Brom"
    assert exported["values"]["attributes"]["constitution"] == base_con + 2
    assert set(report.rules_fired) >= {
        "dwarf_hardy",
        "dwarf_save_poison",
        "dwarf_save_magic",
        "wizard_mind",
    }


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
    # No racial skill grant anymore: the free picks stand alone.
    assert context.effective("values.skills") == ["Diplomacy", "Arcane Lore"]
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
    # Without a race/class choice no skill or spell is proposed: both
    # steps are not applicable and the recorded answers are ignored.
    statuses = {result.step_id: result.status for result in report.results}
    assert statuses["skills"].value == "skipped"
    assert statuses["spells"].value == "skipped"
    assert context.peek("choices.skills") is None
    assert context.peek("choices.spells") is None
    # No free pick means no skill-driven bonus either.
    assert "iron_body" not in report.rules_fired
    assert context.effective("values.attributes.constitution") == context.peek(
        "values.attributes.constitution"
    )


def test_free_skill_picks_grant_their_rule_bonuses(
    pipeline: CharacterCreationPipeline,
) -> None:
    """Once a race/class is chosen, free picks feed the rules engine."""
    answers = {
        "identity.name": "Rowan",
        "identity.background": "Keen tracker",
        "race": "Human",
        "class": "Warrior",
        "skills": ["Athletics", "Survival"],
    }
    context = pipeline.create_context()
    report = pipeline.run(context, MappingInputProvider(answers))
    assert report.ok
    assert context.peek("choices.skills") == ["Athletics", "Survival"]
    # Athletics (free pick) grants its own bonus through the rules.
    assert "iron_body" in report.rules_fired


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
        "class": "Rogue",
        "skills": ["Stealth", "Perception"],
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
        f"attributes.{entry['id']}": 10 + index
        for index, entry in enumerate(build_system()["attributes"])
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
    """Inherited skills and automatic spells ask no question.

    ``creation_rules.yaml`` no longer grants skills or spells (they now
    come from the catalogs picked freely), so this alternate workflow
    declares its own grant rules to cover the ``inherited`` and ``auto``
    modes of the core steps.
    """
    workflow = {
        "steps": [
            character_workflow_step("race", target="choices.race", catalog="races"),
            character_workflow_step("class", target="choices.class", catalog="classes"),
            character_workflow_step("skills", mode="inherited"),
            character_workflow_step("spells", mode="auto"),
        ]
    }
    grant_rules = [
        CreationRule(
            id="elf_infravision",
            description="Elves inherit the Infravision skill.",
            when=(Condition("choices.race", Operator.EQ, "Elf"),),
            effects=(Effect("values.skills", Action.GRANT, "Infravision"),),
        ),
        CreationRule(
            id="wizard_spark",
            description="Wizards start with the Spark spell.",
            when=(Condition("choices.class", Operator.EQ, "Wizard"),),
            effects=(Effect("values.spells", Action.GRANT, "Spark"),),
        ),
    ]
    pipeline = build_workflow(
        workflow,
        rules=grant_rules,
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
    assert context.effective("values.skills") == ["Infravision"]
    assert context.effective("values.spells") == ["Spark"]


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


def test_can_cast_spells_follows_the_yaml_flags() -> None:
    """The can_cast_spells flags of races.yaml/classes.yaml gate casting."""
    context = CharacterCreationContext(system=build_system())
    # Nothing chosen yet: no casting at all (spells block stays hidden).
    assert can_cast_spells(context) is False

    context.set("choices.race", "Dwarf")
    context.set("choices.class", "Warrior")
    assert can_cast_spells(context) is False  # neither of them casts

    context.set("choices.class", "Wizard")
    assert can_cast_spells(context) is True  # the class can cast

    context.set("choices.race", "Gnome")
    context.set("choices.class", "Rogue")
    assert can_cast_spells(context) is True  # the race can cast

    context.set("choices.race", "Human")
    context.set("choices.class", "Rogue")
    assert can_cast_spells(context) is False


def test_skill_available_filters_by_type_race_and_class() -> None:
    """The skill list follows the entry type and the choices made.

    With no race and no class the catalog stays closed; a chosen race
    opens the general and matching racial skills, the class adds its
    own skills, and monster abilities never show up for a player
    character.
    """
    general = {"name": "Diplomacy", "type": "general"}
    racial = {"name": "Stonewise", "type": "race", "races": ["Dwarf"]}
    class_skill = {"name": "Spellcraft", "type": "class", "classes": ["Wizard"]}
    monster = {"name": "Sneak Attack", "type": "monster"}

    context = CharacterCreationContext(system=build_system())
    # Nothing chosen yet: the whole catalog stays closed.
    assert skill_available(general, context) is False
    assert skill_available(racial, context) is False
    assert skill_available(class_skill, context) is False
    assert skill_available(monster, context) is False

    # A race opens the general skills; racial skills need a match and
    # class skills still wait for a class.
    context.set("choices.race", "Human")
    assert skill_available(general, context) is True
    assert skill_available(racial, context) is False  # not a Dwarf
    assert skill_available(class_skill, context) is False  # no class yet

    context.set("choices.race", "Dwarf")
    assert skill_available(racial, context) is True

    # The class adds its class skills; racial skills still match and
    # monster abilities stay hidden.
    context.set("choices.class", "Wizard")
    assert skill_available(class_skill, context) is True
    assert skill_available(racial, context) is True
    assert skill_available(general, context) is True
    assert skill_available(monster, context) is False  # never for players

    # Another class does not unlock its skills.
    context.set("choices.class", "Warrior")
    assert skill_available(class_skill, context) is False


def test_spell_available_filters_by_casting_class_and_level() -> None:
    """The filter applies the casting flag, the class and the level."""
    context = CharacterCreationContext(system=build_system())
    wizard_spell = {"name": "Spark", "level": 1, "classes": ["Wizard"]}
    classless = {"name": "Light", "level": 1, "classes": []}
    high_level = {"name": "Fireball", "level": 3, "classes": ["Wizard"]}
    guarded = {
        "name": "Rune Ward",
        "level": 1,
        "classes": ["Wizard"],
        "requires_skill": "Arcane Lore",
    }

    # Without a spellcasting race/class, no spell at all stays available.
    assert spell_available(classless, context) is False
    assert spell_available(wizard_spell, context) is False

    context.set("choices.class", "Wizard")
    # The Wizard casts: the classless spells come back with the class
    # spells of level 1; a requires_skill guard never hides a spell.
    assert spell_available(classless, context) is True
    assert spell_available(wizard_spell, context) is True
    assert spell_available(guarded, context) is True
    assert spell_available(high_level, context) is False

    # Another class only gets its own spells.
    context.set("choices.class", "Priest")
    assert spell_available(wizard_spell, context) is False

    # A non-casting class combination loses every spell again.
    context.set("choices.class", "Rogue")
    assert spell_available(classless, context) is False
    context.set("choices.race", "Gnome")
    assert spell_available(classless, context) is True  # the race casts


# ----------------------------------------------------------------------
# Saving throws (per-block strategy, classes.yaml)
# ----------------------------------------------------------------------


def test_classes_declare_base_saving_throws() -> None:
    """Every class of classes.yaml declares its base saving throws."""
    classes = load_data("classes.yaml")
    assert {entry["name"]: entry["save"] for entry in classes} == {
        "Warrior": {"poison": 16, "magic": 19},
        "Priest": {"poison": 10, "magic": 15},
        "Wizard": {"poison": 14, "magic": 12},
        "Rogue": {"poison": 13, "magic": 15},
    }


def test_workflow_uses_a_different_strategy_per_block(
    pipeline: CharacterCreationPipeline,
) -> None:
    """The attributes are rolled, the saving throws are assigned."""
    steps = {step.step_id: step for step in pipeline.steps}
    context = pipeline.create_context()
    attributes = steps["attributes"].describe_inputs(context)
    assert {field.kind for field in attributes} == {InputKind.DICE}

    save = steps["save"].describe_inputs(context)
    assert [field.kind for field in save] == [InputKind.READONLY, InputKind.READONLY]
    # No die to roll and no answer collected for a saving throw.
    assert all(field.roll is None for field in save)


@pytest.mark.parametrize(
    ("character_class", "magic", "poison"),
    [
        ("Warrior", 19, 16),
        ("Priest", 15, 10),
        ("Wizard", 12, 14),
        ("Rogue", 15, 13),
    ],
)
def test_saving_throws_come_from_the_chosen_class(
    pipeline: CharacterCreationPipeline,
    character_class: str,
    magic: int,
    poison: int,
) -> None:
    """The class assigns the base saving throws: no dice drawn."""
    context = pipeline.create_context()
    report = pipeline.run(
        context,
        MappingInputProvider(
            {
                "identity.name": "Solo",
                "identity.background": "None",
                "class": character_class,
                "skills": ["Diplomacy", "Swimming"],
            }
        ),
    )
    assert report.ok
    assert context.get("values.save") == {"magic": magic, "poison": poison}


def test_saving_throws_are_modulated_by_the_creation_rules(
    pipeline: CharacterCreationPipeline,
) -> None:
    """The race bonuses of creation_rules.yaml layer on the base."""
    context = pipeline.create_context()
    report = pipeline.run(
        context,
        MappingInputProvider(
            {
                "identity.name": "Brom",
                "identity.background": "Orphaned smith",
                "race": "Dwarf",
                "class": "Warrior",
                "skills": ["Athletics", "Survival"],
            }
        ),
    )
    assert report.ok
    # Base from classes.yaml (Warrior), then +2 / +2 for the Dwarf.
    assert context.get("values.save") == {"magic": 19, "poison": 16}
    assert context.effective("values.save.magic") == 21
    assert context.effective("values.save.poison") == 18


def test_saving_throws_fall_back_without_a_class(
    pipeline: CharacterCreationPipeline,
) -> None:
    """An undefined class keeps neutral saving throws."""
    context = pipeline.create_context()
    report = pipeline.run(
        context,
        MappingInputProvider({"identity.name": "Solo", "identity.background": "None"}),
    )
    assert report.ok
    assert context.get("values.save") == {"magic": 10, "poison": 10}
