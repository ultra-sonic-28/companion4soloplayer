"""Tests for the Condition/Effect rule engine of the creation flow."""

from pathlib import Path
from typing import Any

import pytest

from companion4soloplayer.core.creation.context import CharacterCreationContext
from companion4soloplayer.core.creation.rules import (
    Action,
    Condition,
    CreationRule,
    Effect,
    Operator,
    RuleDefinitionError,
    RuleEvaluationError,
    RulesEngine,
    load_creation_rules,
)


def make_context(**values: Any) -> CharacterCreationContext:
    """Build a context with ``values.attributes.x`` shortcuts set.

    Args:
        **values: Attribute values stored under
            ``values.attributes``.

    Returns:
        The prepared context.
    """
    context = CharacterCreationContext()
    for name, value in values.items():
        context.set(f"values.attributes.{name}", value)
    return context


# ----------------------------------------------------------------------
# Operator / Action parsing
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("eq", Operator.EQ),
        ("NE", Operator.NE),
        ("==", Operator.EQ),
        (">=", Operator.GE),
        ("<", Operator.LT),
        ("contains", Operator.CONTAINS),
    ],
)
def test_operator_parse_accepts_names_and_symbols(raw: str, expected: Operator) -> None:
    """Operators parse from names (case-insensitive) and symbols."""
    assert Operator.parse(raw) is expected


def test_operator_parse_rejects_unknown() -> None:
    """An unknown operator raises an explicit error."""
    with pytest.raises(RuleDefinitionError, match="Unknown condition operator"):
        Operator.parse("approximately")


@pytest.mark.parametrize("raw", ["add", "SET", "grant", "remove", "mul"])
def test_action_parse_accepts_known_actions(raw: str) -> None:
    """Known actions parse case-insensitively."""
    assert isinstance(Action.parse(raw), Action)


def test_action_parse_rejects_unknown() -> None:
    """An unknown action raises an explicit error."""
    with pytest.raises(RuleDefinitionError, match="Unknown effect action"):
        Action.parse("teleport")


# ----------------------------------------------------------------------
# Conditions
# ----------------------------------------------------------------------


def test_condition_from_dict_parses_entries() -> None:
    """A condition parses target, operator and value."""
    condition = Condition.from_dict({"target": "choices.race", "operator": "==", "value": "Dwarf"})
    assert condition.target == "choices.race"
    assert condition.operator is Operator.EQ
    assert condition.value == "Dwarf"
    assert "choices.race" in condition.describe()


@pytest.mark.parametrize(
    "data",
    [
        {"operator": "eq", "value": 1},
        {"target": "choices.race", "value": 1},
        {"target": "choices.race", "operator": "eq", "typo": 1},
        {"target": "race", "operator": "eq"},
        {"target": "choices.race", "operator": "wat"},
        {"target": "choices.race", "operator": "in", "value": "Dwarf"},
        "not-a-mapping",
    ],
)
def test_condition_from_dict_rejects_malformed_payloads(data: Any) -> None:
    """Malformed condition documents raise an explicit error."""
    with pytest.raises(RuleDefinitionError):
        Condition.from_dict(data)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("operator", "value", "expected"),
    [
        (Operator.EQ, "Dwarf", True),
        (Operator.EQ, "Elf", False),
        (Operator.NE, "Elf", True),
        (Operator.IN, ["Dwarf", "Elf"], True),
        (Operator.IN, ["Human"], False),
        (Operator.NOT_IN, ["Human"], True),
    ],
)
def test_condition_text_operators(operator: Operator, value: Any, expected: bool) -> None:
    """Text comparisons evaluate against the effective value."""
    context = CharacterCreationContext()
    context.set("choices.race", "Dwarf")
    condition = Condition(target="choices.race", operator=operator, value=value)
    assert condition.evaluate(context) is expected


@pytest.mark.parametrize(
    ("operator", "value", "expected"),
    [
        (Operator.GT, 12, True),
        (Operator.GT, 13, False),
        (Operator.GE, 13, True),
        (Operator.LT, 14, True),
        (Operator.LE, 13, True),
    ],
)
def test_condition_numeric_operators(operator: Operator, value: int, expected: bool) -> None:
    """Numeric comparisons evaluate against the effective value."""
    context = make_context(strength=13)
    condition = Condition(target="values.attributes.strength", operator=operator, value=value)
    assert condition.evaluate(context) is expected


def test_condition_numeric_on_missing_value_is_false() -> None:
    """A not-yet-computed value makes the comparison simply false."""
    context = CharacterCreationContext()
    condition = Condition(target="values.attributes.strength", operator=Operator.GE, value=10)
    assert condition.evaluate(context) is False


def test_condition_numeric_on_text_raises() -> None:
    """Comparing a text with a number raises an evaluation error."""
    context = CharacterCreationContext()
    context.set("values.attributes.strength", "high")
    condition = Condition(target="values.attributes.strength", operator=Operator.GT, value=10)
    with pytest.raises(RuleEvaluationError, match="Numeric comparison"):
        condition.evaluate(context)


