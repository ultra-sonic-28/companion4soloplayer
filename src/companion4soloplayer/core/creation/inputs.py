"""Input providers used by the character creation steps.

The creation steps never talk to a UI directly: they ask the attached
:class:`InputProvider` for the answer of the current question. This
keeps the engine headless and testable:

- the UI implements an interactive provider (dialogs, forms...);
- tests and automated flows use :class:`MappingInputProvider`, which
  replays pre-recorded answers keyed by question.

Answer keys are stable identifiers built by the steps:

============================  ==========================================
Question                      Answer key
============================  ==========================================
Character name                ``<step_id>.name``
Background                    ``<step_id>.background``
Single selection              ``<step_id>`` (e.g. ``race``, ``class``)
Many selections               ``<step_id>`` (e.g. ``skills``, ``spells``)
One attribute value           ``<step_id>.<attribute>`` (e.g.
                              ``attributes.strength``)
============================  ==========================================

Before any answer exists, a step may also *describe* the data it is
going to ask: :class:`InputKind` and :class:`InputField` carry the
answer key, the widget category (text, dice, choice...) and the
available options of one data item. Those descriptions are produced by
``CreationStep.describe_inputs()`` and consumed by the UI to build a
form dynamically, in the step order declared by the workflow.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

#: Internal marker for "the provider holds no answer for this key".
_MISSING: Any = object()


class InputError(Exception):
    """Base class raised when an answer cannot be collected."""


class MissingInputError(InputError):
    """Raised when a required answer is absent from the provider."""


class InvalidAnswerError(InputError):
    """Raised when an answer has the wrong type or is out of bounds."""


class InputKind(StrEnum):
    """Category of one data item, mapped to a widget by the UI.

    The kind tells the UI *how* to render the field and tells the
    reader *which* provider method will collect the answer:

    ===========  ==================  ====================================
    Kind         Provider method     Typical widget
    ===========  ==================  ====================================
    ``TEXT``     ``ask_text``        single-line text edit
    ``NUMBER``   ``ask_number``      single-line numeric text edit
    ``DICE``     ``ask_number``      label + die button (rolled value)
    ``CHOICE``   ``ask_choice``      single-selection list
    ``CHOICES``  ``ask_many``        multiple-selection list
    ===========  ==================  ====================================
    """

    TEXT = "text"
    NUMBER = "number"
    DICE = "dice"
    CHOICE = "choice"
    CHOICES = "choices"


@dataclass(frozen=True)
class InputField:
    """Description of one data item collected by a creation step.

    A field is pure data (no widget): a step declares what it is going
    to ask through ``CreationStep.describe_inputs()`` and the UI turns
    each field into a widget of the kind declared here.

    Attributes:
        key: Stable answer key forwarded to the ``InputProvider``
            (e.g. ``identity.name``, ``attributes.strength``).
        label: Human-readable label displayed next to the widget.
        kind: Widget/answer category (see :class:`InputKind`).
        options: Available options of a ``CHOICE``/``CHOICES`` field.
        required: Whether an empty answer is rejected.
        min_count: Minimum number of picks of a ``CHOICES`` field.
        max_count: Maximum number of picks of a ``CHOICES`` field
            (None means unlimited).
        min_value: Inclusive lower bound of a ``NUMBER``/``DICE``
            field.
        max_value: Inclusive upper bound of a ``NUMBER``/``DICE``
            field.
        roll: Callable producing the dice value of a ``DICE`` field
            (None when no die is involved).
    """

    key: str
    label: str
    kind: InputKind
    options: tuple[str, ...] = ()
    required: bool = False
    min_count: int = 0
    max_count: int | None = None
    min_value: int | None = None
    max_value: int | None = None
    roll: Callable[[], int] | None = None


@runtime_checkable
class InputProvider(Protocol):
    """Contract implemented by every answer source of a creation step."""

    def ask_text(
        self,
        key: str,
        prompt: str,
        *,
        default: str | None = None,
        required: bool = True,
    ) -> str:
        """Ask a free-form text answer.

        Args:
            key: Stable answer key.
            prompt: Human-readable question.
            default: Value returned when no answer is recorded.
            required: When True, a missing or empty answer raises.

        Returns:
            The answer as a string.
        """
        ...

    def ask_choice(
        self,
        key: str,
        prompt: str,
        options: Sequence[Any],
        *,
        allow_none: bool = False,
    ) -> Any:
        """Ask a single choice among ``options``.

        Args:
            key: Stable answer key.
            prompt: Human-readable question.
            options: Available options.
            allow_none: When True, a missing answer resolves to None.

        Returns:
            The selected option, or None when allowed and unanswered.
        """
        ...

    def ask_many(
        self,
        key: str,
        prompt: str,
        options: Sequence[Any],
        *,
        min_count: int = 0,
        max_count: int | None = None,
    ) -> list[Any]:
        """Ask several choices among ``options``.

        Args:
            key: Stable answer key.
            prompt: Human-readable question.
            options: Available options.
            min_count: Minimum number of selections.
            max_count: Maximum number of selections (None = unlimited).

        Returns:
            The selected options, in answer order.
        """
        ...

    def ask_number(
        self,
        key: str,
        prompt: str,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
        default: int | None = None,
    ) -> int:
        """Ask an integer answer.

        Args:
            key: Stable answer key.
            prompt: Human-readable question.
            minimum: Inclusive lower bound.
            maximum: Inclusive upper bound.
            default: Value returned when no answer is recorded.

        Returns:
            The answer as an integer.
        """
        ...


class MappingInputProvider:
    """Replay pre-recorded answers stored in a mapping.

    The provider validates the *shape* of each answer (missing key,
    wrong type, value outside the options or the bounds) and raises the
    :class:`InputError` family; the semantic validation of the written
    state stays the responsibility of the steps.

    Args:
        answers: Mapping of answer key to recorded answer.

    Example:
        >>> provider = MappingInputProvider({"identity.name": "Aria"})
        >>> provider.ask_text("identity.name", "Name?")
        'Aria'
    """

    def __init__(self, answers: Mapping[str, Any] | None = None) -> None:
        """Initialize the provider.

        Args:
            answers: Mapping of answer key to recorded answer.
        """
        self._answers: dict[str, Any] = dict(answers or {})

    @property
    def answers(self) -> Mapping[str, Any]:
        """Return a copy of the recorded answers."""
        return dict(self._answers)

    def ask_text(
        self,
        key: str,
        prompt: str,
        *,
        default: str | None = None,
        required: bool = True,
    ) -> str:
        """Return a recorded text answer.

        Args:
            key: Stable answer key.
            prompt: Human-readable question (used in error messages).
            default: Value returned when no answer is recorded.
            required: When True, a missing or empty answer raises.

        Returns:
            The answer as a string.

        Raises:
            MissingInputError: If the answer is absent and required.
            InvalidAnswerError: If the answer is empty and required, or
                is not a scalar value.
        """
        answer = self._answers.get(key, _MISSING)
        if answer is _MISSING or answer is None:
            if default is not None:
                return default
            if required:
                raise MissingInputError(f"Missing answer for {key!r} ({prompt!r})")
            return ""
        if isinstance(answer, (list, tuple, dict, set)):
            raise InvalidAnswerError(
                f"Answer for {key!r} must be a text value, got {type(answer).__name__}"
            )
        text = str(answer)
        if required and not text.strip():
            raise InvalidAnswerError(f"Answer for {key!r} must not be empty ({prompt!r})")
        return text

    def ask_choice(
        self,
        key: str,
        prompt: str,
        options: Sequence[Any],
        *,
        allow_none: bool = False,
    ) -> Any:
        """Return a recorded single choice.

        Args:
            key: Stable answer key.
            prompt: Human-readable question (used in error messages).
            options: Available options.
            allow_none: When True, a missing answer resolves to None.

        Returns:
            The selected option, or None when allowed and unanswered.

        Raises:
            MissingInputError: If the answer is absent and None is not
                allowed.
            InvalidAnswerError: If the answer is not one of the options.
        """
        answer = self._answers.get(key, _MISSING)
        if answer is _MISSING or answer is None:
            if allow_none:
                return None
            raise MissingInputError(f"Missing answer for {key!r} ({prompt!r})")
        if answer not in options:
            raise InvalidAnswerError(
                f"Answer {answer!r} for {key!r} is not one of the "
                f"{len(options)} available option(s)"
            )
        return answer

    def ask_many(
        self,
        key: str,
        prompt: str,
        options: Sequence[Any],
        *,
        min_count: int = 0,
        max_count: int | None = None,
    ) -> list[Any]:
        """Return a recorded multiple choice answer.

        Args:
            key: Stable answer key.
            prompt: Human-readable question (used in error messages).
            options: Available options.
            min_count: Minimum number of selections.
            max_count: Maximum number of selections (None = unlimited).

        Returns:
            The selected options, in answer order.

        Raises:
            MissingInputError: If the answer is absent and
                ``min_count`` is not satisfied.
            InvalidAnswerError: If the answer is not a sequence of
                options, or breaks the count bounds.
        """
        answer = self._answers.get(key, _MISSING)
        if answer is _MISSING or answer is None:
            if min_count <= 0:
                return []
            raise MissingInputError(f"Missing answer for {key!r} ({prompt!r})")
        if isinstance(answer, (str, bytes)) or not isinstance(answer, Sequence):
            raise InvalidAnswerError(
                f"Answer for {key!r} must be a sequence, got {type(answer).__name__}"
            )
        picks = list(answer)
        if len(picks) < min_count:
            raise InvalidAnswerError(
                f"Answer for {key!r} needs at least {min_count} selection(s), got {len(picks)}"
            )
        if max_count is not None and len(picks) > max_count:
            raise InvalidAnswerError(
                f"Answer for {key!r} accepts at most {max_count} selection(s), got {len(picks)}"
            )
        unknown = [pick for pick in picks if pick not in options]
        if unknown:
            raise InvalidAnswerError(
                f"Answer for {key!r} contains unavailable option(s): {unknown!r}"
            )
        return picks

    def ask_number(
        self,
        key: str,
        prompt: str,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
        default: int | None = None,
    ) -> int:
        """Return a recorded integer answer.

        Args:
            key: Stable answer key.
            prompt: Human-readable question (used in error messages).
            minimum: Inclusive lower bound.
            maximum: Inclusive upper bound.
            default: Value returned when no answer is recorded.

        Returns:
            The answer as an integer.

        Raises:
            MissingInputError: If the answer is absent and no default
                is provided.
            InvalidAnswerError: If the answer is not an integer or lies
                outside the bounds.
        """
        answer = self._answers.get(key, _MISSING)
        if answer is _MISSING or answer is None:
            if default is not None:
                answer = default
            else:
                raise MissingInputError(f"Missing answer for {key!r} ({prompt!r})")
        number = self._to_int(key, answer)
        if minimum is not None and number < minimum:
            raise InvalidAnswerError(f"Answer for {key!r} must be >= {minimum}, got {number}")
        if maximum is not None and number > maximum:
            raise InvalidAnswerError(f"Answer for {key!r} must be <= {maximum}, got {number}")
        return number

    @staticmethod
    def _to_int(key: str, answer: Any) -> int:
        """Coerce an answer to ``int``.

        Args:
            key: Stable answer key (used in error messages).
            answer: Raw answer.

        Returns:
            The answer as an integer.

        Raises:
            InvalidAnswerError: If the answer is a boolean, a non
                integral number or a non numeric text.
        """
        if isinstance(answer, bool):
            raise InvalidAnswerError(f"Answer for {key!r} must be an integer, got a boolean")
        if isinstance(answer, int):
            return answer
        if isinstance(answer, float) and answer.is_integer():
            return int(answer)
        if isinstance(answer, str):
            try:
                return int(answer.strip(), 10)
            except ValueError as exc:
                raise InvalidAnswerError(
                    f"Answer {answer!r} for {key!r} is not an integer"
                ) from exc
        raise InvalidAnswerError(
            f"Answer for {key!r} must be an integer, got {type(answer).__name__}"
        )
