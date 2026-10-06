"""Tests for the core dice expression value (``core.dice_expression``)."""

import pytest

from companion4soloplayer.core.dice_expression import DiceExpression, DiceExpressionError
from companion4soloplayer.core.dice_roller import DiceRoller


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2d6", DiceExpression(2, 6, 0)),
        ("1d20+3", DiceExpression(1, 20, 3)),
        ("d6-1", DiceExpression(1, 6, -1)),
        ("D100", DiceExpression(1, 100, 0)),
    ],
)
def test_parse_notations(text: str, expected: DiceExpression) -> None:
    """Dice notations are parsed into typed values."""
    assert DiceExpression.parse(text) == expected


def test_parse_passes_through_parsed_values() -> None:
    """An already parsed expression is returned unchanged."""
    expr = DiceExpression(3, 8, -2)
    assert DiceExpression.parse(expr) is expr


@pytest.mark.parametrize("text", ["2x6", "2d", "0d6", "1d1", "d6+", "", "  "])
def test_parse_rejects_invalid_notation(text: str) -> None:
    """Invalid dice notations raise an explicit error."""
    with pytest.raises(DiceExpressionError, match="Invalid dice notation"):
        DiceExpression.parse(text)


def test_dice_expression_error_is_a_value_error() -> None:
    """The error stays compatible with generic ValueError handlers."""
    assert issubclass(DiceExpressionError, ValueError)


def test_notation_is_canonical() -> None:
    """The canonical notation round-trips through parse()."""
    assert DiceExpression(2, 6, 0).notation == "2d6"
    assert str(DiceExpression(2, 6, 0)) == "2d6"
    assert DiceExpression(1, 20, 3).notation == "1d20+3"
    assert DiceExpression.parse("d6-1").notation == "1d6-1"


def test_roll_returns_total_including_modifier() -> None:
    """roll() adds the modifier to the dice results."""
    total = DiceExpression(2, 6, 1).roll(DiceRoller())
    assert 3 <= total <= 13


def test_roll_detail_reports_results_and_total() -> None:
    """roll_detail() returns the individual results and their modified sum."""
    results, total = DiceExpression(3, 8, -2).roll_detail(DiceRoller())
    assert len(results) == 3
    assert all(1 <= result <= 8 for result in results)
    assert total == sum(results) - 2


def test_roll_without_roller_uses_a_fresh_roller() -> None:
    """A missing roller is created on the fly."""
    assert DiceExpression(1, 6).roll() in range(1, 7)
