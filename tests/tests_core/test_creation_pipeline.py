"""Tests for the creation pipeline and the YAML workflow loader."""

from pathlib import Path
from typing import Any

import pytest

from companion4soloplayer.core.creation import (
    Action,
    CharacterCreationContext,
    CharacterCreationPipeline,
    Condition,
    CreationRule,
    CreationStep,
    Effect,
    IdentityStep,
    MappingInputProvider,
    Operator,
    StepConfigurationError,
    StepStatus,
    WorkflowError,
    build_workflow,
    build_workflow_from_yaml,
)
from companion4soloplayer.core.creation.inputs import InputKind, InputProvider
from companion4soloplayer.core.creation.strategies import ConstantStrategy
from companion4soloplayer.utils.yaml_loader import PyClassRef


class RecordingStep(CreationStep):
    """Step appending its identifier to a shared log on execution."""

    def __init__(self, step_id: str, log: list[str]) -> None:
        super().__init__(step_id)
        self._log = log

    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Always applicable."""
        return True

    def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
        """Record the execution and write a marker value."""
        self._log.append(self.step_id)
        context.set(f"choices.{self.step_id}", "done")

    def validate(self, context: CharacterCreationContext) -> list[str]:
        """Always valid."""
        return []


class ProbeStep(CreationStep):
    """Record the effective bonus seen when the step executes."""

    def __init__(self, step_id: str, log: list[int]) -> None:
        super().__init__(step_id)
        self._log = log

    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Always applicable."""
        return True

    def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
        """Probe the rules state written by the previous step."""
        self._log.append(int(context.effective("values.bonus") or 0))
        context.set(f"choices.{self.step_id}", "done")

    def validate(self, context: CharacterCreationContext) -> list[str]:
        """Always valid."""
        return []


class FailingValidationStep(CreationStep):
    """Step whose state never validates."""

    def __init__(self, step_id: str = "broken", message: str = "invalid state") -> None:
        super().__init__(step_id)
        self._message = message

    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Always applicable."""
        return True

    def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
        """Write a marker value."""
        context.set(f"choices.{self.step_id}", "done")

    def validate(self, context: CharacterCreationContext) -> list[str]:
        """Always fails."""
        return [self._message]


class MissingAnswerStep(CreationStep):
    """Step requiring an answer the provider does not hold."""

    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Always applicable."""
        return True

    def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
        """Ask a required answer (missing in the tests)."""
        inputs.ask_text(self.step_id, "Something")

    def validate(self, context: CharacterCreationContext) -> list[str]:
        """Always valid."""
        return []


class ConfigErrorStep(CreationStep):
    """Step raising a configuration error at execution."""

    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Always applicable."""
        return True

    def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
        """Fail with a configuration error."""
        raise StepConfigurationError("broken game data")

    def validate(self, context: CharacterCreationContext) -> list[str]:
        """Always valid."""
        return []


class AlphaYesStep(CreationStep):
    """Step writing ``choices.alpha = 'yes'`` (rule trigger)."""

    def __init__(self, step_id: str, log: list[str]) -> None:
        super().__init__(step_id)
        self._log = log

    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Always applicable."""
        return True

    def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
        """Write the magic value and log the execution."""
        self._log.append(self.step_id)
        context.set("choices.alpha", "yes")

    def validate(self, context: CharacterCreationContext) -> list[str]:
        """Always valid."""
        return []


# ----------------------------------------------------------------------
# Pipeline mechanics
# ----------------------------------------------------------------------


def test_pipeline_runs_steps_in_declared_order() -> None:
    """Steps run in the order they were declared."""
    log: list[str] = []
    pipeline = CharacterCreationPipeline(
        [RecordingStep("first", log), RecordingStep("second", log)]
    )
    context = pipeline.create_context()
    report = pipeline.run(context, MappingInputProvider({}))
    assert log == ["first", "second"]
    assert report.ok
    assert report.completed
    assert report.executed_steps == ("first", "second")
    assert context.executed_steps == ["first", "second"]
    assert report.total_steps == 2
    assert report.errors == ()


