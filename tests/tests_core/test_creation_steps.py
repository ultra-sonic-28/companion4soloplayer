"""Tests for the generic character creation steps and strategies."""

from collections.abc import Mapping
from typing import Any

import pytest

from companion4soloplayer.core.creation.context import CharacterCreationContext
from companion4soloplayer.core.creation.inputs import (
    InvalidAnswerError,
    MappingInputProvider,
    MissingInputError,
)
from companion4soloplayer.core.creation.steps import (
    AttributeGenerationStep,
    IdentityStep,
    SelectionStep,
    SkillSelectionStep,
    SpellSelectionStep,
    StepConfigurationError,
)
from companion4soloplayer.core.creation.strategies import (
    ConstantStrategy,
    RollStrategy,
)
from companion4soloplayer.core.dice_roller import DiceRoller

#: Minimal game system used by the step tests.
SYSTEM: dict[str, Any] = {
    "attributes": ["strength", "charm"],
    "races": [{"name": "Dwarf"}, {"name": "Elf"}],
    "classes": ["Wizard", "Scout"],
    "skills": ["Athletics", "Stealth"],
    "spells": [
        {"name": "Light", "level": 1, "classes": []},
        {"name": "Fireball", "level": 2, "classes": ["Wizard"]},
    ],
    "strategies": {"fixed": ConstantStrategy(12)},
}


def make_context(**overrides: Any) -> CharacterCreationContext:
    """Build a context backed by :data:`SYSTEM`.

    Args:
        **overrides: Replacements applied to the system mapping.

    Returns:
        The prepared context.
    """
    system = dict(SYSTEM)
    system.update(overrides)
    return CharacterCreationContext(system=system)


# ----------------------------------------------------------------------
# Strategies
# ----------------------------------------------------------------------


def test_roll_strategy_keeps_the_best_dice() -> None:
    """4d6 keep 3 stays in the 3..18 range and is reproducible."""
    strategy = RollStrategy("4d6", keep=3)
    first = strategy.roll("strength", DiceRoller(seed=7))
    second = strategy.roll("strength", DiceRoller(seed=7))
    assert first == second
    assert 3 <= first <= 18


def test_roll_strategy_detail_returns_kept_dice() -> None:
    """roll_detail returns the kept rolls and their sum."""
    strategy = RollStrategy("4d6", keep=3)
    kept, total = strategy.roll_detail("strength", DiceRoller(seed=7))
    assert len(kept) == 3
    assert total == sum(kept)


def test_roll_strategy_keeps_lowest_when_asked() -> None:
    """keep_best=False keeps the lowest dice."""
    strategy = RollStrategy("4d6", keep=2, keep_best=False)
    kept, total = strategy.roll_detail("strength", DiceRoller(seed=7))
    assert kept == sorted(kept)
    assert total == sum(kept)


@pytest.mark.parametrize("keep", [0, 5])
def test_roll_strategy_rejects_out_of_range_keep(keep: int) -> None:
    """keep must address at least one of the rolled dice."""
    with pytest.raises(ValueError, match="keep"):
        RollStrategy("4d6", keep=keep)


def test_constant_strategy_returns_the_fixed_value() -> None:
    """A constant strategy ignores the roller and the attribute."""
    assert ConstantStrategy(10).roll("mind", DiceRoller()) == 10


# ----------------------------------------------------------------------
# IdentityStep
# ----------------------------------------------------------------------


def test_identity_step_writes_name_and_background() -> None:
    """The step stores both answers under choices.identity."""
    step = IdentityStep()
    context = make_context()
    step.execute(
        context,
        MappingInputProvider({"identity.name": "Aria", "identity.background": "Sellsword"}),
    )
    assert context.get("choices.identity.name") == "Aria"
    assert context.get("choices.identity.background") == "Sellsword"
    assert step.validate(context) == []
    assert step.is_applicable(context) is True


def test_identity_step_requires_the_name() -> None:
    """A missing name raises at input time, an empty one at validation."""
    step = IdentityStep()
    context = make_context()
    with pytest.raises(MissingInputError):
        step.execute(context, MappingInputProvider({}))
    context.set("choices.identity.name", "   ")
    errors = step.validate(context)
    assert errors
    assert "name" in errors[0].lower()


