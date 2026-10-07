"""Generic spell selection step (filtered choice, automatic or none)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from companion4soloplayer.core.creation.context import CharacterCreationContext, parse_path
from companion4soloplayer.core.creation.inputs import InputProvider
from companion4soloplayer.core.creation.steps.base import (
    CreationStep,
    StepConfigurationError,
    catalog_names,
)

#: Spell selection modes understood by the step.
MODES: tuple[str, ...] = ("choice", "auto", "none")

#: Signature of the spell filter: ``(spell, context) -> is_available``.
SpellFilter = Callable[[Mapping[str, Any], CharacterCreationContext], bool]


class SpellSelectionStep(CreationStep):
    """Collect the spells of the character.

    Three modes cover the possible spell models of a game system:

    - ``choice``: the player picks spells from the catalog **filtered**
      by ``spell_filter`` (restricted by the chosen class/race, the
      known skills or the spell level...); the raw picks are stored at
      ``target`` and mirrored at ``working_target`` so rule grants are
      layered on top;
    - ``auto``: no question is asked; spells are attributed
      automatically by the rules, the step is *not applicable*;
    - ``none``: the game system has no spells (step not applicable).

    Args:
        step_id: Unique identifier of the step; also the answer key in
            ``choice`` mode.
        mode: ``choice``, ``auto`` or ``none``.
        catalog: Key of the spell catalog in ``context.system``.
        target: State path storing the raw picks.
        working_target: State path of the effective spell list base.
        min_count: Minimum number of picks in ``choice`` mode.
        max_count: Maximum number of picks in ``choice`` mode.
        spell_filter: Predicate keeping the spells available for the
            current character; ``None`` keeps the whole catalog.
        prompt: Question asked to the player.
        label: Human-readable label.

    Raises:
        StepConfigurationError: If ``step_id`` is empty, a target is
            not a valid leaf path, the mode is unknown, or the counts
            are inconsistent.
    """

    def __init__(
        self,
        step_id: str = "spells",
        *,
        mode: str = "choice",
        catalog: str = "spells",
        target: str = "choices.spells",
        working_target: str = "values.spells",
        min_count: int = 0,
        max_count: int | None = None,
        spell_filter: SpellFilter | None = None,
        prompt: str | None = None,
        label: str = "",
    ) -> None:
        """Initialize the step.

        Args:
            step_id: Unique identifier of the step.
            mode: ``choice``, ``auto`` or ``none``.
            catalog: Key of the spell catalog in the system data.
            target: State path storing the raw picks.
            working_target: State path of the effective spell list base.
            min_count: Minimum number of picks.
            max_count: Maximum number of picks.
            spell_filter: Predicate keeping available spells.
            prompt: Question asked to the player.
            label: Human-readable label.

        Raises:
            StepConfigurationError: If the configuration is invalid.
        """
        super().__init__(step_id, label=label)
        if mode not in MODES:
            raise StepConfigurationError(
                f"Unknown spell selection mode {mode!r} (available: {', '.join(MODES)})"
            )
        parse_path(target)
        parse_path(working_target)
        if min_count < 0:
            raise StepConfigurationError(f"min_count must be >= 0, got {min_count}")
        if max_count is not None and max_count < min_count:
            raise StepConfigurationError(
                f"max_count ({max_count}) cannot be lower than min_count ({min_count})"
            )
        if spell_filter is not None and not callable(spell_filter):
            raise StepConfigurationError("spell_filter must be callable")
        self._mode = mode
        self._catalog = catalog
        self._target = target
        self._working_target = working_target
        self._min_count = min_count
        self._max_count = max_count
        self._spell_filter = spell_filter
        self._prompt = prompt or "Choose your spells"

    @property
    def mode(self) -> str:
        """Return the configured spell selection mode."""
        return self._mode

    def available(self, context: CharacterCreationContext) -> list[str]:
        """Return the spells available for the current character.

        Args:
            context: Current creation state (the filter receives the
                catalog entries together with the state, so it can
                filter on race, class, skills...).

        Returns:
            The names of the catalog entries passing the filter (the
            whole catalog when no filter is configured).

        Raises:
            StepConfigurationError: If the catalog is malformed or the
                filter raises.
        """
        entries = context.system.get(self._catalog)
        if entries is None:
            return []
        names = catalog_names(context.system, self._catalog)
        if self._spell_filter is None:
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
                keep = self._spell_filter(entry, context)
            except Exception as exc:
                raise StepConfigurationError(
                    f"The spell filter of step {self.step_id!r} failed for {name!r}: {exc}"
                ) from exc
            if keep:
                available.append(name)
        return available

    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Tell whether the step must run.

        Args:
            context: Current creation state.

        Returns:
            True only in ``choice`` mode with at least one available
            spell.
        """
        if self._mode != "choice":
            return False
        return bool(self.available(context))

    def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
        """Ask for the spell picks and mirror them to the working list.

        Args:
            context: Current creation state, updated in place.
            inputs: Answer source of the session.

        Raises:
            InputError: If the answer is missing (below ``min_count``)
                or breaks the count bounds.
            StepConfigurationError: If the catalog or the filter is
                broken.
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
        """Validate the stored spell picks.

        Args:
            context: Current creation state.

        Returns:
            Error messages; empty when every pick is available for the
            current character, within the count bounds, and mirrored
            correctly.
        """
        errors: list[str] = []
        options = self.available(context)
        raw = context.peek(self._target, [])
        if not isinstance(raw, (list, tuple)):
            errors.append(f"Spell picks at {self._target!r} must be a list")
            return errors
        picks = list(raw)
        unknown = [pick for pick in picks if pick not in options]
        if unknown:
            errors.append(f"Spell pick(s) not available for this character: {unknown!r}")
        if len(picks) < self._min_count:
            errors.append(f"At least {self._min_count} spell(s) must be picked, got {len(picks)}")
        if self._max_count is not None and len(picks) > self._max_count:
            errors.append(f"At most {self._max_count} spell(s) may be picked, got {len(picks)}")
        working = context.peek(self._working_target, [])
        working_list = list(working) if isinstance(working, (list, tuple)) else working
        if working_list != picks:
            errors.append(f"The working spell list {self._working_target!r} must mirror the picks")
        return errors