def test_pipeline_skips_non_applicable_steps() -> None:
    """Non-applicable steps are recorded as skipped, not executed."""
    log: list[str] = []
    skip = RecordingStep("skip", log)
    skip.is_applicable = lambda context: False  # type: ignore[method-assign]
    pipeline = CharacterCreationPipeline([RecordingStep("first", log), skip])
    report = pipeline.run(pipeline.create_context(), MappingInputProvider({}))
    assert log == ["first"]
    assert [result.status for result in report.results] == [
        StepStatus.EXECUTED,
        StepStatus.SKIPPED,
    ]
    assert report.completed
    assert "skip" not in report.executed_steps


def test_pipeline_evaluates_rules_after_every_step() -> None:
    """The rule of a step is visible to the next step immediately."""
    probe_log: list[int] = []
    log: list[str] = []
    bonus_rule = CreationRule(
        id="alpha_bonus",
        when=(Condition("choices.alpha", Operator.EQ, "yes"),),
        effects=(Effect("values.bonus", Action.ADD, 1),),
    )

    # A step that does not trigger the rule leaves the bonus at zero.
    pipeline = CharacterCreationPipeline(
        [RecordingStep("alpha", log), ProbeStep("probe", probe_log)],
        rules=[bonus_rule],
    )
    report = pipeline.run(pipeline.create_context(), MappingInputProvider({}))
    assert probe_log == [0]
    assert report.rules_fired == ()

    # A triggering step makes the bonus visible to the next step.
    probe_log.clear()
    pipeline = CharacterCreationPipeline(
        [AlphaYesStep("alpha", log), ProbeStep("probe", probe_log)],
        rules=[bonus_rule],
    )
    report = pipeline.run(pipeline.create_context(), MappingInputProvider({}))
    assert probe_log == [1]
    assert report.rules_fired == ("alpha_bonus",)


def test_pipeline_deduplicates_fired_rule_ids() -> None:
    """A rule firing at several evaluations is reported once."""
    log: list[str] = []
    always_rule = CreationRule(id="always", effects=(Effect("values.bonus", Action.ADD, 1),))
    pipeline = CharacterCreationPipeline(
        [RecordingStep("one", log), RecordingStep("two", log)],
        rules=[always_rule],
    )
    report = pipeline.run(pipeline.create_context(), MappingInputProvider({}))
    assert report.rules_fired == ("always",)


def test_pipeline_stops_on_validation_failure_by_default() -> None:
    """The run stops at the first invalid step."""
    log: list[str] = []
    pipeline = CharacterCreationPipeline([FailingValidationStep(), RecordingStep("after", log)])
    report = pipeline.run(pipeline.create_context(), MappingInputProvider({}))
    assert not report.ok
    assert not report.completed
    assert log == []
    assert [result.status for result in report.results] == [StepStatus.FAILED]
    assert report.errors == ("broken: invalid state",)


def test_pipeline_can_continue_after_a_failure() -> None:
    """stop_on_error=False processes the remaining steps."""
    log: list[str] = []
    pipeline = CharacterCreationPipeline([FailingValidationStep(), RecordingStep("after", log)])
    report = pipeline.run(pipeline.create_context(), MappingInputProvider({}), stop_on_error=False)
    assert not report.ok
    assert not report.completed
    assert log == ["after"]


def test_pipeline_reports_missing_input_as_failure() -> None:
    """A missing answer fails the step instead of crashing the run."""
    pipeline = CharacterCreationPipeline([MissingAnswerStep("need")])
    report = pipeline.run(pipeline.create_context(), MappingInputProvider({}))
    assert not report.ok
    assert report.results[0].status is StepStatus.FAILED
    assert "need" in report.errors[0]


def test_pipeline_reports_configuration_error_as_failure() -> None:
    """A broken game data fails the step instead of crashing the run."""
    pipeline = CharacterCreationPipeline([ConfigErrorStep("config")])
    report = pipeline.run(pipeline.create_context(), MappingInputProvider({}))
    assert not report.ok
    assert "broken game data" in report.errors[0]


def test_pipeline_rejects_duplicate_step_ids() -> None:
    """Two steps cannot share the same identifier."""
    log: list[str] = []
    with pytest.raises(ValueError, match="Duplicate step identifier"):
        CharacterCreationPipeline([RecordingStep("same", log), RecordingStep("same", log)])