def test_identity_step_background_optional_by_default() -> None:
    """No recorded background is fine unless it is required."""
    step = IdentityStep()
    context = make_context()
    step.execute(context, MappingInputProvider({"identity.name": "Aria"}))
    assert context.get("choices.identity.background") == ""
    assert step.validate(context) == []

    strict = IdentityStep(background_required=True)
    with pytest.raises(MissingInputError):
        strict.execute(context, MappingInputProvider({"identity.name": "Aria"}))


def test_identity_step_with_predefined_backgrounds() -> None:
    """A background catalog turns the answer into a validated choice."""
    step = IdentityStep(background_options=["Orphan", "Scholar"], background_required=True)
    context = make_context()
    step.execute(
        context,
        MappingInputProvider({"identity.name": "Aria", "identity.background": "Orphan"}),
    )
    assert context.get("choices.identity.background") == "Orphan"
    assert step.validate(context) == []
    with pytest.raises(InvalidAnswerError):
        step.execute(
            context,
            MappingInputProvider({"identity.name": "Aria", "identity.background": "Noble"}),
        )


# ----------------------------------------------------------------------
# SelectionStep
# ----------------------------------------------------------------------


def test_selection_step_requires_exactly_one_option_source() -> None:
    """Neither or both of catalog/options is a configuration error."""
    with pytest.raises(StepConfigurationError):
        SelectionStep("race", target="choices.race")
    with pytest.raises(StepConfigurationError):
        SelectionStep("race", target="choices.race", catalog="races", options=["Dwarf"])


def test_selection_step_rejects_non_leaf_target() -> None:
    """The target must address a leaf, not a whole namespace."""
    with pytest.raises(StepConfigurationError):
        SelectionStep("race", target="choices", catalog="races")


def test_selection_step_reads_catalog_from_system() -> None:
    """Options come from the catalog of the game system."""
    step = SelectionStep("race", target="choices.race", catalog="races", optional=True)
    context = make_context()
    assert step.available(context) == ["Dwarf", "Elf"]
    assert step.is_applicable(context) is True
    step.execute(context, MappingInputProvider({"race": "Elf"}))
    assert context.get("choices.race") == "Elf"
    assert step.validate(context) == []


def test_selection_step_without_catalog_is_not_applicable() -> None:
    """A game system without races skips the step entirely."""
    step = SelectionStep("race", target="choices.race", catalog="races", optional=True)
    context = make_context(races=None)
    assert step.is_applicable(context) is False
    assert step.available(context) == []


def test_selection_step_optional_accepts_a_missing_answer() -> None:
    """An optional selection resolves a missing answer to None."""
    step = SelectionStep("race", target="choices.race", catalog="races", optional=True)
    context = make_context()
    step.execute(context, MappingInputProvider({}))
    assert context.get("choices.race") is None
    assert step.validate(context) == []


def test_selection_step_required_needs_an_answer() -> None:
    """A required selection raises without an answer."""
    step = SelectionStep("klass", target="choices.class", catalog="classes")
    context = make_context()
    with pytest.raises(MissingInputError):
        step.execute(context, MappingInputProvider({}))
    assert "class" in step.validate(context)[0]


def test_selection_step_validate_rejects_unknown_value() -> None:
    """A stored value outside the catalog fails validation."""
    step = SelectionStep("race", target="choices.race", catalog="races", optional=True)
    context = make_context()
    context.set("choices.race", "Dragonborn")
    assert step.validate(context)


def test_selection_step_supports_inline_and_callable_options() -> None:
    """Inline lists and state-dependent callables both work."""
    inline = SelectionStep("align", target="choices.align", options=["Lawful", "Chaotic"])
    context = make_context()
    assert inline.available(context) == ["Lawful", "Chaotic"]

    dynamic = SelectionStep(
        "klass",
        target="choices.class",
        options=lambda ctx: ctx.peek("choices.race") and ["Elf Wizard"] or ["Human Wizard"],
    )
    assert dynamic.available(context) == ["Human Wizard"]
    context.set("choices.race", "Elf")
    assert dynamic.available(context) == ["Elf Wizard"]


# ----------------------------------------------------------------------
# AttributeGenerationStep
# ----------------------------------------------------------------------


