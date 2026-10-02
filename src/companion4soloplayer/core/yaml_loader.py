"""
YAML data loading module for plugin and rule data.

The loader builds on :class:`yaml.SafeLoader`, so only plain YAML data
(mappings, sequences and scalars) can be constructed: arbitrary Python
object instantiation (``!!python/...`` tags) is rejected by the parser.
On top of that hardened baseline, a small set of custom tags adds typed
values on purpose:

- ``!pyclass`` declares a Python class to instantiate later (hybrid
  YAML/Python rule architecture). It is parsed into a :class:`PyClassRef`
  value; **no import happens during parsing**.
- ``!dice`` declares a dice expression (``2d6``, ``1d20+3``, ``d6-1``...)
  and is parsed into a :class:`DiceExpression` value.

Additional tags can be registered with :func:`register_tag` before any
document is loaded, which lets plugins extend the vocabulary without
touching the core loader.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode

from companion4soloplayer.core.dice_roller import DiceRoller


class YamlLoadError(ValueError):
    """Raised when a YAML document cannot be parsed."""


class YamlTagError(ValueError):
    """Raised when the payload of a custom tag is invalid."""


# Accepts "2d6", "d20", "1d20+3", "4d6-2" (case-insensitive).
_DICE_PATTERN = re.compile(r"^(?P<count>\d*)[dD](?P<sides>\d+)(?P<modifier>[+-]\d+)?$")


@dataclass(frozen=True)
class DiceExpression:
    """A parsed dice expression such as ``2d6`` or ``1d20+3``.

    Attributes:
        count: Number of dice to roll (at least 1).
        sides: Number of sides per die (at least 2).
        modifier: Value added to (or subtracted from) the dice total.
    """

    count: int
    sides: int
    modifier: int = 0

    @classmethod
    def parse(cls, value: DiceExpression | str) -> DiceExpression:
        """Parse a dice notation string (already-parsed values pass through).

        Args:
            value: Dice notation such as ``2d6``, ``d20``, ``1d20+3``.

        Returns:
            The parsed :class:`DiceExpression`.

        Raises:
            YamlTagError: If the notation is invalid.
        """
        if isinstance(value, DiceExpression):
            return value
        match = _DICE_PATTERN.match(value.strip())
        if match is None:
            raise YamlTagError(
                f"Invalid dice notation {value!r}: expected '<count>d<sides>[+/-<modifier>]'"
            )
        count = int(match.group("count")) if match.group("count") else 1
        sides = int(match.group("sides"))
        if count < 1 or sides < 2:
            raise YamlTagError(
                f"Invalid dice notation {value!r}: count >= 1 and sides >= 2 required"
            )
        modifier = int(match.group("modifier")) if match.group("modifier") else 0
        return cls(count=count, sides=sides, modifier=modifier)

    @property
    def notation(self) -> str:
        """Return the canonical notation (``2d6+1``)."""
        modifier = f"{self.modifier:+d}" if self.modifier else ""
        return f"{self.count}d{self.sides}{modifier}"

    def __str__(self) -> str:
        """Return the canonical notation."""
        return self.notation

    def roll(self, roller: DiceRoller | None = None) -> int:
        """Roll the expression and return the total, modifier included.

        Args:
            roller: Optional dice roller; a fresh one is created when omitted.

        Returns:
            Sum of the dice results plus the modifier.
        """
        _, total = self.roll_detail(roller)
        return total

    def roll_detail(self, roller: DiceRoller | None = None) -> tuple[list[int], int]:
        """Roll the expression and return both the dice results and the total.

        Args:
            roller: Optional dice roller; a fresh one is created when omitted.

        Returns:
            Tuple ``(dice results, total including modifier)``.
        """
        roller = roller or DiceRoller()
        results = roller.roll_dice(self.count, self.sides)
        return results, sum(results) + self.modifier


# --------------------------------------------------------------------------
# !pyclass -> PyClassRef
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PyClassRef:
    """A reference to a Python class declared in YAML.

    The reference is *data*: it is never imported while parsing. The core
    rule engine resolves and instantiates it on demand, after checking a
    module allow-list.

    Attributes:
        path: Either ``"module.path:ClassName"`` (absolute import) or
            ``"local:ClassName"`` / ``":ClassName"`` (class living in the
            module that declared the rules, valid in development and in
            the compiled ``.pyd`` build).
        params: Keyword arguments passed to the constructor.
    """

    path: str
    params: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, value: str) -> PyClassRef:
        """Parse a ``module:Class`` / ``local:Class`` reference string.

        Args:
            value: The reference string.

        Returns:
            The parsed :class:`PyClassRef`.

        Raises:
            YamlTagError: If the reference format is invalid.
        """
        module_name, separator, attr = value.partition(":")
        if not separator or not attr or "." in attr:
            raise YamlTagError(
                f"Invalid class reference {value!r}: expected 'module.path:ClassName' "
                "or 'local:ClassName'"
            )
        if module_name in ("", "local"):
            return cls(path=f"local:{attr}")
        if not all(part.isidentifier() for part in module_name.split(".")):
            raise YamlTagError(f"Invalid class reference {value!r}")
        if not attr.isidentifier():
            raise YamlTagError(f"Invalid class reference {value!r}")
        return cls(path=f"{module_name}:{attr}")

    @property
    def module(self) -> str:
        """Return the module part (``"local"`` for plugin-local references)."""
        return self.path.partition(":")[0]

    @property
    def attr(self) -> str:
        """Return the class/attribute part of the reference."""
        return self.path.partition(":")[2]

    @property
    def is_local(self) -> bool:
        """Return True when the reference targets the declaring module."""
        return self.module == "local"


# --------------------------------------------------------------------------
# Loader with the C4SP custom tags
# --------------------------------------------------------------------------

#: Signature of a custom tag constructor.
TagConstructor = Callable[[Any, Node], Any]


class C4SPSafeLoader(yaml.SafeLoader):
    """``yaml.SafeLoader`` extended with the C4SP custom tags.

    The class only *adds* constructors; the unsafe ``yaml.Loader`` /
    ``yaml.FullLoader`` classes are never used, so ``!!python/...`` tags
    keep raising a :class:`yaml.constructor.ConstructorError`.
    """


def _construct_pyclass(loader: C4SPSafeLoader, node: Node) -> PyClassRef:
    """Construct a ``!pyclass`` node (scalar or mapping form)."""
    if isinstance(node, ScalarNode):
        return PyClassRef.parse(str(loader.construct_scalar(node)))
    if isinstance(node, MappingNode):
        data = loader.construct_mapping(node, deep=True)
        unknown = set(data) - {"path", "params"}
        if unknown:
            raise YamlTagError(f"!pyclass got unknown keys: {sorted(unknown, key=str)}")
        path = data.get("path")
        if not isinstance(path, str):
            raise YamlTagError("!pyclass mapping form requires a string 'path' entry")
        params = data.get("params", {})
        if not isinstance(params, Mapping):
            raise YamlTagError("!pyclass 'params' must be a mapping")
        return PyClassRef(path=path, params=dict(params))
    raise YamlTagError("!pyclass expects a 'module:Class' scalar or a {path, params} mapping")


def _construct_dice(loader: C4SPSafeLoader, node: Node) -> DiceExpression:
    """Construct a ``!dice`` scalar node."""
    if not isinstance(node, ScalarNode):
        raise YamlTagError("!dice expects a scalar notation such as '2d6'")
    return DiceExpression.parse(str(loader.construct_scalar(node)))


C4SPSafeLoader.add_constructor("!pyclass", _construct_pyclass)
C4SPSafeLoader.add_constructor("!dice", _construct_dice)


def register_tag(tag: str, constructor: TagConstructor) -> None:
    """Register an additional custom tag on the C4SP safe loader.

    Registration must happen before any document is loaded with
    :func:`load_yaml` / :func:`load_yaml_file`. Only safe constructors are
    accepted: they receive the loader and the YAML node and must return
    plain data or lightweight value objects.

    Args:
        tag: Tag name, starting with ``!`` (e.g. ``!table``).
        constructor: ``(loader, node) -> value`` callable.

    Raises:
        ValueError: If the tag name does not start with ``!``.
    """
    if not tag.startswith("!"):
        raise ValueError(f"YAML tag names must start with '!': {tag!r}")
    C4SPSafeLoader.add_constructor(tag, constructor)


def load_yaml(source: str | bytes) -> Any:
    """Parse YAML text with the C4SP safe loader.

    Args:
        source: YAML document as text or bytes (UTF-8).

    Returns:
        The parsed document (mapping, sequence or scalar).

    Raises:
        yaml.YAMLError: If the document is invalid or uses an unknown tag.
        YamlTagError: If a custom tag payload is invalid.
    """
    # C4SPSafeLoader derives from yaml.SafeLoader and only registers safe
    # constructors, so no arbitrary object can be instantiated.
    return yaml.load(source, Loader=C4SPSafeLoader)  # noqa: S506


def load_yaml_file(path: str | Path) -> Any:
    """Load and parse a YAML file with the C4SP safe loader.

    Args:
        path: Path of the YAML file (read as UTF-8).

    Returns:
        The parsed document (mapping, sequence or scalar).

    Raises:
        OSError: If the file cannot be read.
        YamlLoadError: If the file content is not valid YAML; the message
            includes the file path and the underlying parser error.
        YamlTagError: If a custom tag payload is invalid.
    """
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    try:
        # Safe loader (see load_yaml): parsing never instantiates objects.
        return yaml.load(text, Loader=C4SPSafeLoader)  # noqa: S506
    except yaml.YAMLError as exc:
        raise YamlLoadError(f"Invalid YAML in {file_path}: {exc}") from exc
