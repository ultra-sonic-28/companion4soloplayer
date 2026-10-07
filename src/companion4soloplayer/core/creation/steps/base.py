"""Base classes shared by the generic creation steps.

The :class:`CreationStep` abstract class defines the lifecycle used by
the pipeline:

1. :meth:`CreationStep.is_applicable` tells whether the step must run
   for the current state (a system without races simply never declares
   or returns False for its race step);
2. :meth:`CreationStep.execute` collects the answer through the
   :class:`~companion4soloplayer.core.creation.inputs.InputProvider`
   and writes the state;
3. :meth:`CreationStep.validate` checks the state and returns the list
   of error messages (empty means valid).

The pipeline then evaluates the condition/effect rules automatically
before moving to the next step.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from companion4soloplayer.core.creation.context import CharacterCreationContext
from companion4soloplayer.core.creation.inputs import InputProvider


class StepConfigurationError(ValueError):
    """Raised when a step is misconfigured (bad catalog, mode, path...)."""


class StepStatus(StrEnum):
    """Outcome status of one pipeline step."""

    EXECUTED = "executed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class StepResult:
    """Record of one step processed by the pipeline.

    Attributes:
        step_id: Identifier of the step.
        status: Outcome (executed, skipped or failed).
        errors: Validation or input error messages (empty unless the
            status is ``failed``).
    """

    step_id: str
    status: StepStatus
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """Tell whether the step completed without error."""
        return self.status is not StepStatus.FAILED

    @property
    def executed(self) -> bool:
        """Tell whether the step actually ran."""
        return self.status is StepStatus.EXECUTED


class CreationStep(ABC):
    """Abstract base class of every character creation step.

    Subclasses configure themselves in their constructor (the workflow
    YAML passes the parameters) and stay stateless between runs, so a
    pipeline can be replayed with a fresh context.

    Args:
        step_id: Unique identifier inside the pipeline; also the
            default answer key of the step.
        label: Human-readable label (defaults to ``step_id``).

    Raises:
        StepConfigurationError: If ``step_id`` is empty.
    """

    def __init__(self, step_id: str, *, label: str = "") -> None:
        """Initialize the step.

        Args:
            step_id: Unique identifier inside the pipeline.
            label: Human-readable label (defaults to ``step_id``).
        """
        if not isinstance(step_id, str) or not step_id.strip():
            raise StepConfigurationError("A creation step requires a non-empty step_id")
        self._step_id = step_id.strip()
        self._label = label.strip() or self._step_id

    @property
    def step_id(self) -> str:
        """Return the unique identifier of the step."""
        return self._step_id

    @property
    def label(self) -> str:
        """Return the human-readable label of the step."""
        return self._label

    @abstractmethod
    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Tell whether the step must run for this state.

        Args:
            context: Current creation state.

        Returns:
            True when the step applies (its data exists in the game
            system and it has something to do).
        """
        ...

    @abstractmethod
    def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
        """Collect the answers and write them into the context.

        Args:
            context: Current creation state, updated in place.
            inputs: Answer source of the session.

        Raises:
            InputError: If an answer is missing or malformed.
            StepConfigurationError: If the step cannot run with the
                current game data (unknown strategy, broken catalog...).
        """
        ...

    @abstractmethod
    def validate(self, context: CharacterCreationContext) -> list[str]:
        """Validate the state written by :meth:`execute`.

        Args:
            context: Current creation state.

        Returns:
            The list of error messages, empty when the state is valid.
        """
        ...

    def __repr__(self) -> str:
        """Return a compact debugging representation."""
        return f"<{type(self).__name__} {self._step_id!r}>"


def catalog_names(system: Mapping[str, Any], key: str) -> list[str]:
    """Extract the option names of a catalog stored in ``system``.

    Catalog entries are either plain strings or mappings holding a
    ``name`` entry. A missing catalog yields an empty list, which makes
    the dependent step *not applicable*: a game system without races
    or spells simply skips those steps.

    Args:
        system: Read-only game data of the context.
        key: Catalog key (``races``, ``classes``, ``skills``...).

    Returns:
        The catalog names, in declaration order.

    Raises:
        StepConfigurationError: If the catalog exists but is malformed
            (not a sequence, entry without a valid ``name``).
    """
    catalog = system.get(key)
    if catalog is None:
        return []
    if isinstance(catalog, (str, bytes)) or not isinstance(catalog, Sequence):
        raise StepConfigurationError(
            f"Catalog {key!r} must be a sequence of entries, got {type(catalog).__name__}"
        )
    names: list[str] = []
    for position, entry in enumerate(catalog):
        name: Any
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, Mapping):
            name = entry.get("name")
        else:
            name = None
        if not isinstance(name, str) or not name.strip():
            raise StepConfigurationError(
                f"Catalog {key!r} entry #{position + 1} must define a non-empty 'name'"
            )
        names.append(name)
    return names