def test_attribute_step_random_mode_uses_named_strategy() -> None:
    """Random mode resolves the strategy by name in the system data."""
    step = AttributeGenerationStep(strategy="fixed")
    context = make_context()
    assert step.is_applicable(context) is True
    step.execute(context, MappingInputProvider({}))
    assert context.get("values.attributes.strength") == 12
    assert context.get("values.attributes.charm") == 12
    assert step.validate(context) == []


def test_attribute_step_manual_mode_asks_every_value() -> None:
    """Manual mode reads one answer per attribute."""
    step = AttributeGenerationStep(mode="manual", min_value=3, max_value=18)
    context = make_context()
    step.execute(
        context,
        MappingInputProvider({"attributes.strength": 15, "attributes.charm": 8}),
    )
    assert context.get("values.attributes.strength") == 15
    assert context.get("values.attributes.charm") == 8
    assert step.validate(context) == []
    with pytest.raises(InvalidAnswerError):
        step.execute(
            context, MappingInputProvider({"attributes.strength": 99, "attributes.charm": 8})
        )


def test_attribute_step_mixed_mode_splits_manual_and_rolled() -> None:
    """Mixed mode asks only the attributes listed as manual."""
    step = AttributeGenerationStep(mode="mixed", strategy="fixed", manual_attributes=("strength",))
    context = make_context()
    step.execute(context, MappingInputProvider({"attributes.strength": 17}))
    assert context.get("values.attributes.strength") == 17
    assert context.get("values.attributes.charm") == 12
    assert step.validate(context) == []


def test_attribute_step_rejects_unknown_mode() -> None:
    """An unknown generation mode is a configuration error."""
    with pytest.raises(StepConfigurationError, match="mode"):
        AttributeGenerationStep(mode="point-buy")


def test_attribute_step_unknown_strategy_raises() -> None:
    """An unknown strategy name fails at execution with a clear error."""
    step = AttributeGenerationStep(strategy="does_not_exist")
    context = make_context()
    with pytest.raises(StepConfigurationError, match="unknown strategy"):
        step.execute(context, MappingInputProvider({}))


def test_attribute_step_missing_strategy_raises() -> None:
    """Random mode without any strategy fails explicitly."""
    step = AttributeGenerationStep()
    context = make_context()
    with pytest.raises(StepConfigurationError, match="strategy"):
        step.execute(context, MappingInputProvider({}))


def test_attribute_step_not_applicable_without_attributes() -> None:
    """A system without attributes skips the step."""
    step = AttributeGenerationStep(strategy="fixed")
    context = make_context(attributes=None)
    assert step.is_applicable(context) is False


def test_attribute_step_explicit_names_override_system_data() -> None:
    """Explicit attribute names win over the system declaration."""
    step = AttributeGenerationStep(attributes=["luck"], strategy="fixed")
    context = make_context()
    step.execute(context, MappingInputProvider({}))
    assert context.get("values.attributes.luck") == 12
    assert not context.has("values.attributes.strength")


def test_attribute_step_validate_reports_missing_and_invalid_values() -> None:
    """Validation catches absent, non integer and out of bound values."""
    step = AttributeGenerationStep(mode="manual", min_value=3, max_value=18)
    context = make_context()
    errors = step.validate(context)
    assert len(errors) == 2

    context.set("values.attributes.strength", True)
    context.set("values.attributes.charm", 99)
    errors = step.validate(context)
    assert any("integer" in error for error in errors)
    assert any("<= 18" in error for error in errors)


# ----------------------------------------------------------------------
# SkillSelectionStep
# ----------------------------------------------------------------------


def test_skill_step_free_mode_picks_and_mirrors() -> None:
    """Free mode stores raw picks and mirrors them to the working list."""
    step = SkillSelectionStep(min_count=1, max_count=2)
    context = make_context()
    assert step.is_applicable(context) is True
    step.execute(context, MappingInputProvider({"skills": ["Stealth"]}))
    assert context.get("choices.skills") == ["Stealth"]
    assert context.get("values.skills") == ["Stealth"]
    assert step.validate(context) == []


def test_skill_step_inherited_and_none_modes_are_not_applicable() -> None:
    """Inherited/none modes ask nothing (rules or no skills at all)."""
    inherited = SkillSelectionStep(mode="inherited")
    none = SkillSelectionStep(mode="none")
    context = make_context()
    assert inherited.is_applicable(context) is False
    assert none.is_applicable(context) is False


