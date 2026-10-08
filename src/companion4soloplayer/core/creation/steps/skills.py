"""Generic skill selection step (free, inherited or none)."""

from __future__ import annotations

from companion4soloplayer.core.creation.context import CharacterCreationContext, parse_path
from companion4soloplayer.core.creation.inputs import InputField, InputKind, InputProvider
from companion4soloplayer.core.creation.steps.base import (
    CreationStep,
    StepConfigurationError,
    catalog_names,
)

#: Skill selection modes understood by the step.
MODES: tuple[str, ...] = ("free", "inherited", "none")


class SkillSelectionStep(CreationStep):
    """Collect the skills of the character.

    Three modes cover the possible skill models of a game system:

    - ``free``: the player picks 0..n skills from the catalog; the raw
      picks are stored at ``target`` (``choices.skills``) and mirrored
      as base values at ``working_target`` (``values.skills``) so the
      rules engine can layer the inherited skills on top;
    - ``inherited``: the step does not ask anything (it is *not
      applicable*); every skill comes from the rules granting them for
      the chosen race/class;
    - ``none``: the game system has no skills at all (the step is not
      applicable and no rule should target skills).

    Args:
        step_id: Unique identifier of the step; also the answer key in
            ``free`` mode.
        mode: ``free``, ``inherited`` or ``none``.
        catalog: Key of the skill catalog in ``context.system``.
        target: State path storing the raw picks.
        working_target: State path of the effective skill list base
            (rule grants are layered on top of it).
        min_count: Minimum number of picks in ``free`` mode.
        max_count: Maximum number of picks in ``free`` mode.
        prompt: Question asked to the player.
        label: Human-readable label.

    Raises:
        StepConfigurationError: If ``step_id`` is empty, a target is
            not a valid leaf path, or the mode is unknown.
    """

    def __init__(
        self,
        step_id: str = "skills",
        *,
        mode: str = "free",
        catalog: str = "skills",
        target: str = "choices.skills",
        working_target: str = "values.skills",
        min_count: int = 0,
        max_count: int | None = None,
        prompt: str | None = None,
        label: str = "",
    ) -> None:
        """Initialize the step.

        Args:
            step_id: Unique identifier of the step.
            mode: ``free``, ``inherited`` or ``none``.
            catalog: Key of the skill catalog in the system data.
            target: State path storing the raw picks.
            working_target: State path of the effective skill list base.
            min_count: Minimum number of picks.
            max_count: Maximum number of picks.
            prompt: Question asked to the player.
            label: Human-readable label.

        Raises:
            StepConfigurationError: If the configuration is invalid.
        """
        super().__init__(step_id, label=label)
        if mode not in MODES:
            raise StepConfigurationError(
                f"Unknown skill selection mode {mode!r} (available: {', '.join(MODES)})"
            )
        parse_path(target)
        parse_path(working_target)
        if min_count < 0:
            raise StepConfigurationError(f"min_count must be >= 0, got {min_count}")
        if max_count is not None and max_count < min_count:
            raise StepConfigurationError(
                f"max_count ({max_count}) cannot be lower than min_count ({min_count})"
            )
        self._mode = mode
        self._catalog = catalog
        self._target = target
        self._working_target = working_target
        self._min_count = min_count
        self._max_count = max_count
        self._prompt = prompt or "Choose your skills"

    @property
    def mode(self) -> str:
        """Return the configured skill selection mode."""
        return self._mode

    def available(self, context: CharacterCreationContext) -> list[str]:
        """Return the skill catalog of the game system.

        Args:
            context: Current creation state.

        Returns:
            The skill names, or an empty list when the system declares
            no skills.

        Raises:
            StepConfigurationError: If the catalog is malformed.
        """
        return catalog_names(context.system, self._catalog)

    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Tell whether the step must run.

        Args:
            context: Current creation state.

        Returns:
            True only in ``free`` mode with a non-empty catalog.
        """
        if self._mode != "free":
            return False
        return bool(self.available(context))

    def describe_inputs(self, context: CharacterCreationContext) -> tuple[InputField, ...]:
        """Describe the skill picks as one multiple-choice field.

        Args:
            context: Current creation state (provides the catalog).

        Returns:
            One ``CHOICES`` field in ``free`` mode with a non-empty
            catalog, or an empty tuple (``inherited`` and ``none``
            modes ask nothing).
        """
        if self._mode != "free":
            return ()
        options = self.available(context)
        if not options:
            return ()
        return (
            InputField(
                key=self.step_id,
                label=self._prompt,
                kind=InputKind.CHOICES,
                options=tuple(options),
                required=self._min_count > 0,
                min_count=self._min_count,
                max_count=self._max_count,
            ),
        )

    def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
        """Ask for the skill picks and mirror them to the working list.

        Args:
            context: Current creation state, updated in place.
            inputs: Answer source of the session.

        Raises:
            InputError: If the answer is missing (below ``min_count``)
                or breaks the count bounds.
            StepConfigurationError: If the catalog is malformed.
        """
        options = self.available(context)
        if not options:
            return
        picks = inputs.ask_many(
            self.step_id,
            self._prompt,
            options,
            min_count=self._min_count,
            max_count=self._max_count,
        )
        context.set(self._target, list(picks))
        context.set(self._working_target, list(picks))

    def validate(self, context: CharacterCreationContext) -> list[str]:
        """Validate the stored skill picks.

        Args:
            context: Current creation state.

        Returns:
            Error messages; empty when the picks are a subset of the
            catalog within the count bounds and mirrored correctly.
        """
        errors: list[str] = []
        options = self.available(context)
        raw = context.peek(self._target, [])
        if not isinstance(raw, (list, tuple)):
            errors.append(f"Skill picks at {self._target!r} must be a list")
            return errors
        picks = list(raw)
        unknown = [pick for pick in picks if pick not in options]
        if unknown:
            errors.append(f"Unknown skill pick(s) at {self._target!r}: {unknown!r}")
        if len(picks) < self._min_count:
            errors.append(f"At least {self._min_count} skill(s) must be picked, got {len(picks)}")
        if self._max_count is not None and len(picks) > self._max_count:
            errors.append(f"At most {self._max_count} skill(s) may be picked, got {len(picks)}")
        working = context.peek(self._working_target, [])
        working_list = list(working) if isinstance(working, (list, tuple)) else working
        if working_list != picks:
            errors.append(f"The working skill list {self._working_target!r} must mirror the picks")
        return errors
