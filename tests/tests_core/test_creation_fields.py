"""Tests for the input field descriptions of the creation steps.

``CreationStep.describe_inputs()`` declares the data a step is going to
ask (the Player dialog builds its form from those descriptions), and
the attribute step keeps the dice answers recorded by the UI.
"""

from collections.abc import Mapping
from typing import Any

import pytest

from companion4soloplayer.core.creation.context import CharacterCreationContext
from companion4soloplayer.core.creation.inputs import (
    InputKind,
    InputProvider,
    InvalidAnswerError,
    MappingInputProvider,
    MissingInputError,
)
from companion4soloplayer.core.creation.steps import (
    AttributeGenerationStep,
    CreationStep,
    IdentityStep,
    SelectionStep,
    SkillSelectionStep,
    SpellSelectionStep,
    StepConfigurationError,
)
from companion4soloplayer.core.creation.strategies import ConstantStrategy

#: Minimal game system used by the tests.
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
# IdentityStep
# ----------------------------------------------------------------------


def test_identity_describes_name_and_background() -> None:
    """The name is a text field, the background a multi-line text area."""
    fields = IdentityStep().describe_inputs(make_context())
    assert [field.kind for field in fields] == [InputKind.TEXT, InputKind.TEXTAREA]
    assert [field.key for field in fields] == ["identity.name", "identity.background"]
    assert fields[0].label == "Character name"
    assert fields[0].required is True
    assert fields[1].required is False


def test_identity_background_becomes_a_choice_with_options() -> None:
    """A background list turns the second field into a choice."""
    step = IdentityStep(background_options=["Sellsword", "Noble"], background_required=True)
    fields = step.describe_inputs(make_context())
    assert fields[1].kind is InputKind.CHOICE
    assert fields[1].options == ("Sellsword", "Noble")
    assert fields[1].required is True


# ----------------------------------------------------------------------
# SelectionStep
# ----------------------------------------------------------------------


def test_selection_describes_one_single_choice_field() -> None:
    """The catalog becomes the option list of one CHOICE field."""
    step = SelectionStep(
        "race",
        target="choices.race",
        catalog="races",
        prompt="Choose a race",
        optional=True,
    )
    fields = step.describe_inputs(make_context())
    assert len(fields) == 1
    field = fields[0]
    assert field.key == "race"
    assert field.label == "Choose a race"
    assert field.kind is InputKind.CHOICE
    assert field.options == ("Dwarf", "Elf")
    assert field.required is False


def test_selection_without_catalog_describes_nothing() -> None:
    """A game system without such data describes no field."""
    step = SelectionStep("race", target="choices.race", catalog="races")
    assert step.describe_inputs(make_context(races=None)) == ()


# ----------------------------------------------------------------------
# AttributeGenerationStep
# ----------------------------------------------------------------------


def test_random_attributes_describe_dice_fields() -> None:
    """Each generated attribute gets a bounded DICE field with a roll."""
    step = AttributeGenerationStep(strategy="fixed", min_value=3, max_value=18)
    fields = step.describe_inputs(make_context())
    assert [field.kind for field in fields] == [InputKind.DICE, InputKind.DICE]
    assert [field.key for field in fields] == ["attributes.strength", "attributes.charm"]
    assert [field.label for field in fields] == ["strength", "charm"]
    assert all(field.roll is not None for field in fields)
    assert fields[0].min_value == 3
    assert fields[0].max_value == 18


def test_manual_attributes_describe_number_fields() -> None:
    """A manually entered attribute is a plain NUMBER field."""
    step = AttributeGenerationStep(mode="manual", strategy="fixed")
    fields = step.describe_inputs(make_context())
    assert [field.kind for field in fields] == [InputKind.NUMBER, InputKind.NUMBER]
    assert all(field.roll is None for field in fields)


def test_mixed_mode_describes_both_kinds() -> None:
    """The manual attributes and the rolled ones coexist in a mixed step."""
    step = AttributeGenerationStep(mode="mixed", manual_attributes=("charm",), strategy="fixed")
    fields = step.describe_inputs(make_context())
    assert [field.kind for field in fields] == [InputKind.DICE, InputKind.NUMBER]


def test_attributes_without_system_attributes_describe_nothing() -> None:
    """A system declaring no attribute describes no field."""
    step = AttributeGenerationStep(strategy="fixed")
    assert step.describe_inputs(make_context(attributes=None)) == ()


# ----------------------------------------------------------------------
# SkillSelectionStep
# ----------------------------------------------------------------------


