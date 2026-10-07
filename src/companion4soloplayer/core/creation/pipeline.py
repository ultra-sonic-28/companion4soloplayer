"""Ordered pipeline executing the character creation steps.

The pipeline is the orchestration layer between the steps, the input
provider and the rules engine:

1. each step is processed in declaration order;
2. non-applicable steps are recorded as *skipped* (this is how a game
   system without races, spells or skills drops those steps);
3. the step collects its answers and is validated;
4. **after every executed step**, the condition/effect rules are
   evaluated automatically, so bonuses granted by a race/class choice
   are visible to the following steps.

The order of the steps is *data* (see
:mod:`companion4soloplayer.core.creation.workflow`): each game system
declares its own pipeline in its workflow YAML file.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from companion4soloplayer.core.creation.context import CharacterCreationContext
from companion4soloplayer.core.creation.inputs import InputError, InputProvider
from companion4soloplayer.core.creation.rules import (
    CreationRule,
    EvaluationReport,
    RulesEngine,
)
from companion4soloplayer.core.creation.steps.base import (
    CreationStep,
    StepConfigurationError,
    StepResult,
    StepStatus,
)


@dataclass(frozen=True)
class CreationReport:
    """Result of one full pipeline run.

    Attributes:
        results: Record of every processed step, in processing order.
        rules_fired: Identifiers of the rules that fired during the
            run, in first-firing order and without duplicates.
        total_steps: Number of steps declared by the pipeline (used to
            detect an interrupted run).
    """

    results: tuple[StepResult, ...] = ()
    rules_fired: tuple[str, ...] = ()
    total_steps: int = 0

    @property
    def ok(self) -> bool:
        """Tell whether no step failed."""
        return all(result.ok for result in self.results)

    @property
    def completed(self) -> bool:
        """Tell whether every declared step was processed and valid."""
        return self.ok and len(self.results) == self.total_steps

    @property
    def errors(self) -> tuple[str, ...]:
        """Return every error message, prefixed by its step identifier."""
        return tuple(
            f"{result.step_id}: {message}" for result in self.results for message in result.errors
        )

    @property
    def executed_steps(self) -> tuple[str, ...]:
        """Return the identifiers of the executed steps, in order."""
        return tuple(
            result.step_id for result in self.results if result.status is StepStatus.EXECUTED
        )


class CharacterCreationPipeline:
    """Run an ordered list of creation steps against a context.

    The pipeline is reusable and stateless: every :meth:`run` works on
    the given context and returns a fresh report.

    Args:
        steps: Steps to run, in order.
        rules: Creation rules (or a ready engine) evaluated after every
            executed step.
        system: Default game data attached to the contexts created by
            :meth:`create_context` (catalogs, attributes, strategies).
        stop_on_error: When True (default) the run stops on the first
            failed step.

    Raises:
        ValueError: If two steps share the same identifier.
    """

    def __init__(
        self,
        steps: Sequence[CreationStep],
        *,
        rules: Sequence[CreationRule] | RulesEngine = (),
        system: Mapping[str, Any] | None = None,
        stop_on_error: bool = True,
    ) -> None:
        """Initialize the pipeline.

        Args:
            steps: Steps to run, in order.
            rules: Creation rules or ready engine.
            system: Default game data of the created contexts.
            stop_on_error: Whether to stop on the first failed step.

        Raises:
            ValueError: If two steps share the same identifier.
        """
        self._steps = tuple(steps)
        seen: set[str] = set()
        for step in self._steps:
            if step.step_id in seen:
                raise ValueError(f"Duplicate step identifier {step.step_id!r}")
            seen.add(step.step_id)
        if isinstance(rules, RulesEngine):
            self._rules = rules
        else:
            self._rules = RulesEngine(rules)
        self._system = dict(system or {})
        self._stop_on_error = bool(stop_on_error)

    @property
    def steps(self) -> tuple[CreationStep, ...]:
        """Return the steps of the pipeline, in execution order."""
        return self._steps

    @property
    def rules(self) -> RulesEngine:
        """Return the rules engine evaluated after each step."""
        return self._rules

    @property
    def system(self) -> Mapping[str, Any]:
        """Return the default game data of the created contexts."""
        return dict(self._system)

    def create_context(
        self, *, system: Mapping[str, Any] | None = None
    ) -> CharacterCreationContext:
        """Create a fresh context for a new session.

        Args:
            system: Override the game data of the pipeline (defaults to
                the data given at construction).

        Returns:
            An empty creation context.
        """
        return CharacterCreationContext(system=self._system if system is None else system)

    def run(
        self,
        context: CharacterCreationContext,
        inputs: InputProvider,
        *,
        stop_on_error: bool | None = None,
    ) -> CreationReport:
        """Run every step in order.

        Args:
            context: Creation state, updated in place.
            inputs: Answer source of the session.
            stop_on_error: Override the pipeline default; when True the
                run stops on the first failed step.

        Returns:
            The report of the run (per-step results and fired rules).

        Raises:
            Exception: Unexpected exceptions raised by a step are not
                swallowed: they signal a programming error, not a user
                input problem.
        """
        stop = self._stop_on_error if stop_on_error is None else stop_on_error
        results: list[StepResult] = []
        fired: list[str] = []
        for step in self._steps:
            if not step.is_applicable(context):
                results.append(StepResult(step_id=step.step_id, status=StepStatus.SKIPPED))
                continue
            try:
                step.execute(context, inputs)
            except (InputError, StepConfigurationError) as exc:
                results.append(
                    StepResult(
                        step_id=step.step_id,
                        status=StepStatus.FAILED,
                        errors=(str(exc),),
                    )
                )
                fired.extend(self._evaluate(context).fired)
                if stop:
                    break
                continue
            errors = tuple(str(message) for message in step.validate(context))
            if errors:
                results.append(
                    StepResult(step_id=step.step_id, status=StepStatus.FAILED, errors=errors)
                )
            else:
                results.append(StepResult(step_id=step.step_id, status=StepStatus.EXECUTED))
                context.mark_executed(step.step_id)
            fired.extend(self._evaluate(context).fired)
            if results[-1].status is StepStatus.FAILED and stop:
                break
        return CreationReport(
            results=tuple(results),
            rules_fired=tuple(dict.fromkeys(fired)),
            total_steps=len(self._steps),
        )

    def _evaluate(self, context: CharacterCreationContext) -> EvaluationReport:
        """Evaluate the rules after a processed step.

        Args:
            context: Creation state to update.

        Returns:
            The evaluation report.
        """
        return self._rules.evaluate(context)

    def __repr__(self) -> str:
        """Return a compact debugging representation."""
        return (
            f"{type(self).__name__}(steps={[step.step_id for step in self._steps]}, "
            f"rules={len(self._rules.rules)})"
        )
