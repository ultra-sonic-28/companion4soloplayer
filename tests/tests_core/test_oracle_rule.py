"""Tests for the shared oracle rule element (``core.rules``)."""

from companion4soloplayer.core.dice_roller import DiceRoller
from companion4soloplayer.core.rules import OracleRule
from companion4soloplayer.core.rules.oracle_rule import OracleRule as OracleRuleImpl


def test_oracle_exported_by_core_rules_is_the_implementation() -> None:
    """``core.rules.OracleRule`` re-exports the class of its own module."""
    assert OracleRule is OracleRuleImpl


def test_oracle_answers_a_known_outcome() -> None:
    """The default 1d6 oracle answers one of the documented outcomes."""
    oracle = OracleRule()
    assert oracle.ask() in set(OracleRule.OUTCOMES.values())


def test_oracle_accepts_dice_notation() -> None:
    """The oracle accepts any dice expression (kept within 1..6 outcomes)."""
    oracle = OracleRule(dice="2d6")
    answer = oracle.ask(DiceRoller())
    assert answer in set(OracleRule.OUTCOMES.values())


def test_oracle_outcome_table_is_complete() -> None:
    """Every face of the die maps to an outcome with a yes/no answer."""
    assert sorted(OracleRule.OUTCOMES) == [1, 2, 3, 4, 5, 6]
    assert all(outcome.startswith(("yes", "no")) for outcome in OracleRule.OUTCOMES.values())
