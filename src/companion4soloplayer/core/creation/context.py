"""State container for a character creation session.

A creation session manipulates two kinds of data, kept apart on purpose
(Separation of Concerns):

- the **raw choices** given by the player (name, background, race,
  class, picked skills/spells...) live under the ``choices`` namespace;
- the **computed values** produced by the creation steps (base
  attributes, working skill/spell lists...) live under the ``values``
  namespace.

Both namespaces are addressed with dotted paths such as
``choices.race`` or ``values.attributes.strength``; the first segment
selects the namespace (see :data:`CHOICES_NAMESPACE` and
:data:`VALUES_NAMESPACE`).

On top of the base values, the rules engine records *operations*
(bonuses, maluses, grants...) produced by the condition/effect rules of
:mod:`companion4soloplayer.core.creation.rules`. The recorded operations
are cleared and rebuilt at every evaluation, so
:meth:`CharacterCreationContext.effective` never double counts a bonus,
whatever the number of evaluations performed by the pipeline.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from copy import deepcopy
from types import MappingProxyType
from typing import Any

#: Namespace holding the raw choices given by the player.
CHOICES_NAMESPACE = "choices"

#: Namespace holding the values computed by the creation steps.
VALUES_NAMESPACE = "values"

#: Namespaces accepted as the first segment of a state path.
NAMESPACES: tuple[str, ...] = (CHOICES_NAMESPACE, VALUES_NAMESPACE)


class InvalidPathError(ValueError):
    """Raised when a state path is malformed or targets an unknown namespace."""


def parse_path(path: str) -> tuple[str, ...]:
    """Split and validate a dotted state path.

    Args:
        path: Dotted path such as ``choices.race`` or
            ``values.attributes.strength``. The first segment must be a
            known namespace (``choices`` or ``values``).

    Returns:
        The path segments as a tuple.

    Raises:
        InvalidPathError: If the path is empty, contains an empty
            segment or does not start with a known namespace.

    Example:
        >>> parse_path("values.attributes.strength")
        ('values', 'attributes', 'strength')
    """
    if not isinstance(path, str) or not path.strip():
        raise InvalidPathError(f"A state path must be a non-empty string, got {path!r}")
    parts = tuple(path.split("."))
    if any(not part for part in parts):
        raise InvalidPathError(f"Invalid state path {path!r}: empty segment")
    if parts[0] not in NAMESPACES:
        expected = " or ".join(repr(namespace) for namespace in NAMESPACES)
        raise InvalidPathError(
            f"Invalid state path {path!r}: expected a path starting with {expected}"
        )
    return parts


def _read(root: Mapping[str, Any], parts: Sequence[str], path: str) -> Any:
    """Read a nested value from ``root``.

    Args:
        root: Root mapping of the namespace.
        parts: Path segments relative to ``root``.
        path: Full path, used to build the error message.

    Returns:
        The stored value.

    Raises:
        KeyError: If a segment is missing or traverses a non-mapping.
    """
    current: Any = root
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            raise KeyError(path)
        current = current[part]
    return current


def _write(root: MutableMapping[str, Any], parts: Sequence[str], value: Any) -> None:
    """Write ``value`` below ``root``, creating intermediate mappings.

    Args:
        root: Root mapping of the namespace.
        parts: Non-empty path segments relative to ``root``.
        value: Value to store at the leaf.

    Raises:
        InvalidPathError: If an intermediate segment exists but is not
            a mapping.
    """
    current: MutableMapping[str, Any] = root
    for part in parts[:-1]:
        child = current.get(part)
        if child is None:
            child = {}
            current[part] = child
        elif not isinstance(child, MutableMapping):
            raise InvalidPathError(f"Cannot write below {part!r} in the state path: not a mapping")
        current = child
    current[parts[-1]] = value


class CharacterCreationContext:
    """Hold the raw choices and the computed values of a creation session.

    The context is the single state container shared by the creation
    steps and the rules engine:

    - :attr:`choices` stores the raw player answers;
    - :attr:`values` stores the values computed by the steps;
    - :attr:`system` exposes the read-only game data (catalogs,
      attribute names, strategies...) supplied by the plugin;
    - :attr:`executed_steps` records the identifiers of the steps that
      already ran, in execution order.

    On top of those base values, rules record *operations* that
    :meth:`effective` folds over the base value. Operations are dropped
    and rebuilt by :meth:`begin_evaluation` at every rules evaluation,
    which keeps the computation idempotent.

    Args:
        system: Read-only game data shared with the steps (catalogs,
            attribute definitions, named strategies...). The mapping is
            shallow-copied and exposed through a mapping proxy.

    Example:
        >>> context = CharacterCreationContext()
        >>> context.set("choices.race", "Dwarf")
        >>> context.peek("choices.race")
        'Dwarf'
    """

    def __init__(self, *, system: Mapping[str, Any] | None = None) -> None:
        """Initialize an empty creation context.

        Args:
            system: Read-only game data shared with the steps.
        """
        self.choices: dict[str, Any] = {}
        self.values: dict[str, Any] = {}
        self.executed_steps: list[str] = []
        self._system: Mapping[str, Any] = MappingProxyType(dict(system or {}))
        self._operations: dict[str, list[Any]] = {}

    @property
    def system(self) -> Mapping[str, Any]:
        """Return the read-only game data attached to the session."""
        return self._system

    # ------------------------------------------------------------------
    # Base values
    # ------------------------------------------------------------------

    def has(self, path: str) -> bool:
        """Tell whether a base value exists for ``path``.

        Args:
            path: Dotted state path (``choices....`` / ``values....``).

        Returns:
            True when the path is present in the base state.

        Raises:
            InvalidPathError: If the path is malformed.
        """
        parts = parse_path(path)
        try:
            _read(self._root(parts[0]), parts[1:], path)
        except KeyError:
            return False
        return True

    def get(self, path: str) -> Any:
        """Return the base value stored at ``path``.

        Args:
            path: Dotted state path.

        Returns:
            The stored value (any YAML-compatible data).

        Raises:
            InvalidPathError: If the path is malformed.
            KeyError: If the path does not exist.
        """
        parts = parse_path(path)
        return _read(self._root(parts[0]), parts[1:], path)

    def peek(self, path: str, default: Any = None) -> Any:
        """Return the base value stored at ``path``, or ``default``.

        Args:
            path: Dotted state path.
            default: Value returned when the path is absent.

        Returns:
            The stored value or ``default``.

        Raises:
            InvalidPathError: If the path is malformed.
        """
        try:
            return self.get(path)
        except KeyError:
            return default

    def set(self, path: str, value: Any) -> None:
        """Store ``value`` at ``path``, creating intermediate mappings.

        Args:
            path: Dotted state path with a leaf segment (at least
                ``namespace.key``).
            value: Value to store.

        Raises:
            InvalidPathError: If the path is malformed, has no leaf
                segment, or traverses a non-mapping value.
        """
        parts = parse_path(path)
        if len(parts) < 2:
            raise InvalidPathError(
                f"Cannot write the whole namespace {path!r}: a leaf path is required"
            )
        _write(self._root(parts[0]), parts[1:], value)

    # ------------------------------------------------------------------
    # Effective values (base + recorded rule operations)
    # ------------------------------------------------------------------

    def effective(self, path: str, default: Any = None) -> Any:
        """Return the value of ``path`` with the rule operations applied.

        The base value is read first (``default`` is used when the path
        is absent), then every operation recorded for that path is
        applied in recording order. A missing base is treated as ``0``
        by numeric operations and as an empty list by collection
        operations, so a rule may fire before the step that computes the
        base value: the next evaluation recomputes the result from the
        fresh base.

        Args:
            path: Dotted state path.
            default: Base value used when the path is absent.

        Returns:
            The effective value.

        Raises:
            InvalidPathError: If the path is malformed.
        """
        value = self.peek(path, default)
        for operation in self._operations.get(path, ()):
            value = operation.apply_to(value)
        return value

    def begin_evaluation(self) -> None:
        """Drop every recorded operation (start of a rules evaluation)."""
        self._operations.clear()

    def record(self, path: str, effect: Any) -> None:
        """Record a rule effect operation for ``path``.

        Args:
            path: Dotted state path targeted by the effect.
            effect: Operation object exposing ``apply_to(base)`` (in
                practice a
                :class:`~companion4soloplayer.core.creation.rules.Effect`).

        Raises:
            InvalidPathError: If the path is malformed or has no leaf
                segment.
        """
        parts = parse_path(path)
        if len(parts) < 2:
            raise InvalidPathError(f"Cannot apply an effect to the whole namespace {path!r}")
        self._operations.setdefault(path, []).append(effect)

    @property
    def operations(self) -> Mapping[str, Sequence[Any]]:
        """Return a read-only snapshot of the recorded operations."""
        return MappingProxyType({path: tuple(ops) for path, ops in self._operations.items()})

    # ------------------------------------------------------------------
    # Session bookkeeping and export
    # ------------------------------------------------------------------

    def mark_executed(self, step_id: str) -> None:
        """Record that a step ran (identifiers stay unique and ordered).

        Args:
            step_id: Identifier of the executed step.
        """
        if step_id not in self.executed_steps:
            self.executed_steps.append(step_id)

    def export(self) -> dict[str, Any]:
        """Export the character built by the session.

        Returns:
            A plain ``dict`` with the raw ``choices``, the **effective**
            ``values`` (rule operations folded in) and the
            ``executed_steps`` list. The result is deep-copied: the
            caller may freely mutate it.
        """
        exported: dict[str, Any] = {
            CHOICES_NAMESPACE: deepcopy(self.choices),
            VALUES_NAMESPACE: deepcopy(self.values),
            "executed_steps": list(self.executed_steps),
        }
        for path in tuple(self._operations):
            parts = parse_path(path)
            if len(parts) < 2:
                continue
            root: dict[str, Any] = exported[parts[0]]
            _write(root, parts[1:], self.effective(path))
        return exported

    def _root(self, namespace: str) -> dict[str, Any]:
        """Return the mapping behind a namespace.

        Args:
            namespace: ``choices`` or ``values``.

        Returns:
            The live namespace mapping.
        """
        if namespace == CHOICES_NAMESPACE:
            return self.choices
        return self.values

    def __repr__(self) -> str:
        """Return a compact debugging representation."""
        return (
            f"{type(self).__name__}(choices={len(self.choices)}, values={len(self.values)}, "
            f"operations={len(self._operations)})"
        )
