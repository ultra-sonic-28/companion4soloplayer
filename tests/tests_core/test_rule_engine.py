"""Tests for the hybrid rule engine (YAML declarations + Python classes)."""

from pathlib import Path

import pytest

from companion4soloplayer.core.dice_roller import DiceRoller
from companion4soloplayer.core.rule_engine import (
    RULE_KINDS,
    ImplementationError,
    ImplementationNotAllowedError,
    RuleEngine,
    RuleEngineError,
    UnknownRuleKindError,
)
from companion4soloplayer.core.yaml_loader import PyClassRef, load_yaml


class Widget:
    """Test component accepting constructor parameters."""

    def __init__(self, size: int = 1) -> None:
        self.size = size


def test_standard_rule_kinds() -> None:
    """The standard kinds cover the expected rule elements."""
    assert set(RULE_KINDS) >= {"character_creation", "combat", "loot", "magic", "oracle"}


def test_component_from_local_reference() -> None:
    """'local:' references resolve inside the declaring module."""
    engine = RuleEngine(
        load_yaml("""implementations:
  widget: !pyclass local:Widget
"""),
        base_module=__name__,
    )
    widget = engine.component("widget")
    assert isinstance(widget, Widget)
    assert widget.size == 1


def test_component_is_cached() -> None:
    """A rule kind is instantiated only once."""
    engine = RuleEngine({"implementations": {"widget": "local:Widget"}}, base_module=__name__)
    assert engine.component("widget") is engine.component("widget")


def test_component_params_from_yaml() -> None:
    """Constructor params declared in YAML are forwarded to the class."""
    engine = RuleEngine(
        load_yaml("""
            implementations:
              widget: !pyclass
                path: local:Widget
                params:
                  size: 5
            """),
        base_module=__name__,
    )
    assert engine.component("widget").size == 5


def test_absolute_reference_within_allow_list() -> None:
    """Absolute references to allowed modules are imported on demand."""
    engine = RuleEngine(
        {"implementations": {"roller": "companion4soloplayer.core.dice_roller:DiceRoller"}}
    )
    assert isinstance(engine.component("roller"), DiceRoller)


def test_reference_outside_allow_list_is_rejected() -> None:
    """Modules outside the allow-list are refused before any import."""
    engine = RuleEngine({"implementations": {"bad": PyClassRef(path="os:system")}})
    with pytest.raises(ImplementationNotAllowedError):
        engine.component("bad")


def test_unknown_rule_kind_raises() -> None:
    """Undeclared kinds raise an explicit error listing what exists."""
    engine = RuleEngine({"implementations": {"widget": "local:Widget"}}, base_module=__name__)
    with pytest.raises(UnknownRuleKindError):
        engine.component("combat")


def test_local_reference_without_base_module_raises() -> None:
    """A 'local:' reference requires the declaring module."""
    engine = RuleEngine({"implementations": {"widget": "local:Widget"}})
    with pytest.raises(ImplementationError):
        engine.component("widget")


def test_non_callable_reference_raises() -> None:
    """References must resolve to something instantiable."""
    engine = RuleEngine(
        {"implementations": {"bad": "companion4soloplayer.core.rule_engine:RULE_KINDS"}}
    )
    with pytest.raises(ImplementationError):
        engine.component("bad")


def test_non_mapping_rules_rejected() -> None:
    """The rules document must be a mapping."""
    with pytest.raises(RuleEngineError):
        RuleEngine([])  # type: ignore[arg-type]


def test_implementations_must_be_references() -> None:
    """Non-reference implementation values raise an explicit error."""
    engine = RuleEngine({"implementations": {"bad": 42}})
    with pytest.raises(RuleEngineError):
        _ = engine.implementations


def test_rules_property_returns_a_copy() -> None:
    """Callers cannot corrupt the engine by mutating the returned dict."""
    engine = RuleEngine({"combat": {"steps": []}}, base_module=__name__)
    rules = engine.rules
    rules["combat"] = None
    assert engine.get("combat") == {"steps": []}


def test_kinds_are_sorted() -> None:
    """The kinds property lists declared kinds alphabetically."""
    engine = RuleEngine(
        {"implementations": {"widget": "local:Widget", "oracle": "local:Widget"}},
        base_module=__name__,
    )
    assert engine.kinds == ["oracle", "widget"]


def test_from_yaml(tmp_path: Path) -> None:
    """The engine can be built directly from a rules file."""
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        "implementations:\n  widget: !pyclass\n    path: local:Widget\n"
        "    params:\n      size: 7\n",
        encoding="utf-8",
    )
    engine = RuleEngine.from_yaml(rules, base_module=__name__)
    assert engine.component("widget").size == 7


def test_from_yaml_empty_file(tmp_path: Path) -> None:
    """An empty rules file raises an explicit error."""
    rules = tmp_path / "rules.yaml"
    rules.write_text("# nothing here\n", encoding="utf-8")
    with pytest.raises(RuleEngineError):
        RuleEngine.from_yaml(rules, base_module=__name__)
