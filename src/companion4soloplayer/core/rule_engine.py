"""
Hybrid rule engine module.

Game rules are described *declaratively* in YAML (``rules.yaml``) and may
bind Python rule elements (character creation, combat, loot, magic,
oracle, ...) through ``!pyclass`` references. This module fuses both
worlds:

- the YAML part stays pure data (loaded with the safe loader);
- the Python part is resolved and instantiated lazily by
  :class:`RuleEngine`, only when a rule element is actually requested.

Security model:

- parsing never imports anything (see
  :mod:`companion4soloplayer.core.yaml_loader`);
- absolute imports are restricted to an allow-list of module prefixes
  (:data:`DEFAULT_ALLOWED_MODULES`);
- ``local:`` references resolve inside the module that declared the rules
  (the plugin module), which keeps them valid both in development and in
  the compiled ``.pyd`` build, where the plugin ships as a single module.
"""

from __future__ import annotations

import importlib
import types
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from companion4soloplayer.core.yaml_loader import PyClassRef, load_yaml_file

#: Standard rule element kinds understood by the application.
RULE_KINDS: tuple[str, ...] = (
    "character_creation",
    "combat",
    "loot",
    "magic",
    "oracle",
    "special",
)

#: Modules that may be imported through an absolute ``!pyclass`` reference.
DEFAULT_ALLOWED_MODULES: tuple[str, ...] = ("companion4soloplayer",)

#: Key of the ``rules.yaml`` mapping declaring the rule implementations.
IMPLEMENTATIONS_KEY = "implementations"


class RuleEngineError(Exception):
    """Base class for rule engine errors."""


class UnknownRuleKindError(RuleEngineError):
    """Raised when a rule kind is not declared in ``implementations``."""


class ImplementationError(RuleEngineError):
    """Raised when a rule reference cannot be resolved or instantiated."""


class ImplementationNotAllowedError(ImplementationError):
    """Raised when a rule reference targets a module outside the allow-list."""


