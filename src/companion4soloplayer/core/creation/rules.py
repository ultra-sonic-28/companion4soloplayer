"""Condition/Effect rule engine for the character creation flow.

A *creation rule* links a set of **conditions** (when does it apply?)
to a set of **effects** (what does it change?):

- a :class:`Condition` is a triple *target + operator + value* evaluated
  against the effective state of a
  :class:`~companion4soloplayer.core.creation.context.CharacterCreationContext`
  (for example ``choices.race == "Dwarf"``);
- an :class:`Effect` is a triple *target + action + value* applied to
  the state (for example ``values.attributes.constitution += 2``).

The :class:`RulesEngine` evaluates every rule **after each executed
step** (the pipeline triggers it automatically) and records the
matching effects as *operations* on the context. Each evaluation starts
from a clean slate (:meth:`CharacterCreationContext.begin_evaluation`),
so bonuses are never double counted and a rule whose condition becomes
true later (race chosen, attributes rolled, skills picked...) is picked
up at the next evaluation.

Rules are evaluated **in declaration order**; a rule sees the effects
of the rules declared before it within the same evaluation, which
allows deliberate chaining while keeping the result deterministic.

The declarative format loaded by :func:`load_creation_rules` is::

    rules:
      - id: dwarf_hardy
        description: Dwarves are hardy.
        when:
          - target: choices.race
            operator: eq
            value: Dwarf
        effects:
          - target: values.attributes.constitution
            action: add
            value: 2
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from companion4soloplayer.core.creation.context import CharacterCreationContext, parse_path
from companion4soloplayer.utils.yaml_loader import load_yaml_file


class RuleDefinitionError(ValueError):
    """Raised when a rule document or rule entry is malformed."""


class RuleEvaluationError(ValueError):
    """Raised when a condition or an effect cannot be evaluated."""


def _is_number(value: Any) -> bool:
    """Tell whether ``value`` is a real number (booleans excluded)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_empty(value: Any) -> bool:
    """Tell whether ``value`` behaves as an empty container/scalar."""
    if value is None:
        return True
    if isinstance(value, (str, bytes, list, tuple, dict, set, frozenset)):
        return len(value) == 0
    return False


def _contains(container: Any, item: Any) -> bool:
    """Tell whether ``container`` holds ``item``.

    Args:
        container: Sequence, mapping (keys) or string (substring).
        item: Searched value.

    Returns:
        True when the item is found.

    Raises:
        RuleEvaluationError: If the container is not searchable.
    """
    if container is None:
        return False
    if isinstance(container, Mapping):
        return item in container
    if isinstance(container, str):
        return str(item) in container
    if isinstance(container, (list, tuple, set, frozenset)):
        return item in container
    raise RuleEvaluationError(f"Cannot test 'contains' on a {type(container).__name__} value")


