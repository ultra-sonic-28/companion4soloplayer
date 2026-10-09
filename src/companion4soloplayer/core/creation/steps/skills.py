"""Generic skill selection step (free, inherited or none)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from companion4soloplayer.core.creation.context import CharacterCreationContext, parse_path
from companion4soloplayer.core.creation.inputs import InputField, InputKind, InputProvider
from companion4soloplayer.core.creation.steps.base import (
    CreationStep,
    StepConfigurationError,
    catalog_names,
)

#: Skill selection modes understood by the step.
MODES: tuple[str, ...] = ("free", "inherited", "none")

#: Signature of the skill filter: ``(skill, context) -> is_available``.
SkillFilter = Callable[[Mapping[str, Any], CharacterCreationContext], bool]


class SkillSelectionStep(CreationStep):
    """Collect the skills of the character.

    Three modes cover the possible skill models of a game system:

    - ``free``: the player picks 0..n skills from the catalog, kept
      available by the optional ``skill_filter``; the raw
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
        skill_filter: Predicate keeping the skills available for the
            current character; ``None`` keeps the whole catalog.
        prompt: Question asked to the player.
        label: Human-readable label.

    Raises:
        StepConfigurationError: If ``step_id`` is empty, a target is
            not a valid leaf path, the mode is unknown, or the filter
            is not callable.
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
        skill_filter: SkillFilter | None = None,
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
            skill_filter: Predicate keeping available skills.
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
        if skill_filter is not None and not callable(skill_filter):
            raise StepConfigurationError("skill_filter must be callable")
        self._mode = mode
        self._catalog = catalog
        self._target = target
        self._working_target = working_target
        self._min_count = min_count
        self._max_count = max_count
        self._skill_filter = skill_filter
        self._prompt = prompt or "Choose your skills"

    @property
    def mode(self) -> str:
        """Return the configured skill selection mode."""
        return self._mode

    def available(self, context: CharacterCreationContext) -> list[str]:
        """Return the skills available for the current character.

        The catalog goes through the configured ``skill_filter`` when
        one is declared, so an option list depending on the state (the
        skills unlocked by the chosen race/class, for instance) only
        proposes the relevant entries.

        Args:
            context: Current creation state (the filter receives the
                catalog entries together with the state).

        Returns:
            The names of the catalog entries passing the filter (the
            whole catalog when no filter is configured), or an empty
            list when the system declares no skills.

        Raises:
            StepConfigurationError: If the catalog or the filter is
                malformed.
        """
        entries = context.system.get(self._catalog)
        if entries is None:
            return []
        names = catalog_names(context.system, self._catalog)
        if self._skill_filter is None:
            return names
        if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
            raise StepConfigurationError(f"Catalog {self._catalog!r} must be a sequence of entries")
        available: list[str] = []
        for name, entry in zip(names, entries, strict=True):
            if not isinstance(entry, Mapping):
                raise StepConfigurationError(
                    f"Catalog {self._catalog!r} entries must be mappings to be filtered"
                )
            try:
                keep = self._skill_filter(entry, context)
            except Exception as exc:
                raise StepConfigurationError(
                    f"The skill filter of step {self.step_id!r} failed for {name!r}: {exc}"
                ) from exc
            if keep:
                available.append(name)
        return available

    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Tell whether the step must run.

        Args:
            context: Current creation state.

        Returns:
            True only in ``free`` mode with at least one available
            skill.
        """
        if self._mode != "free":
            return False
        return bool(self.available(context))

    def describe_inputs(self, context: CharacterCreationContext) -> tuple[InputField, ...]:
        """Describe the skill picks as one multiple-choice field.

        The step keeps describing its field even when the filter
        currently removes every entry (before a race/class is chosen,
        for instance): a UI then renders the block with an *empty*
        option list, which fills in as soon as the state unlocks
        skills.

        Args:
            context: Current creation state (provides the catalog and
                feeds the filter).

        Returns:
            One ``CHOICES`` field in ``free`` mode with a non-empty
            catalog (its options may be empty while nothing is
            available), or an empty tuple (``inherited``/``none``
            modes and a system without skills ask nothing).
        """
        if self._mode != "free":
            return ()
        entries = context.system.get(self._catalog)
        if entries is None or (isinstance(entries, Sequence) and not entries):
            return ()
        return (
            InputField(
                key=self.step_id,
                label=self._prompt,
                kind=InputKind.CHOICES,
                options=tuple(self.available(context)),
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