def test_free_skills_describe_one_multiple_choice_field() -> None:
    """A free skill step describes one bounded CHOICES field."""
    step = SkillSelectionStep(mode="free", min_count=2, max_count=4, prompt="Pick skills")
    fields = step.describe_inputs(make_context())
    assert len(fields) == 1
    field = fields[0]
    assert field.key == "skills"
    assert field.kind is InputKind.CHOICES
    assert field.label == "Pick skills"
    assert field.options == ("Athletics", "Stealth")
    assert (field.required, field.min_count, field.max_count) == (True, 2, 4)


def test_inherited_and_missing_skills_describe_nothing() -> None:
    """Inherited/none modes and a missing catalog describe no field."""
    assert SkillSelectionStep(mode="inherited").describe_inputs(make_context()) == ()
    assert SkillSelectionStep(mode="none").describe_inputs(make_context()) == ()
    assert SkillSelectionStep().describe_inputs(make_context(skills=None)) == ()


# ----------------------------------------------------------------------
# SpellSelectionStep
# ----------------------------------------------------------------------


def level_one(spell: Mapping[str, Any], context: CharacterCreationContext) -> bool:
    """Keep the first-level spells only (test filter).

    Args:
        spell: Spell catalog entry.
        context: Current creation state (unused).

    Returns:
        True for a level 1 spell.
    """
    return int(spell.get("level", 1)) == 1


def test_chosen_spells_describe_a_filtered_multiple_choice() -> None:
    """Only the spells passing the filter are offered."""
    step = SpellSelectionStep(
        mode="choice",
        max_count=2,
        prompt="Pick spells",
        spell_filter=level_one,
    )
    fields = step.describe_inputs(make_context())
    assert len(fields) == 1
    field = fields[0]
    assert field.kind is InputKind.CHOICES
    assert field.label == "Pick spells"
    assert field.options == ("Light",)  # the level 2 spell is filtered out
    assert field.required is False
    assert field.max_count == 2


def test_automatic_spells_describe_nothing() -> None:
    """An automatic spell attribution asks nothing."""
    assert SpellSelectionStep(mode="auto").describe_inputs(make_context()) == ()


# ----------------------------------------------------------------------
# Default implementation
# ----------------------------------------------------------------------


def test_custom_step_describes_nothing_by_default() -> None:
    """A plugin-specific step inherits the empty description."""

    class CustomStep(CreationStep):
        def is_applicable(self, context: CharacterCreationContext) -> bool:
            return True

        def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
            return None

        def validate(self, context: CharacterCreationContext) -> list[str]:
            return []

    assert CustomStep("custom").describe_inputs(make_context()) == ()


# ----------------------------------------------------------------------
# AttributeGenerationStep and provider answers
# ----------------------------------------------------------------------


def test_random_attribute_uses_the_answer_of_the_provider() -> None:
    """A recorded dice answer wins; the strategy stays the fallback."""
    step = AttributeGenerationStep(strategy="fixed")
    context = make_context()
    step.execute(context, MappingInputProvider({"attributes.strength": 15}))
    assert context.get("values.attributes.strength") == 15
    assert context.get("values.attributes.charm") == 12


def test_random_attribute_answer_is_checked_against_the_bounds() -> None:
    """An out-of-bounds rolled value fails the step."""
    step = AttributeGenerationStep(strategy="fixed", min_value=3, max_value=18)
    with pytest.raises(InvalidAnswerError):
        step.execute(make_context(), MappingInputProvider({"attributes.strength": 99}))


def test_random_attribute_without_strategy_reports_a_configuration_error() -> None:
    """No strategy and no answer means the step is misconfigured."""
    with pytest.raises(StepConfigurationError, match="strategy"):
        AttributeGenerationStep().execute(make_context(), MappingInputProvider({}))


def test_manual_attribute_missing_answer_still_fails() -> None:
    """A manual attribute with no answer raises the input error."""
    step = AttributeGenerationStep(mode="manual", strategy="fixed")
    with pytest.raises(MissingInputError):
        step.execute(make_context(), MappingInputProvider({}))


def test_roll_attribute_returns_a_strategy_value() -> None:
    """roll_attribute resolves the strategy by name from the system."""
    step = AttributeGenerationStep(strategy="fixed")
    assert step.roll_attribute("strength", make_context()) == 12
    unknown = AttributeGenerationStep(strategy="unknown")
    with pytest.raises(StepConfigurationError, match="unknown"):
        unknown.roll_attribute("strength", make_context())