class Operator(StrEnum):
    """Comparison operators understood by :class:`Condition`."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GE = "ge"
    LT = "lt"
    LE = "le"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    EMPTY = "empty"
    NOT_EMPTY = "not_empty"

    @classmethod
    def parse(cls, value: Operator | str) -> Operator:
        """Parse an operator from YAML data.

        Args:
            value: Operator name (case-insensitive) or common symbol
                (``==``, ``!=``, ``>=``...).

        Returns:
            The parsed operator.

        Raises:
            RuleDefinitionError: If the operator is unknown.

        Example:
            >>> Operator.parse(">=") is Operator.GE
            True
        """
        if isinstance(value, Operator):
            return value
        if not isinstance(value, str):
            raise RuleDefinitionError(f"Invalid condition operator {value!r}")
        normalized = value.strip().lower()
        aliases = {"==": "eq", "!=": "ne", ">": "gt", ">=": "ge", "<": "lt", "<=": "le"}
        normalized = aliases.get(normalized, normalized)
        try:
            return cls(normalized)
        except ValueError as exc:
            available = ", ".join(operator.value for operator in cls)
            raise RuleDefinitionError(
                f"Unknown condition operator {value!r} (available: {available})"
            ) from exc


class Action(StrEnum):
    """Mutation actions performed by :class:`Effect`."""

    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    SET = "set"
    GRANT = "grant"
    REMOVE = "remove"

    @classmethod
    def parse(cls, value: Action | str) -> Action:
        """Parse an action from YAML data.

        Args:
            value: Action name (case-insensitive).

        Returns:
            The parsed action.

        Raises:
            RuleDefinitionError: If the action is unknown.
        """
        if isinstance(value, Action):
            return value
        if not isinstance(value, str):
            raise RuleDefinitionError(f"Invalid effect action {value!r}")
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            available = ", ".join(action.value for action in cls)
            raise RuleDefinitionError(
                f"Unknown effect action {value!r} (available: {available})"
            ) from exc


@dataclass(frozen=True)
class Condition:
    """A test evaluated against the effective state of a context.

    Attributes:
        target: Dotted state path tested by the condition.
        operator: Comparison operator (see :class:`Operator`).
        value: Expected value; ignored by the existence and emptiness
            operators.

    Raises:
        RuleDefinitionError: When built through :meth:`from_dict` with a
            malformed payload.
    """

    target: str
    operator: Operator
    value: Any = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Condition:
        """Build a condition from a YAML mapping.

        Args:
            data: Mapping with ``target``, ``operator`` and optional
                ``value`` entries.

        Returns:
            The parsed condition.

        Raises:
            RuleDefinitionError: If the mapping misses a required entry
                holds an unknown entry, or uses an invalid operator or
                path.
        """
        if not isinstance(data, Mapping):
            raise RuleDefinitionError(f"A condition must be a mapping, got {type(data).__name__}")
        unknown = set(data) - {"target", "operator", "value"}
        if unknown:
            raise RuleDefinitionError(f"Unknown condition entries: {sorted(unknown, key=str)}")
        if "target" not in data:
            raise RuleDefinitionError("A condition requires a 'target' entry")
        if "operator" not in data:
            raise RuleDefinitionError("A condition requires an 'operator' entry")
        target = data["target"]
        if not isinstance(target, str):
            raise RuleDefinitionError(f"Condition target must be a string, got {target!r}")
        try:
            parse_path(target)
        except ValueError as exc:
            raise RuleDefinitionError(f"Invalid condition target: {exc}") from exc
        operator = Operator.parse(data["operator"])
        condition = cls(target=target, operator=operator, value=data.get("value"))
        condition._check_definition()
        return condition

    def evaluate(self, context: CharacterCreationContext) -> bool:
        """Evaluate the condition against ``context``.

        Args:
            context: Creation state; the **effective** value of the
                target is tested, i.e. the base value with the effects
                of the rules evaluated before this one.

        Returns:
            True when the condition holds.

        Raises:
            RuleEvaluationError: If the comparison cannot be performed
                (for example a numeric operator applied to texts).
        """
        if self.operator is Operator.EXISTS:
            return context.effective(self.target) is not None
        if self.operator is Operator.NOT_EXISTS:
            return context.effective(self.target) is None
        if self.operator is Operator.EMPTY:
            return _is_empty(context.effective(self.target))
        if self.operator is Operator.NOT_EMPTY:
            return not _is_empty(context.effective(self.target))

        actual = context.effective(self.target)
        if self.operator is Operator.EQ:
            return bool(actual == self.value)
        if self.operator is Operator.NE:
            return bool(actual != self.value)
        if self.operator in (Operator.GT, Operator.GE, Operator.LT, Operator.LE):
            if actual is None:
                # The value is not computed yet (e.g. a rule evaluated
                # before the attribute step): the condition simply
                # cannot hold yet, it will be re-evaluated later.
                return False
            self._check_numbers(actual, self.value)
            if self.operator is Operator.GT:
                return bool(actual > self.value)
            if self.operator is Operator.GE:
                return bool(actual >= self.value)
            if self.operator is Operator.LT:
                return bool(actual < self.value)
            return bool(actual <= self.value)
        if self.operator is Operator.IN:
            self._check_container(self.value, "in")
            return actual in self.value
        if self.operator is Operator.NOT_IN:
            self._check_container(self.value, "not_in")
            return actual not in self.value
        if self.operator is Operator.CONTAINS:
            return _contains(actual, self.value)
        return not _contains(actual, self.value)

    def describe(self) -> str:
        """Return a compact human-readable form (for reports/logs)."""
        return f"{self.target} {self.operator.value} {self.value!r}"

    def _check_definition(self) -> None:
        """Validate the static shape of the condition.

        Raises:
            RuleDefinitionError: If ``in``/``not_in`` does not target a
                list of expected values.
        """
        if self.operator in (Operator.IN, Operator.NOT_IN):
            self._check_container(self.value, self.operator.value)

    @staticmethod
    def _check_container(value: Any, operator: str) -> None:
        """Ensure the expected value of ``in`` is a container.

        Args:
            value: Value stored in the condition.
            operator: Operator name, used in error messages.

        Raises:
            RuleDefinitionError: If the value is not a list or tuple.
        """
        if not isinstance(value, (list, tuple)):
            raise RuleDefinitionError(
                f"The {operator!r} operator expects a list of values, got {value!r}"
            )

    @staticmethod
    def _check_numbers(actual: Any, expected: Any) -> None:
        """Ensure both operands of a numeric comparison are numbers.

        Args:
            actual: Effective value read from the context.
            expected: Value stored in the condition.

        Raises:
            RuleEvaluationError: If an operand is not a number.
        """
        if not _is_number(actual) or not _is_number(expected):
            raise RuleEvaluationError(
                f"Numeric comparison between {actual!r} and {expected!r} is not possible"
            )


@dataclass(frozen=True)
class Effect:
    """A mutation applied to the effective state of a context.

    Attributes:
        target: Dotted state path modified by the effect.
        action: Mutation action (see :class:`Action`).
        value: Value carried by the action (expected value for
            ``set``, amount for ``add``/``sub``/``mul``, item for
            ``grant``/``remove``).

    Example:
        >>> effect = Effect(target="values.attributes.strength",
        ...                 action=Action.ADD, value=2)
        >>> effect.apply_to(10)
        12
    """

    target: str
    action: Action
    value: Any = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Effect:
        """Build an effect from a YAML mapping.

        Args:
            data: Mapping with ``target``, ``action`` and optional
                ``value`` entries.

        Returns:
            The parsed effect.

        Raises:
            RuleDefinitionError: If the mapping misses a required entry
                holds an unknown entry, or uses an invalid action or
                path.
        """
        if not isinstance(data, Mapping):
            raise RuleDefinitionError(f"An effect must be a mapping, got {type(data).__name__}")
        unknown = set(data) - {"target", "action", "value"}
        if unknown:
            raise RuleDefinitionError(f"Unknown effect entries: {sorted(unknown, key=str)}")
        if "target" not in data:
            raise RuleDefinitionError("An effect requires a 'target' entry")
        if "action" not in data:
            raise RuleDefinitionError("An effect requires an 'action' entry")
        target = data["target"]
        if not isinstance(target, str):
            raise RuleDefinitionError(f"Effect target must be a string, got {target!r}")
        try:
            parts = parse_path(target)
        except ValueError as exc:
            raise RuleDefinitionError(f"Invalid effect target: {exc}") from exc
        if len(parts) < 2:
            raise RuleDefinitionError(
                f"Effect target {target!r} must address a leaf, not a whole namespace"
            )
        return cls(target=target, action=Action.parse(data["action"]), value=data.get("value"))

    def apply_to(self, base: Any) -> Any:
        """Return ``base`` with this effect applied (pure function).

        A ``None`` base is treated as ``0`` by the numeric actions and
        as an empty list by the collection actions, so an effect may be
        evaluated before the step that computes the base value.

        Args:
            base: Current effective value of the target.

        Returns:
            The new effective value; collections are copied, the base
            value is never mutated in place.

        Raises:
            RuleEvaluationError: If the action cannot be applied to the
                base value (numeric action on a text, ``remove`` on a
                scalar...).
        """
        if self.action is Action.SET:
            return deepcopy(self.value)
        if self.action in (Action.ADD, Action.SUB, Action.MUL):
            number = 0 if base is None else base
            amount = 0 if self.value is None else self.value
            if not _is_number(number) or not _is_number(amount):
                raise RuleEvaluationError(
                    f"The {self.action.value!r} action needs numbers: "
                    f"cannot apply {self.value!r} to {base!r} at {self.target!r}"
                )
            if self.action is Action.ADD:
                return number + amount
            if self.action is Action.SUB:
                return number - amount
            return number * amount
        return self._apply_collection_action(base)

    def _apply_collection_action(self, base: Any) -> Any:
        """Apply ``grant``/``remove`` to a collection value.

        Args:
            base: Current effective value of the target.

        Returns:
            The new list value.

        Raises:
            RuleEvaluationError: If the base is not a collection.
        """
        if base is None:
            items: list[Any] = []
        elif isinstance(base, (list, tuple)):
            items = list(base)
        else:
            raise RuleEvaluationError(
                f"The {self.action.value!r} action needs a list at {self.target!r}, "
                f"got {type(base).__name__}"
            )
        if self.action is Action.GRANT:
            if self.value not in items:
                items.append(deepcopy(self.value))
            return items
        return [item for item in items if item != self.value]


@dataclass(frozen=True)
class CreationRule:
    """A declarative rule: conditions gate a list of effects.

    Attributes:
        id: Unique identifier used in evaluation reports.
        description: Human-readable intent of the rule.
        when: Conditions that must **all** hold for the rule to fire
            (an empty tuple makes the rule unconditional).
        effects: Effects applied, in order, when the rule fires.
    """

    id: str
    description: str = ""
    when: tuple[Condition, ...] = ()
    effects: tuple[Effect, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> CreationRule:
        """Build a rule from a YAML mapping.

        Args:
            data: Mapping with ``id``, ``description``, ``when`` and
                ``effects`` entries (only ``effects`` is required).
            index: Position of the rule in the document, used to derive
                a default identifier.

        Returns:
            The parsed rule.

        Raises:
            RuleDefinitionError: If the mapping is malformed.
        """
        if not isinstance(data, Mapping):
            raise RuleDefinitionError(f"A rule must be a mapping, got {type(data).__name__}")
        unknown = set(data) - {"id", "description", "when", "effects"}
        if unknown:
            raise RuleDefinitionError(f"Unknown rule entries: {sorted(unknown, key=str)}")
        raw_effects = data.get("effects")
        if not isinstance(raw_effects, Sequence) or isinstance(raw_effects, (str, bytes)):
            raise RuleDefinitionError("A rule requires a 'effects' sequence")
        if not raw_effects:
            raise RuleDefinitionError("A rule requires at least one effect")
        raw_when = data.get("when", [])
        if not isinstance(raw_when, Sequence) or isinstance(raw_when, (str, bytes)):
            raise RuleDefinitionError("The 'when' entry of a rule must be a sequence")
        rule_id = data.get("id", f"rule_{index + 1}")
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise RuleDefinitionError(f"Rule id must be a non-empty string, got {rule_id!r}")
        description = data.get("description", "")
        if not isinstance(description, str):
            raise RuleDefinitionError("Rule description must be a string")
        return cls(
            id=rule_id.strip(),
            description=description,
            when=tuple(Condition.from_dict(entry) for entry in _require_mappings(raw_when, "when")),
            effects=tuple(
                Effect.from_dict(entry) for entry in _require_mappings(raw_effects, "effects")
            ),
        )

    def matches(self, context: CharacterCreationContext) -> bool:
        """Tell whether every condition of the rule holds.

        Args:
            context: Creation state to test.

        Returns:
            True when the rule must fire.
        """
        return all(condition.evaluate(context) for condition in self.when)


def _require_mappings(entries: Sequence[Any], name: str) -> list[Mapping[str, Any]]:
    """Ensure a rule section contains mappings only.

    Args:
        entries: Raw entries read from the YAML document.
        name: Section name, used in error messages.

    Returns:
        The entries, typed as mappings.

    Raises:
        RuleDefinitionError: If an entry is not a mapping.
    """
    result: list[Mapping[str, Any]] = []
    for position, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise RuleDefinitionError(
                f"Entry #{position + 1} of {name!r} must be a mapping, "
                f"got {type(entry).__name__}"
            )
        result.append(entry)
    return result


@dataclass(frozen=True)
class EvaluationReport:
    """Outcome of one rules evaluation.

    Attributes:
        fired: Identifiers of the rules that fired, in evaluation order.
        applied_effects: Total number of recorded effect operations.
    """

    fired: tuple[str, ...] = ()
    applied_effects: int = 0


class RulesEngine:
    """Evaluate creation rules against a creation context.

    The engine holds no session state: every :meth:`evaluate` call
    clears the operations recorded on the context and rebuilds them
    from scratch, in declaration order. This makes the evaluation
    idempotent and lets a rule fire as soon as its conditions become
    true, whatever the step that changed the state.

    Args:
        rules: Initial rules; identifiers must be unique.

    Raises:
        RuleDefinitionError: If two rules share the same identifier.

    Example:
        >>> from companion4soloplayer.core.creation.context import (
        ...     CharacterCreationContext)
        >>> engine = RulesEngine([CreationRule(
        ...     id="r",
        ...     when=(Condition("choices.race", Operator.EQ, "Dwarf"),),
        ...     effects=(Effect("values.hp", Action.ADD, 2),))])
        >>> context = CharacterCreationContext()
        >>> context.set("choices.race", "Dwarf")
        >>> engine.evaluate(context).fired
        ('r',)
        >>> context.effective("values.hp")
        2
    """

    def __init__(self, rules: Sequence[CreationRule] = ()) -> None:
        """Initialize the engine.

        Args:
            rules: Initial rules, evaluated in the given order.
        """
        self._rules: list[CreationRule] = []
        for rule in rules:
            self.add(rule)

    @property
    def rules(self) -> tuple[CreationRule, ...]:
        """Return the rules, in declaration order."""
        return tuple(self._rules)

    def add(self, rule: CreationRule) -> None:
        """Append a rule to the engine.

        Args:
            rule: Rule to register.

        Raises:
            RuleDefinitionError: If the rule identifier is already used.
        """
        if any(existing.id == rule.id for existing in self._rules):
            raise RuleDefinitionError(f"Duplicate rule id {rule.id!r}")
        self._rules.append(rule)

    def evaluate(self, context: CharacterCreationContext) -> EvaluationReport:
        """Evaluate every rule and record the matching effects.

        Args:
            context: Creation state; operations recorded by a previous
                evaluation are dropped first, then each matching rule
                appends its effects (later rules see the effects of the
                rules evaluated before them).

        Returns:
            The identifiers of the fired rules and the number of
            recorded effect operations.
        """
        context.begin_evaluation()
        fired: list[str] = []
        applied = 0
        for rule in self._rules:
            if not rule.matches(context):
                continue
            for effect in rule.effects:
                context.record(effect.target, effect)
            fired.append(rule.id)
            applied += len(rule.effects)
        return EvaluationReport(fired=tuple(fired), applied_effects=applied)


def load_creation_rules(path: str | Path) -> list[CreationRule]:
    """Load creation rules from a YAML document.

    The document is either a bare sequence of rules or a mapping with a
    ``rules`` entry holding that sequence.

    Args:
        path: Path of the YAML file (read as UTF-8).

    Returns:
        The parsed rules, in declaration order.

    Raises:
        YamlLoadError: If the file content is not valid YAML.
        RuleDefinitionError: If the document shape or a rule entry is
            invalid.
    """
    document = load_yaml_file(path)
    if isinstance(document, Mapping):
        if "rules" not in document:
            raise RuleDefinitionError(f"Rules document {path} must hold a 'rules' sequence")
        entries = document["rules"]
    elif isinstance(document, Sequence) and not isinstance(document, (str, bytes)):
        entries = document
    else:
        raise RuleDefinitionError(
            f"Rules document {path} must be a mapping or a sequence, got {type(document).__name__}"
        )
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise RuleDefinitionError(f"The 'rules' entry of {path} must be a sequence")
    rules: list[CreationRule] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise RuleDefinitionError(
                f"Rule #{index + 1} of {path} must be a mapping, got {type(entry).__name__}"
            )
        rules.append(CreationRule.from_dict(entry, index=index))
    return rules