def test_pipeline_create_context_uses_the_pipeline_system() -> None:
    """Contexts created by the pipeline carry the configured data."""
    pipeline = CharacterCreationPipeline([], system={"attributes": ["strength"]})
    context = pipeline.create_context()
    assert context.system["attributes"] == ["strength"]
    assert pipeline.system == {"attributes": ["strength"]}
    override = pipeline.create_context(system={"attributes": ["charm"]})
    assert override.system["attributes"] == ["charm"]


# ----------------------------------------------------------------------
# Workflow loader (declarative YAML)
# ----------------------------------------------------------------------


class EchoStep(CreationStep):
    """Workflow test step accepting a parameter and a nested reference."""

    def __init__(self, step_id: str = "echo", *, value: str = "v", marker: Any = None) -> None:
        super().__init__(step_id)
        self.value = value
        self.marker = marker

    def is_applicable(self, context: CharacterCreationContext) -> bool:
        """Always applicable."""
        return True

    def execute(self, context: CharacterCreationContext, inputs: InputProvider) -> None:
        """Store the configured value as the step answer."""
        context.set(f"choices.{self.step_id}", self.value)

    def validate(self, context: CharacterCreationContext) -> list[str]:
        """Always valid."""
        return []


class NotAStep:
    """Deliberately not a CreationStep (workflow error case)."""


def passthrough(spell: Any, context: CharacterCreationContext) -> bool:
    """Nested ``!pyclass`` parameter used by the workflow tests.

    Args:
        spell: Unused catalog entry.
        context: Unused creation state.

    Returns:
        Always True.
    """
    return True


WORKFLOW_YAML = """
steps:
  - !pyclass
    path: local:EchoStep
    params:
      step_id: echo
      value: hello
      marker: !pyclass local:passthrough
  - !pyclass
    path: companion4soloplayer.core.creation:IdentityStep
    params:
      step_id: identity
"""


def test_build_workflow_from_document() -> None:
    """A workflow document builds an ordered pipeline of steps."""
    pipeline = build_workflow(
        {"steps": ["local:EchoStep", "companion4soloplayer.core.creation:IdentityStep"]},
        base_module=__name__,
    )
    assert [step.step_id for step in pipeline.steps] == ["echo", "identity"]
    assert isinstance(pipeline.steps[0], EchoStep)


def test_build_workflow_resolves_params_and_nested_references() -> None:
    """Constructor params pass through, nested references resolve."""
    from companion4soloplayer.utils.yaml_loader import load_yaml

    pipeline = build_workflow(load_yaml(WORKFLOW_YAML), base_module=__name__)
    echo = pipeline.steps[0]
    assert isinstance(echo, EchoStep)
    assert echo.value == "hello"
    assert echo.marker is passthrough
    assert isinstance(pipeline.steps[1], IdentityStep)


def test_build_workflow_from_yaml_file(tmp_path: Path) -> None:
    """The loader reads the document straight from a YAML file."""
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text(WORKFLOW_YAML, encoding="utf-8")
    pipeline = build_workflow_from_yaml(workflow, base_module=__name__)
    assert [step.step_id for step in pipeline.steps] == ["echo", "identity"]


def test_build_workflow_from_empty_yaml_file(tmp_path: Path) -> None:
    """An empty workflow file raises an explicit error."""
    workflow = tmp_path / "empty.yaml"
    workflow.write_text("# nothing\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="empty"):
        build_workflow_from_yaml(workflow, base_module=__name__)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ({}, "steps"),
        ({"steps": "not-a-list"}, "sequence"),
        ({"steps": [42]}, "!pyclass reference"),
        ({"steps": ["local:NotAStep"]}, "expected a CreationStep"),
        ({"steps": ["companion4soloplayer.core.creation:DoesNotExist"]}, "cannot resolve"),
        ({"steps": ["os:system"]}, "cannot resolve"),
        ({"steps": ["local:MissingAnswerStep"]}, "cannot instantiate"),
    ],
)
def test_build_workflow_rejects_invalid_documents(document: dict[str, Any], message: str) -> None:
    """Invalid workflow documents raise WorkflowError with a clear hint."""
    with pytest.raises(WorkflowError, match=message):
        build_workflow(document, base_module=__name__)