def test_condition_exists_and_empty_operators() -> None:
    """Existence and emptiness operators work on absent and empty data."""
    context = CharacterCreationContext()
    context.set("values.spells", [])
    context.set("choices.race", None)
    assert Condition("choices.race", Operator.EXISTS).evaluate(context) is False
    assert Condition("choices.race", Operator.NOT_EXISTS).evaluate(context) is True
    assert Condition("values.spells", Operator.EMPTY).evaluate(context) is True
    assert Condition("values.spells", Operator.NOT_EMPTY).evaluate(context) is False
    context.set("values.spells", ["Light"])
    assert Condition("values.spells", Operator.NOT_EMPTY).evaluate(context) is True


@pytest.mark.parametrize(
    ("operator", "expected"),
    [(Operator.CONTAINS, True), (Operator.NOT_CONTAINS, False)],
)
def test_condition_contains_on_lists(operator: Operator, expected: bool) -> None:
    """Collection membership is tested on effective lists."""
    context = CharacterCreationContext()
    context.record("values.skills", Effect("values.skills", Action.GRANT, "Stealth"))
    condition = Condition(target="values.skills", operator=operator, value="Stealth")
    assert condition.evaluate(context) is expected


def test_condition_contains_on_absent_value_is_false() -> None:
    """Contains on a missing value never matches and never raises."""
    context = CharacterCreationContext()
    assert Condition("values.skills", Operator.CONTAINS, "Stealth").evaluate(context) is False


def test_condition_contains_on_opaque_type_raises() -> None:
    """Contains on a non-searchable value raises an evaluation error."""
    context = CharacterCreationContext()
    context.set("values.level", 3)
    with pytest.raises(RuleEvaluationError, match="contains"):
        Condition("values.level", Operator.CONTAINS, 1).evaluate(context)


# ----------------------------------------------------------------------
# Effects
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "value", "base", "expected"),
    [
        (Action.ADD, 2, 10, 12),
        (Action.SUB, 2, 10, 8),
        (Action.MUL, 3, 5, 15),
        (Action.ADD, 2, None, 2),
        (Action.SET, "Dwarf", "Elf", "Dwarf"),
        (Action.GRANT, "Stealth", ["Athletics"], ["Athletics", "Stealth"]),
        (Action.GRANT, "Stealth", ["Stealth"], ["Stealth"]),
        (Action.GRANT, "Stealth", None, ["Stealth"]),
        (Action.REMOVE, "Stealth", ["Athletics", "Stealth"], ["Athletics"]),
        (Action.REMOVE, "Stealth", None, []),
    ],
)
def test_effect_apply_to(action: Action, value: Any, base: Any, expected: Any) -> None:
    """Each action computes the new effective value."""
    effect = Effect(target="values.data", action=action, value=value)
    assert effect.apply_to(base) == expected


def test_effect_grant_does_not_mutate_the_base_list() -> None:
    """Grant returns a copy: the stored base list stays untouched."""
    base = ["Athletics"]
    effect = Effect(target="values.skills", action=Action.GRANT, value="Stealth")
    assert effect.apply_to(base) == ["Athletics", "Stealth"]
    assert base == ["Athletics"]


@pytest.mark.parametrize(
    ("action", "value", "base"),
    [
        (Action.ADD, 2, "text"),
        (Action.SUB, "x", 3),
        (Action.GRANT, "Stealth", 3),
        (Action.REMOVE, "Stealth", "text"),
    ],
)
def test_effect_apply_to_rejects_incompatible_types(action: Action, value: Any, base: Any) -> None:
    """Applying an action to an incompatible base raises an error."""
    effect = Effect(target="values.data", action=action, value=value)
    with pytest.raises(RuleEvaluationError):
        effect.apply_to(base)


def test_effect_from_dict_rejects_malformed_payloads() -> None:
    """Malformed effect documents raise an explicit error."""
    with pytest.raises(RuleDefinitionError):
        Effect.from_dict({"target": "values.x", "action": "nope"})
    with pytest.raises(RuleDefinitionError):
        Effect.from_dict({"target": "values", "action": "add"})
    with pytest.raises(RuleDefinitionError):
        Effect.from_dict({"action": "add"})
    with pytest.raises(RuleDefinitionError):
        Effect.from_dict({"target": "values.x", "action": "add", "typo": 1})


# ----------------------------------------------------------------------
# Creation rules and engine
# ----------------------------------------------------------------------


def dwarf_rule() -> CreationRule:
    """Build the reference "if Race=Dwarf then +2 constitution" rule."""
    return CreationRule.from_dict(
        {
            "id": "dwarf_hardy",
            "description": "Dwarves are hardy.",
            "when": [{"target": "choices.race", "operator": "eq", "value": "Dwarf"}],
            "effects": [{"target": "values.attributes.constitution", "action": "add", "value": 2}],
        }
    )


