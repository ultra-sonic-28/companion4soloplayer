"""Generic single-selection step (race, class, alignment...)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from companion4soloplayer.core.creation.context import CharacterCreationContext, parse_path
from companion4soloplayer.core.creation.inputs import InputField, InputKind, InputProvider
from companion4soloplayer.core.creation.steps.base import (
    CreationStep,
    StepConfigurationError,
    catalog_names,
)

OptionsSource = Sequence[str] | Callable[[CharacterCreationContext], Sequence[str]]


class SelectionStep(CreationStep):
    """Ask the player to pick exactly one option from a list.

    The option list is either an inline sequence (``options``) or a
    catalog of the game system (``catalog``, a key of
    ``context.system``). A callable ``options`` source may be supplied
    programmatically to derive the list from the current state.

    Two common configurations:

    - **optional selection** (``optional=True``): a missing answer
      resolves to None, which is how a *race or class that may not
      exist* is skipped;
    - **no catalog at all**: the step is *not applicable* and the
      pipeline skips it (game system without races).

    Args:
        step_id: Unique identifier of the step; also the answer key.
        target: State path storing the selection (``choices.race``...).
        catalog: Key of the catalog in ``context.system``.
        options: Inline option list, or a callable computing it from
            the current state.
        prompt: Question asked to the player.
        optional: When True a missing answer resolves to None.
        label: Human-readable label.

    Raises:
        StepConfigurationError: If ``step_id`` is empty, ``target`` is
            not a valid leaf path, or neither/both of ``catalog`` and
            ``options`` are provided.
    """

    def __init__(
        self,
        step_id: str,
        *,
        target: str,
        catalog: str | None = None,
        options: OptionsSource | None = None,
        prompt: str | None = None,
        optional: bool = False,
        label: str = "",
    ) -> None:
        """Initialize the step.

        Args:
            step_id: Unique identifier of the step.
            target: State path storing the selection.
            catalog: Key of the catalog in the system data.
            options: Inline option list or callable source.
            prompt: Question asked to the player.
            optional: Whether a missing answer resolves to None.
            label: Human-readable label.
        """
        super().__init__(step_id, label=label)
        parts = parse_path(target)
        if len(parts) < 2:
            raise StepConfigurationError(
                f"SelectionStep target must be a leaf path, got {target!r}"
            )
        if (catalog is None) == (options is None):
            raise StepConfigurationError(
                "SelectionStep requires exactly one of 'catalog' or 'options'"
            )
        if isinstance(options, Sequence) and not isinstance(options, (str, bytes)):
            for position, option in enumerate(options):
                if not isinstance(option, str) or not option.strip():
                    raise StepConfigurationError(
                        f"Inline option #{position + 1} of step {step_id!r} must be a "
                        "non-empty string"
                    )
        elif options is not None and not callable(options):
            raise StepConfigurationError(
                f"'options' of step {step_id!r} must be a sequence or a callable"
            )
        self._target = target
        self._catalog = catalog
        self._options_source = options
        self._prompt = prompt or f"Select a value for {target}"
        self._optional = bool(optional)

    @property
    def target(self) -> str:
        """Return the state path storing the selection."""
        return self._target

    def available(self, context: CharacterCreationContext) -> list[str]:
        """Return the option list for the current state.

        Args:
            context: Current creation state.

        Returns:
            The available options (empty when the game system has no
            such data).

        Raises:
            StepConfigurationError: If the configured catalog is
                malformed.
        """
        if callable(self._options_source):
            return [str(option) for option in self._options_source(context)]
        if self._options_source is not None:
            return list(self._options_source)
        if self._catalog is None:
            return []
        return catalog_names(context.system, self._catalog)

    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Tell whether the step must run.

        Args:
            context: Current creation state.

        Returns:
            True when at least one option is available.
        """
        return bool(self.available(context))

    def describe_inputs(self, context: CharacterCreationContext) -> tuple[InputField, ...]:
        """Describe the selection as one single-choice field.

        Args:
            context: Current creation state (resolves the available
                options).

        Returns:
            One ``CHOICE`` field listing the available options, or an
            empty tuple when the game system declares no such data
            (the step is then skipped by the pipeline).
        """
        options = self.available(context)
        if not options:
            return ()
        return (
            InputField(
                key=self.step_id,
                label=self._prompt,
                kind=InputKind.CHOICE,
                options=tuple(options),
                required=not self._optional,
            ),
        )

    def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
        """Ask for the selection and store it at ``target``.

        Args:
            context: Current creation state, updated in place.
            inputs: Answer source of the session.

        Raises:
            InputError: If the answer is missing (and not optional) or
                is not one of the available options.
            StepConfigurationError: If the catalog is malformed.
        """
        options = self.available(context)
        if not options:
            return
        choice = inputs.ask_choice(self.step_id, self._prompt, options, allow_none=self._optional)
        context.set(self._target, choice)

    def validate(self, context: CharacterCreationContext) -> list[str]:
        """Validate the stored selection.

        Args:
            context: Current creation state.

        Returns:
            Error messages; empty when the selection is valid.
        """
        errors: list[str] = []
        if not context.has(self._target):
            if not self._optional:
                errors.append(f"No selection recorded at {self._target!r}")
            return errors
        value = context.get(self._target)
        if value is None:
            if not self._optional:
                errors.append(f"A selection is required at {self._target!r}")
            return errors
        if value not in self.available(context):
            errors.append(f"{value!r} selected at {self._target!r} is not an available option")
        return errors
