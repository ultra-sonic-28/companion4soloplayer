"""Tests for the character creation state container."""

from typing import Any

import pytest

from companion4soloplayer.core.creation.context import (
    CharacterCreationContext,
    InvalidPathError,
    parse_path,
)


class AddOne:
    """Minimal operation stub recording its application."""

    def __init__(self) -> None:
        self.calls = 0

    def apply_to(self, base: Any) -> Any:
        """Add one to a numeric base (None counts as 0)."""
        self.calls += 1
        return (0 if base is None else base) + 1


def test_parse_path_splits_valid_path() -> None:
    """A dotted path splits into namespace + segments."""
    assert parse_path("values.attributes.strength") == ("values", "attributes", "strength")
    assert parse_path("choices.race") == ("choices", "race")


@pytest.mark.parametrize(
    "path",
    ["", "race", "choices..name", "other.x", " ", 42],
)
def test_parse_path_rejects_invalid_paths(path: Any) -> None:
    """A malformed path raises an explicit error."""
    with pytest.raises(InvalidPathError):
        parse_path(path)  # type: ignore[arg-type]


def test_set_and_get_roundtrip() -> None:
    """Values are written and read back through dotted paths."""
    context = CharacterCreationContext()
    context.set("choices.identity.name", "Aria")
    assert context.get("choices.identity.name") == "Aria"
    assert context.peek("choices.identity.name") == "Aria"
    assert context.has("choices.identity.name")
    assert context.choices["identity"]["name"] == "Aria"


def test_get_missing_path_raises_key_error() -> None:
    """Reading an absent path raises KeyError, peek returns the default."""
    context = CharacterCreationContext()
    with pytest.raises(KeyError):
        context.get("choices.race")
    assert context.peek("choices.race") is None
    assert context.peek("choices.race", "none") == "none"
    assert not context.has("choices.race")


def test_set_rejects_namespace_only_path() -> None:
    """Writing a whole namespace is refused: a leaf path is required."""
    context = CharacterCreationContext()
    with pytest.raises(InvalidPathError):
        context.set("choices", {})


def test_set_rejects_path_through_scalar() -> None:
    """Writing below a scalar value raises an explicit error."""
    context = CharacterCreationContext()
    context.set("choices.race", "Dwarf")
    with pytest.raises(InvalidPathError):
        context.set("choices.race.name", "Gruff")


def test_effective_folds_operations_in_order() -> None:
    """The effective value is the base with every operation applied."""
    context = CharacterCreationContext()
    context.set("values.hit_points", 5)
    operation = AddOne()
    context.record("values.hit_points", operation)
    context.record("values.hit_points", AddOne())
    assert context.effective("values.hit_points") == 7
    assert operation.calls == 1


def test_effective_on_missing_path_starts_from_default() -> None:
    """Operations apply even when the base value does not exist yet."""
    context = CharacterCreationContext()
    context.record("values.hit_points", AddOne())
    context.record("values.other", AddOne())
    assert context.effective("values.hit_points") == 1
    assert context.effective("values.other", 10) == 11
    assert context.effective("values.absent") is None


def test_begin_evaluation_clears_operations() -> None:
    """A new evaluation starts from a clean slate (idempotence)."""
    context = CharacterCreationContext()
    context.record("values.hit_points", AddOne())
    assert context.effective("values.hit_points") == 1
    context.begin_evaluation()
    assert context.operations == {}
    assert context.effective("values.hit_points") is None


def test_record_rejects_namespace_only_path() -> None:
    """An effect must target a leaf path."""
    context = CharacterCreationContext()
    with pytest.raises(InvalidPathError):
        context.record("values", AddOne())


def test_operations_property_is_read_only() -> None:
    """The operations snapshot cannot be mutated by callers."""
    context = CharacterCreationContext()
    context.record("values.hit_points", AddOne())
    operations = context.operations
    with pytest.raises(TypeError):
        operations["values.hit_points"] = ()  # type: ignore[index]


def test_export_applies_effective_values_and_copies() -> None:
    """The export folds the operations and is safe to mutate."""
    context = CharacterCreationContext()
    context.set("choices.race", "Dwarf")
    context.set("values.hit_points", 5)
    context.record("values.hit_points", AddOne())
    context.mark_executed("identity")

    exported = context.export()
    assert exported["choices"]["race"] == "Dwarf"
    assert exported["values"]["hit_points"] == 6
    assert exported["executed_steps"] == ["identity"]

    # The base state is untouched and the export is a deep copy.
    exported["choices"]["race"] = "Elf"
    exported["values"]["hit_points"] = 999
    assert context.get("choices.race") == "Dwarf"
    assert context.get("values.hit_points") == 5


def test_system_data_is_copied_and_read_only() -> None:
    """The system mapping is shallow-copied and exposed read-only."""
    source = {"attributes": ["strength"]}
    context = CharacterCreationContext(system=source)
    source["attributes"].append("charm")
    assert context.system["attributes"] == ["strength", "charm"]
    with pytest.raises(TypeError):
        context.system["attributes"] = []  # type: ignore[index]


def test_executed_steps_are_unique() -> None:
    """Step identifiers are recorded once, in order."""
    context = CharacterCreationContext()
    context.mark_executed("identity")
    context.mark_executed("race")
    context.mark_executed("identity")
    assert context.executed_steps == ["identity", "race"]


def test_repr_shows_counts() -> None:
    """The repr exposes the class name and the state sizes."""
    context = CharacterCreationContext()
    context.set("choices.race", "Dwarf")
    representation = repr(context)
    assert "CharacterCreationContext" in representation
    assert "choices=1" in representation
