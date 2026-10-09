"""Generic identity step (name and background of the character)."""

from __future__ import annotations

from collections.abc import Sequence

from companion4soloplayer.core.creation.context import CharacterCreationContext
from companion4soloplayer.core.creation.inputs import InputField, InputKind, InputProvider
from companion4soloplayer.core.creation.steps.base import CreationStep


class IdentityStep(CreationStep):
    """Collect the identity of the character (name and background).

    The step always applies: every game system has a name. The
    background is free text by default; pass ``background_options`` to
    turn it into a choice among a fixed list.

    Args:
        step_id: Unique identifier of the step (default answer keys are
            ``<step_id>.name`` and ``<step_id>.background``).
        label: Human-readable label.
        name_prompt: Question asked for the name.
        background_prompt: Question asked for the background.
        background_options: Optional list of predefined backgrounds;
            when omitted the background is free text.
        name_required: When True (default) the name must not be empty.
        background_required: When True the background must be filled.

    Raises:
        StepConfigurationError: If ``step_id`` is empty.

    Example:
        >>> from companion4soloplayer.core.creation.inputs import (
        ...     MappingInputProvider)
        >>> step = IdentityStep()
        >>> context = CharacterCreationContext()
        >>> step.execute(context, MappingInputProvider(
        ...     {"identity.name": "Aria", "identity.background": "Sellsword"}))
        >>> step.validate(context)
        []
    """

    def __init__(
        self,
        step_id: str = "identity",
        *,
        label: str = "",
        name_prompt: str = "Character name",
        background_prompt: str = "Background",
        background_options: Sequence[str] | None = None,
        name_required: bool = True,
        background_required: bool = False,
    ) -> None:
        """Initialize the step.

        Args:
            step_id: Unique identifier of the step.
            label: Human-readable label.
            name_prompt: Question asked for the name.
            background_prompt: Question asked for the background.
            background_options: Optional predefined backgrounds.
            name_required: Whether the name must not be empty.
            background_required: Whether the background must be filled.
        """
        super().__init__(step_id, label=label)
        self._name_prompt = name_prompt
        self._background_prompt = background_prompt
        self._background_options = (
            tuple(background_options) if background_options is not None else None
        )
        self._name_required = bool(name_required)
        self._background_required = bool(background_required)

    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Tell whether the step must run.

        Args:
            context: Current creation state (unused).

        Returns:
            Always True: every character has an identity.
        """
        return True

    def describe_inputs(self, context: CharacterCreationContext) -> tuple[InputField, ...]:
        """Describe the name and background fields of the character.

        Args:
            context: Current creation state (unused).

        Returns:
            One ``TEXT`` field for the name and one field for the
            background: a ``CHOICE`` field when ``background_options``
            is configured, a multi-line ``TEXTAREA`` field otherwise.
        """
        background_kind = (
            InputKind.CHOICE if self._background_options is not None else InputKind.TEXTAREA
        )
        return (
            InputField(
                key=f"{self.step_id}.name",
                label=self._name_prompt,
                kind=InputKind.TEXT,
                required=self._name_required,
            ),
            InputField(
                key=f"{self.step_id}.background",
                label=self._background_prompt,
                kind=background_kind,
                options=tuple(self._background_options or ()),
                required=self._background_required,
            ),
        )

    def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
        """Ask for the name and the background, then store them.

        Args:
            context: Current creation state, updated in place under
                ``choices.identity``.
            inputs: Answer source of the session.

        Raises:
            InputError: If a required answer is missing or empty.
        """
        name = inputs.ask_text(
            f"{self.step_id}.name", self._name_prompt, required=self._name_required
        )
        context.set("choices.identity.name", name)
        if self._background_options is not None:
            background = inputs.ask_choice(
                f"{self.step_id}.background",
                self._background_prompt,
                self._background_options,
                allow_none=not self._background_required,
            )
        else:
            background = inputs.ask_text(
                f"{self.step_id}.background",
                self._background_prompt,
                required=self._background_required,
            )
        context.set("choices.identity.background", background)

    def validate(self, context: CharacterCreationContext) -> list[str]:
        """Validate the stored identity.

        Args:
            context: Current creation state.

        Returns:
            Error messages; empty when the identity is valid.
        """
        errors: list[str] = []
        name = context.peek("choices.identity.name")
        if self._name_required and not (isinstance(name, str) and name.strip()):
            errors.append("A non-empty character name is required")
        elif name is not None and not isinstance(name, str):
            errors.append(f"The character name must be a text value, got {type(name).__name__}")
        background = context.peek("choices.identity.background")
        if self._background_required and not (isinstance(background, str) and background.strip()):
            errors.append("A background is required")
        elif background is not None and not isinstance(background, (str, type(None))):
            errors.append(f"The background must be a text value, got {type(background).__name__}")
        return errors