def test_skill_step_rejects_unknown_mode_and_bad_bounds() -> None:
    """Unknown modes and inconsistent bounds are configuration errors."""
    with pytest.raises(StepConfigurationError, match="mode"):
        SkillSelectionStep(mode="free-form")
    with pytest.raises(StepConfigurationError, match="max_count"):
        SkillSelectionStep(min_count=3, max_count=2)


def test_skill_step_without_catalog_is_not_applicable() -> None:
    """A system without a skill catalog skips the step."""
    step = SkillSelectionStep()
    context = make_context(skills=None)
    assert step.is_applicable(context) is False


def test_skill_step_validate_catches_bad_picks() -> None:
    """Unknown picks, count bounds and mirror mismatches fail."""
    step = SkillSelectionStep(min_count=1, max_count=2)
    context = make_context()
    context.set("choices.skills", ["Singing"])
    context.set("values.skills", ["Singing"])
    errors = step.validate(context)
    assert any("Unknown skill" in error for error in errors)

    context.set("choices.skills", ["Athletics", "Stealth", "Singing"])
    context.set("values.skills", ["Athletics", "Stealth", "Singing"])
    errors = step.validate(context)
    assert any("At most 2" in error for error in errors)

    context.set("choices.skills", ["Athletics"])
    context.set("values.skills", [])
    errors = step.validate(context)
    assert any("mirror" in error for error in errors)


# ----------------------------------------------------------------------
# SpellSelectionStep
# ----------------------------------------------------------------------


def spell_filter(spell: Mapping[str, Any], context: CharacterCreationContext) -> bool:
    """Keep level 1 spells only (test filter).

    Args:
        spell: Spell catalog entry.
        context: Current creation state.

    Returns:
        True for level 1 spells.
    """
    return int(spell.get("level", 1)) == 1


def test_spell_step_filters_the_catalog() -> None:
    """The available list only contains the spells passing the filter."""
    step = SpellSelectionStep(spell_filter=spell_filter, max_count=1)
    context = make_context()
    assert step.available(context) == ["Light"]
    assert step.is_applicable(context) is True
    step.execute(context, MappingInputProvider({"spells": ["Light"]}))
    assert context.get("choices.spells") == ["Light"]
    assert context.get("values.spells") == ["Light"]
    assert step.validate(context) == []


def test_spell_step_auto_and_none_modes_are_not_applicable() -> None:
    """Automatic attribution and spell-less systems ask nothing."""
    auto = SpellSelectionStep(mode="auto")
    none = SpellSelectionStep(mode="none")
    context = make_context()
    assert auto.is_applicable(context) is False
    assert none.is_applicable(context) is False


def test_spell_step_without_catalog_is_not_applicable() -> None:
    """A system without a spell catalog skips the step."""
    step = SpellSelectionStep()
    context = make_context(spells=None)
    assert step.is_applicable(context) is False


def test_spell_step_validate_rejects_unavailable_pick() -> None:
    """A pick excluded by the filter (or absent) fails validation."""
    step = SpellSelectionStep(spell_filter=spell_filter, max_count=1)
    context = make_context()
    context.set("choices.spells", ["Fireball"])
    context.set("values.spells", ["Fireball"])
    errors = step.validate(context)
    assert any("not available" in error for error in errors)


def test_spell_step_broken_filter_raises_configuration_error() -> None:
    """A filter raising an error is reported as a configuration error."""

    def broken(spell: Mapping[str, Any], context: CharacterCreationContext) -> bool:
        raise RuntimeError("boom")

    step = SpellSelectionStep(spell_filter=broken)
    context = make_context()
    with pytest.raises(StepConfigurationError, match="failed"):
        step.is_applicable(context)


def test_spell_step_rejects_unknown_mode_and_non_callable_filter() -> None:
    """Unknown modes and non callable filters are configuration errors."""
    with pytest.raises(StepConfigurationError, match="mode"):
        SpellSelectionStep(mode="daily")
    with pytest.raises(StepConfigurationError, match="filter"):
        SpellSelectionStep(spell_filter="not callable")  # type: ignore[arg-type]
