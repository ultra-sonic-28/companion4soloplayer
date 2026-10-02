"""Tests for the core YAML loader and its custom tags."""

from pathlib import Path

import pytest
import yaml

from companion4soloplayer.core.dice_roller import DiceRoller
from companion4soloplayer.core.yaml_loader import (
    C4SPSafeLoader,
    DiceExpression,
    PyClassRef,
    YamlLoadError,
    YamlTagError,
    load_yaml,
    load_yaml_file,
    register_tag,
)


def test_load_basic_document_with_comments() -> None:
    """Comments are ignored and plain data is typed natively."""
    doc = load_yaml("""
        # leading comment
        name: test
        count: 3
        enabled: true
        items: [a, b]
        """)
    assert doc == {"name": "test", "count": 3, "enabled": True, "items": ["a", "b"]}


def test_pyclass_scalar_form() -> None:
    """The scalar form parses 'module:Class' without importing anything."""
    ref = load_yaml("impl: !pyclass companion4soloplayer.core.dice_roller:DiceRoller")["impl"]
    assert isinstance(ref, PyClassRef)
    assert ref.module == "companion4soloplayer.core.dice_roller"
    assert ref.attr == "DiceRoller"
    assert not ref.is_local


@pytest.mark.parametrize("path", ["local:Thing", ":Thing"])
def test_pyclass_local_forms(path: str) -> None:
    """'local:Class' and ':Class' both target the declaring module."""
    ref = PyClassRef.parse(path)
    assert ref.is_local
    assert ref.module == "local"
    assert ref.attr == "Thing"


def test_pyclass_mapping_form_with_nested_params() -> None:
    """The mapping form carries constructor params, including !dice."""
    doc = load_yaml("""
        impl: !pyclass
          path: local:CombatRule
          params:
            attack_dice: !dice 2d6
            base_damage: 2
        """)
    ref = doc["impl"]
    assert isinstance(ref, PyClassRef)
    assert ref.path == "local:CombatRule"
    assert isinstance(ref.params["attack_dice"], DiceExpression)
    assert (ref.params["attack_dice"].count, ref.params["attack_dice"].sides) == (2, 6)
    assert ref.params["base_damage"] == 2


def test_pyclass_rejects_unknown_keys() -> None:
    """Unknown keys in the mapping form raise an explicit error."""
    with pytest.raises(YamlTagError):
        load_yaml("impl: !pyclass {path: local:A, oops: 1}")


def test_pyclass_rejects_invalid_reference() -> None:
    """Malformed references raise an explicit error."""
    with pytest.raises(YamlTagError):
        load_yaml("impl: !pyclass not_a_reference")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2d6", DiceExpression(2, 6, 0)),
        ("1d20+3", DiceExpression(1, 20, 3)),
        ("d6-1", DiceExpression(1, 6, -1)),
    ],
)
def test_dice_parse_notations(text: str, expected: DiceExpression) -> None:
    """Dice notations are parsed into typed values."""
    assert DiceExpression.parse(text) == expected


def test_dice_parse_rejects_invalid_notation() -> None:
    """Invalid dice notations raise an explicit error."""
    with pytest.raises(YamlTagError):
        DiceExpression.parse("2x6")


def test_dice_tag_and_roll() -> None:
    """The !dice tag yields a rollable expression."""
    expr = load_yaml("pool: !dice 2d6")["pool"]
    assert isinstance(expr, DiceExpression)
    results, total = expr.roll_detail(DiceRoller())
    assert len(results) == 2
    assert sum(results) == total
    assert expr.notation == "2d6"


def test_unsafe_python_tags_are_rejected() -> None:
    """!!python tags stay forbidden with the safe loader."""
    with pytest.raises(yaml.YAMLError):
        load_yaml("!!python/object/apply:os.system ['echo pwned']")


def test_unknown_custom_tag_is_rejected() -> None:
    """Tags without a registered constructor raise a parser error."""
    with pytest.raises(yaml.YAMLError):
        load_yaml("value: !unknown_tag 42")


def test_load_yaml_file_reports_path(tmp_path: Path) -> None:
    """Parse errors include the offending file path."""
    broken = tmp_path / "broken.yaml"
    broken.write_text("key: [unclosed", encoding="utf-8")
    with pytest.raises(YamlLoadError) as excinfo:
        load_yaml_file(broken)
    assert str(broken) in str(excinfo.value)


def test_load_yaml_file_missing_file(tmp_path: Path) -> None:
    """A missing file raises OSError."""
    with pytest.raises(FileNotFoundError):
        load_yaml_file(tmp_path / "does_not_exist.yaml")


def test_load_yaml_file_success(tmp_path: Path) -> None:
    """A valid file is parsed like its inline counterpart."""
    path = tmp_path / "data.yaml"
    path.write_text("# comment\nvalue: 42\n", encoding="utf-8")
    assert load_yaml_file(path) == {"value": 42}


def test_register_tag_extends_the_loader() -> None:
    """Plugins may register additional safe tags."""
    try:
        register_tag("!test_tag", lambda loader, node: f"custom:{loader.construct_scalar(node)}")
        assert load_yaml("v: !test_tag hello")["v"] == "custom:hello"
    finally:
        C4SPSafeLoader.yaml_constructors.pop("!test_tag", None)


def test_register_tag_requires_bang_prefix() -> None:
    """Tag names must start with '!'; the loader registry stays untouched."""
    with pytest.raises(ValueError, match="start with"):
        register_tag("no_bang", lambda loader, node: None)