def test_rule_from_dict_defaults_and_matches() -> None:
    """Missing id/description get defaults; 'when' may be omitted."""
    rule = CreationRule.from_dict(
        {"effects": [{"target": "values.hp", "action": "add", "value": 1}]},
        index=4,
    )
    assert rule.id == "rule_5"
    assert rule.when == ()
    assert rule.matches(CharacterCreationContext()) is True


@pytest.mark.parametrize(
    "data",
    [
        "not-a-mapping",
        {"effects": "not-a-list"},
        {"effects": []},
        {"effects": [{"target": "values.hp", "action": "add", "value": 1}], "typo": 1},
        {"effects": [{"target": "values.hp", "action": "add", "value": 1}], "when": 42},
        {"effects": [{"target": "values.hp", "action": "add", "value": 1}], "id": ""},
        {"effects": [42]},
    ],
)
def test_rule_from_dict_rejects_malformed_payloads(data: Any) -> None:
    """Malformed rule documents raise an explicit error."""
    with pytest.raises(RuleDefinitionError):
        CreationRule.from_dict(data)  # type: ignore[arg-type]


def test_engine_applies_rule_and_reports_it() -> None:
    """A matching rule records its effects and appears in the report."""
    context = CharacterCreationContext()
    context.set("choices.race", "Dwarf")
    engine = RulesEngine([dwarf_rule()])
    report = engine.evaluate(context)
    assert report.fired == ("dwarf_hardy",)
    assert report.applied_effects == 1
    assert context.effective("values.attributes.constitution") == 2


def test_engine_evaluation_is_idempotent() -> None:
    """Evaluating twice rebuilds the same result, never doubling it."""
    context = CharacterCreationContext()
    context.set("choices.race", "Dwarf")
    context.set("values.attributes.constitution", 10)
    engine = RulesEngine([dwarf_rule()])
    engine.evaluate(context)
    engine.evaluate(context)
    assert context.effective("values.attributes.constitution") == 12


def test_engine_sees_previous_rules_of_the_same_pass() -> None:
    """Rules chain in declaration order within one evaluation."""
    context = CharacterCreationContext()
    context.set("values.attributes.constitution", 12)
    engine = RulesEngine(
        [
            CreationRule(
                id="first",
                effects=(Effect("values.attributes.constitution", Action.ADD, 2),),
            ),
            CreationRule(
                id="second",
                when=(Condition("values.attributes.constitution", Operator.GE, 14),),
                effects=(Effect("values.hit_points", Action.ADD, 1),),
            ),
        ]
    )
    report = engine.evaluate(context)
    assert report.fired == ("first", "second")
    assert context.effective("values.hit_points") == 1


def test_engine_rejects_duplicate_rule_ids() -> None:
    """Two rules cannot share the same identifier."""
    with pytest.raises(RuleDefinitionError, match="Duplicate rule id"):
        RulesEngine([dwarf_rule(), dwarf_rule()])


def test_engine_add_rejects_duplicates() -> None:
    """Adding a rule with an existing id raises."""
    engine = RulesEngine([dwarf_rule()])
    with pytest.raises(RuleDefinitionError):
        engine.add(dwarf_rule())
    assert len(engine.rules) == 1


def test_load_creation_rules_from_yaml(tmp_path: Path) -> None:
    """Rules load from a 'rules:' document or a bare sequence."""
    document = tmp_path / "rules.yaml"
    document.write_text(
        "rules:\n"
        "  - id: sturdy\n"
        "    when:\n"
        "      - target: values.attributes.constitution\n"
        "        operator: ge\n"
        "        value: 14\n"
        "    effects:\n"
        "      - target: values.hit_points\n"
        "        action: add\n"
        "        value: 2\n",
        encoding="utf-8",
    )
    rules = load_creation_rules(document)
    assert [rule.id for rule in rules] == ["sturdy"]
    assert rules[0].when[0].operator is Operator.GE

    bare = tmp_path / "bare.yaml"
    bare.write_text(
        "- effects:\n" "    - target: values.hit_points\n" "      action: add\n" "      value: 1\n",
        encoding="utf-8",
    )
    assert [rule.id for rule in load_creation_rules(bare)] == ["rule_1"]


def test_load_creation_rules_rejects_invalid_documents(tmp_path: Path) -> None:
    """Documents without a rules sequence are rejected explicitly."""
    missing = tmp_path / "missing.yaml"
    missing.write_text("combat: {}\n", encoding="utf-8")
    with pytest.raises(RuleDefinitionError, match="rules"):
        load_creation_rules(missing)

    scalar = tmp_path / "scalar.yaml"
    scalar.write_text("42\n", encoding="utf-8")
    with pytest.raises(RuleDefinitionError, match="mapping or a sequence"):
        load_creation_rules(scalar)