class RuleEngine:
    """Resolves and caches the Python components declared in YAML rules.

    Args:
        rules: Parsed ``rules.yaml`` document.
        base_module: Module used to resolve ``local:`` references, either
            the module object itself or its dotted name. Required as soon
            as the document contains a ``local:`` reference.
        allowed_modules: Module prefixes accepted for absolute references.

    Raises:
        RuleEngineError: If ``rules`` is not a mapping.
    """

    def __init__(
        self,
        rules: Mapping[str, Any],
        *,
        base_module: str | types.ModuleType | None = None,
        allowed_modules: Sequence[str] = DEFAULT_ALLOWED_MODULES,
    ) -> None:
        if not isinstance(rules, Mapping):
            raise RuleEngineError(f"Rules document must be a mapping, got {type(rules).__name__}")
        self._rules = dict(rules)
        self._base_module = base_module
        self._allowed_modules = tuple(allowed_modules)
        self._components: dict[str, Any] = {}

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        *,
        base_module: str | types.ModuleType | None = None,
        allowed_modules: Sequence[str] = DEFAULT_ALLOWED_MODULES,
    ) -> RuleEngine:
        """Load a rules document from a YAML file.

        Args:
            path: Path of the rules file (typically ``rules.yaml``).
            base_module: Module used to resolve ``local:`` references.
            allowed_modules: Module prefixes accepted for absolute references.

        Returns:
            The initialized rule engine.

        Raises:
            YamlLoadError: If the file is not valid YAML.
            RuleEngineError: If the file is empty or not a mapping.
        """
        data = load_yaml_file(path)
        if data is None:
            raise RuleEngineError(f"Rules document {path} is empty")
        return cls(data, base_module=base_module, allowed_modules=allowed_modules)

    # ------------------------------------------------------------------
    # Declarative side
    # ------------------------------------------------------------------

    @property
    def rules(self) -> dict[str, Any]:
        """Return a copy of the declarative rules document."""
        return dict(self._rules)

    def get(self, key: str, default: Any = None) -> Any:
        """Return a top-level section of the rules document.

        Args:
            key: Top-level key (``combat``, ``movement``, ...).
            default: Value returned when the key is absent.

        Returns:
            The section content.
        """
        return self._rules.get(key, default)

    @property
    def implementations(self) -> dict[str, PyClassRef]:
        """Return the declared rule implementations (kind -> reference).

        Raises:
            RuleEngineError: If ``implementations`` is not a mapping or
                contains a value that is neither a string nor a
                :class:`PyClassRef`.
        """
        raw = self._rules.get(IMPLEMENTATIONS_KEY, {})
        if not isinstance(raw, Mapping):
            raise RuleEngineError(
                f"'{IMPLEMENTATIONS_KEY}' must be a mapping, got {type(raw).__name__}"
            )
        result: dict[str, PyClassRef] = {}
        for kind, value in raw.items():
            if isinstance(value, PyClassRef):
                result[str(kind)] = value
            elif isinstance(value, str):
                result[str(kind)] = PyClassRef.parse(value)
            else:
                raise RuleEngineError(
                    f"Implementation for rule kind {kind!r} must be a !pyclass "
                    f"reference, got {type(value).__name__}"
                )
        return result

    @property
    def kinds(self) -> list[str]:
        """Return the sorted list of declared rule kinds."""
        return sorted(self.implementations)

    # ------------------------------------------------------------------
    # Hybrid side: resolution and instantiation
    # ------------------------------------------------------------------

    def resolve(self, ref: PyClassRef | str) -> Any:
        """Resolve a class reference to the referenced object (no instantiation).

        Args:
            ref: The reference, as a :class:`PyClassRef` or as a
                ``module:Class`` / ``local:Class`` string.

        Returns:
            The object referenced by ``ref``.

        Raises:
            YamlTagError: If a string reference is malformed.
            ImplementationNotAllowedError: If an absolute reference targets a
                module outside the allow-list.
            ImplementationError: If the module or attribute cannot be resolved,
                or if a ``local:`` reference is used without ``base_module``.
        """
        ref = PyClassRef.parse(ref) if isinstance(ref, str) else ref
        if ref.is_local:
            module = self._resolve_base_module()
        else:
            module = self._import_allowed_module(ref.module)
        try:
            return getattr(module, ref.attr)
        except AttributeError as exc:
            raise ImplementationError(
                f"Module {ref.module!r} has no attribute {ref.attr!r}"
            ) from exc

    def component(self, kind: str) -> Any:
        """Instantiate (and cache) the rule component declared for ``kind``.

        Args:
            kind: Rule kind key inside the ``implementations`` mapping.

        Returns:
            The component instance, created with the ``params`` declared
            in the YAML reference.

        Raises:
            UnknownRuleKindError: If ``kind`` is not declared.
            ImplementationNotAllowedError: If an absolute reference targets a
                module outside the allow-list.
            ImplementationError: If the reference cannot be resolved or the
                referenced object cannot be instantiated.
        """
        if kind in self._components:
            return self._components[kind]

        implementations = self.implementations
        if kind not in implementations:
            raise UnknownRuleKindError(
                f"Rule kind {kind!r} is not declared in '{IMPLEMENTATIONS_KEY}' "
                f"(available: {', '.join(sorted(implementations)) or 'none'})"
            )

        ref = implementations[kind]
        target = self.resolve(ref)
        if not callable(target):
            raise ImplementationError(
                f"Reference {ref.path!r} for rule kind {kind!r} is not callable"
            )
        try:
            instance = target(**dict(ref.params))
        except Exception as exc:
            raise ImplementationError(
                f"Cannot instantiate {ref.path!r} for rule kind {kind!r} "
                f"with params {dict(ref.params)!r}: {exc}"
            ) from exc

        self._components[kind] = instance
        return instance

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_base_module(self) -> types.ModuleType:
        """Return the module used for ``local:`` references.

        Raises:
            ImplementationError: If the module is unknown or cannot be imported.
        """
        base = self._base_module
        if base is None:
            raise ImplementationError(
                "A 'local:' reference requires base_module= to be set on the rule engine"
            )
        if isinstance(base, types.ModuleType):
            return base
        try:
            return importlib.import_module(base)
        except ImportError as exc:
            raise ImplementationError(f"Cannot import base module {base!r}: {exc}") from exc

    def _import_allowed_module(self, module_name: str) -> types.ModuleType:
        """Import ``module_name`` after checking it against the allow-list.

        Raises:
            ImplementationNotAllowedError: If the module is outside the allow-list.
            ImplementationError: If the module cannot be imported.
        """
        if not any(
            module_name == prefix or module_name.startswith(f"{prefix}.")
            for prefix in self._allowed_modules
        ):
            raise ImplementationNotAllowedError(
                f"Module {module_name!r} is outside the allowed prefixes "
                f"{self._allowed_modules!r}"
            )
        try:
            return importlib.import_module(module_name)
        except ImportError as exc:
            raise ImplementationError(f"Cannot import module {module_name!r}: {exc}") from exc