# ----------------------------------------------------------------------
# Attribute block expansion (block: "*")
# ----------------------------------------------------------------------

#: Game system declaring two attribute blocks (attributes.yaml layout).
BLOCKS_SYSTEM: dict[str, Any] = {
    "attribute_blocks": {
        "attributes": {
            "id": "attributes",
            "title": "Attributes",
            "list": [{"id": "strength", "name": "Strength"}],
        },
        "save": {
            "id": "save",
            "title": "Saving Throws",
            "list": [{"id": "magic", "name": "Magic"}],
        },
    },
    "strategies": {"fixed": ConstantStrategy(12)},
}

BLOCKS_WORKFLOW: dict[str, Any] = {
    "steps": [
        PyClassRef(
            path="companion4soloplayer.core.creation:IdentityStep",
            params={"step_id": "identity"},
        ),
        PyClassRef(
            path="companion4soloplayer.core.creation:AttributeGenerationStep",
            params={"block": "*", "strategy": "fixed", "min_value": 3, "max_value": 18},
        ),
    ]
}


def test_build_workflow_expands_one_step_per_attribute_block() -> None:
    """``block: "*"`` becomes one step per declared block, in order."""
    pipeline = build_workflow(BLOCKS_WORKFLOW, base_module=__name__, system=BLOCKS_SYSTEM)
    assert [step.step_id for step in pipeline.steps] == ["identity", "attributes", "save"]
    attributes, save = pipeline.steps[1], pipeline.steps[2]
    context = pipeline.create_context()
    # Each block renders its own entries, with its own block title.
    assert [field.key for field in attributes.describe_inputs(context)] == ["attributes.strength"]
    assert attributes.display_label(context) == "Attributes"
    assert [field.key for field in save.describe_inputs(context)] == ["save.magic"]
    assert save.display_label(context) == "Saving Throws"
    # Each block stores its values under its own state path.
    pipeline.run(
        context,
        MappingInputProvider({"identity.name": "Solo", "identity.background": "None"}),
    )
    assert context.get("values.attributes.strength") == 12
    assert context.get("values.save.magic") == 12


def test_build_workflow_expansion_keeps_the_other_steps_untouched() -> None:
    """Steps not declaring ``block: "*"`` pass through unchanged."""
    pipeline = build_workflow(BLOCKS_WORKFLOW, base_module=__name__, system=BLOCKS_SYSTEM)
    assert isinstance(pipeline.steps[0], IdentityStep)


def test_build_workflow_expansion_without_blocks_raises() -> None:
    """``block: "*"`` without declared blocks is a workflow error."""
    with pytest.raises(WorkflowError, match="attribute_blocks"):
        build_workflow(BLOCKS_WORKFLOW, base_module=__name__)


def test_build_workflow_gives_each_block_its_own_strategy() -> None:
    """The per-block mode/strategy are resolved for every expanded block.

    The attributes keep rolling dice while the saving throws are
    assigned by their own strategy, from one single workflow entry.
    """
    workflow: dict[str, Any] = {
        "steps": [
            PyClassRef(
                path="companion4soloplayer.core.creation:AttributeGenerationStep",
                params={
                    "block": "*",
                    "mode": {"attributes": "random", "save": "auto"},
                    "strategy": {"attributes": "fixed", "save": "fixed"},
                    "min_value": 3,
                    "max_value": 18,
                },
            ),
        ]
    }
    pipeline = build_workflow(workflow, base_module=__name__, system=BLOCKS_SYSTEM)
    attributes, save = pipeline.steps
    context = pipeline.create_context()
    assert [field.kind for field in attributes.describe_inputs(context)] == [InputKind.DICE]
    assert [field.kind for field in save.describe_inputs(context)] == [InputKind.READONLY]
    assert pipeline.run(context, MappingInputProvider({})).ok
    assert context.get("values.attributes.strength") == 12
    assert context.get("values.save.magic") == 12
