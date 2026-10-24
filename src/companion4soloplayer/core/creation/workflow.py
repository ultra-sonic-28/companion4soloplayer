"""Load a character creation workflow from declarative YAML.

The workflow document declares the **ordered** list of the steps of a
game system, as ``!pyclass`` references with constructor parameters::

    steps:
      - !pyclass
        path: companion4soloplayer.core.creation:IdentityStep
        params:
          step_id: identity
      - !pyclass
        path: local:AlignmentStep
        params:
          step_id: alignment

References are resolved with the security model of the hybrid
:class:`~companion4soloplayer.core.rule_engine.RuleEngine`: parsing
never imports anything, absolute references are restricted to a module
allow-list and ``local:`` references resolve inside the plugin module
that declares the workflow. Parameters that are themselves ``!pyclass``
references (typically a filter function) are resolved to the object
they point at.

The order of the entries **is** the order of the pipeline, which is
how each game system customizes its character creation flow.
"""

from __future__ import annotations

import logging
import types
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from companion4soloplayer.core.creation.pipeline import CharacterCreationPipeline
from companion4soloplayer.core.creation.rules import CreationRule, RulesEngine
from companion4soloplayer.core.creation.steps.base import CreationStep
from companion4soloplayer.core.rule_engine import (
    DEFAULT_ALLOWED_MODULES,
    RuleEngine,
    RuleEngineError,
)
from companion4soloplayer.utils.yaml_loader import PyClassRef, YamlTagError, load_yaml_file

logger = logging.getLogger(__name__)

#: Key of the workflow document holding the ordered step references.
STEPS_KEY = "steps"

#: Value of the ``block`` parameter expanding to every declared block.
ALL_BLOCKS = "*"


class WorkflowError(ValueError):
    """Raised when a workflow document cannot be turned into a pipeline."""


def build_workflow(
    workflow: Mapping[str, Any],
    *,
    rules: Sequence[CreationRule] | RulesEngine = (),
    base_module: str | types.ModuleType | None = None,
    allowed_modules: Sequence[str] = DEFAULT_ALLOWED_MODULES,
    system: Mapping[str, Any] | None = None,
    stop_on_error: bool = True,
) -> CharacterCreationPipeline:
    """Build a creation pipeline from a parsed workflow document.

    A step reference declaring ``block: "*"`` (an
    :class:`~companion4soloplayer.core.creation.steps.attributes.AttributeGenerationStep`)
    is expanded into one step per attribute block declared in
    ``system["attribute_blocks"]``, so a game system whose
    ``attributes.yaml`` holds several level-1 entries gets one step (and
    therefore one dialog block) per entry; see
    :func:`_expand_all_blocks`.

    Args:
        workflow: Parsed workflow document with a ``steps`` sequence of
            ``!pyclass`` references (strings are accepted too).
        rules: Creation rules (or ready engine) of the pipeline.
        base_module: Module resolving the ``local:`` references, either
            the module object or its dotted name (required as soon as
            the document contains one).
        allowed_modules: Module prefixes accepted for absolute
            references.
        system: Game data (catalogs, attributes, attribute blocks,
            strategies) attached to the contexts created by the
            pipeline.
        stop_on_error: Whether the pipeline stops on the first failed
            step.

    Returns:
        The assembled pipeline.

    Raises:
        WorkflowError: If the document has no ``steps`` sequence, if a
            step entry is not a class reference, if a reference cannot
            be resolved or instantiated, or if the instantiated object
            is not a
            :class:`~companion4soloplayer.core.creation.steps.base.CreationStep`.
    """
    if not isinstance(workflow, Mapping):
        raise WorkflowError(f"A workflow document must be a mapping, got {type(workflow).__name__}")
    raw_steps = workflow.get(STEPS_KEY)
    if raw_steps is None:
        raise WorkflowError(f"A workflow document requires a {STEPS_KEY!r} sequence")
    if isinstance(raw_steps, (str, bytes)) or not isinstance(raw_steps, Sequence):
        raise WorkflowError(f"The {STEPS_KEY!r} entry of a workflow must be a sequence")

    references: dict[str, PyClassRef] = {}
    for index, entry in enumerate(raw_steps):
        references[f"step_{index}"] = _as_reference(entry, index)
    references = _expand_all_blocks(references, system)
    engine = RuleEngine(
        {"implementations": references},
        base_module=base_module,
        allowed_modules=allowed_modules,
    )
    base_module_name = (
        base_module if isinstance(base_module, str) else getattr(base_module, "__name__", None)
    )
    logger.debug(
        "build_workflow: base_module=%s, steps=%d",
        base_module_name,
        len(references),
    )
    steps: list[CreationStep] = []
    for index, reference in enumerate(references.values()):
        params = _resolve_params(engine, reference, index)
        logger.debug(
            "build_workflow: step #%d reference=%s params=%s",
            index + 1,
            reference.path,
            {k: (type(v).__name__, getattr(v, "__name__", None)) for k, v in params.items()},
        )
        steps.append(_instantiate_step(engine, reference, params, index))
    return CharacterCreationPipeline(
        steps,
        rules=rules,
        system=system,
        stop_on_error=stop_on_error,
    )


def _expand_all_blocks(
    references: Mapping[str, PyClassRef],
    system: Mapping[str, Any] | None,
) -> dict[str, PyClassRef]:
    """Expand the steps rendering **every** declared attribute block.

    A step reference declaring ``block: "*"`` is a template: it is
    replaced by one step per block declared in
    ``system["attribute_blocks"]`` (the blocks read by the plugin from
    its ``attributes.yaml`` document). Each generated step takes the
    block identifier as its ``step_id`` and ``block``, and stores its
    values under ``values.<block identifier>``; the other parameters
    (mode, strategy, bounds...) are inherited from the template. This is
    how a game system declaring several level-1 entries in
    ``attributes.yaml`` gets one dialog block per entry, in declaration
    order.

    References not declaring ``block: "*"`` are returned untouched, so a
    workflow may also declare explicit ``block: <identifier>`` steps
    (one per wanted block, at wanted positions).

    Args:
        references: Step references of the workflow, keyed by synthetic
            name.
        system: Game data of the pipeline (provides the
            ``attribute_blocks`` mapping).

    Returns:
        The references to instantiate, in workflow order.

    Raises:
        WorkflowError: If a step declares ``block: "*"`` but the game
            system declares no ``attribute_blocks`` mapping, or
            declares a block without a valid identifier.
    """
    template = {
        name: reference
        for name, reference in references.items()
        if dict(reference.params).get("block") == ALL_BLOCKS
    }
    if not template:
        return dict(references)
    blocks = system.get("attribute_blocks") if system is not None else None
    if not isinstance(blocks, Mapping) or not blocks:
        raise WorkflowError(
            f"A step declaring block={ALL_BLOCKS!r} requires a non-empty "
            "'attribute_blocks' mapping in the system data"
        )
    expanded: dict[str, PyClassRef] = {}
    for name, reference in references.items():
        params = dict(reference.params)
        if name not in template:
            expanded[name] = reference
            continue
        for block_id in blocks:
            if not isinstance(block_id, str) or not block_id.strip():
                raise WorkflowError(
                    f"'attribute_blocks' declares a block without a valid identifier: {block_id!r}"
                )
            expanded[f"{name}[{block_id}]"] = PyClassRef(
                path=reference.path,
                params={
                    **params,
                    "step_id": block_id.strip(),
                    "block": block_id.strip(),
                    "target": f"values.{block_id.strip()}",
                },
            )
    return expanded


def build_workflow_from_yaml(
    path: str | Path,
    *,
    rules: Sequence[CreationRule] | RulesEngine = (),
    base_module: str | types.ModuleType | None = None,
    allowed_modules: Sequence[str] = DEFAULT_ALLOWED_MODULES,
    system: Mapping[str, Any] | None = None,
    stop_on_error: bool = True,
) -> CharacterCreationPipeline:
    """Load a workflow YAML file and build the pipeline.

    Args:
        path: Path of the workflow file (read as UTF-8).
        rules: Creation rules (or ready engine) of the pipeline.
        base_module: Module resolving the ``local:`` references.
        allowed_modules: Module prefixes accepted for absolute
            references.
        system: Game data attached to the created contexts.
        stop_on_error: Whether the pipeline stops on the first failed
            step.

    Returns:
        The assembled pipeline.

    Raises:
        YamlLoadError: If the file content is not valid YAML.
        WorkflowError: If the document is empty or malformed, or if a
            step cannot be built.
    """
    document = load_yaml_file(path)
    if document is None:
        raise WorkflowError(f"Workflow document {path} is empty")
    return build_workflow(
        document,
        rules=rules,
        base_module=base_module,
        allowed_modules=allowed_modules,
        system=system,
        stop_on_error=stop_on_error,
    )


def _as_reference(entry: Any, index: int) -> PyClassRef:
    """Normalize one workflow entry to a class reference.

    Args:
        entry: Raw entry from the ``steps`` sequence.
        index: Position of the entry (0-based), used in error messages.

    Returns:
        The parsed reference.

    Raises:
        WorkflowError: If the entry is neither a ``PyClassRef`` nor a
            reference string.
    """
    if isinstance(entry, PyClassRef):
        return entry
    if isinstance(entry, str):
        try:
            return PyClassRef.parse(entry)
        except YamlTagError as exc:
            raise WorkflowError(f"Step #{index + 1}: invalid reference {entry!r}: {exc}") from exc
    raise WorkflowError(
        f"Step #{index + 1} must be a !pyclass reference, got {type(entry).__name__}"
    )


def _resolve_params(engine: RuleEngine, reference: PyClassRef, index: int) -> dict[str, Any]:
    """Resolve the constructor parameters of one step reference.

    Parameters that are themselves ``!pyclass`` references (for example
    a spell filter function) are resolved to the object they point at;
    the other parameters are plain data.

    Args:
        engine: Rule engine providing the reference resolution (module
            allow-list and ``local:`` base module).
        reference: Reference declaring the parameters.
        index: Position of the step (0-based), used in error messages.

    Returns:
        The resolved constructor parameters.

    Raises:
        WorkflowError: If a nested reference cannot be resolved.
    """
    params: dict[str, Any] = {}
    for name, value in dict(reference.params).items():
        if isinstance(value, PyClassRef):
            logger.debug(
                "workflow._resolve_params: step #%d param %r is a PyClassRef %r",
                index + 1,
                name,
                value.path,
            )
            try:
                resolved = engine.resolve(value)
                logger.debug(
                    "workflow._resolve_params: step #%d param %r resolved %r -> %s (%s)",
                    index + 1,
                    name,
                    value.path,
                    type(resolved).__name__,
                    getattr(resolved, "__name__", None),
                )
                params[name] = resolved
            except RuleEngineError as exc:
                raise WorkflowError(
                    f"Step #{index + 1}: cannot resolve parameter {name!r} "
                    f"({value.path!r}): {exc}"
                ) from exc
        else:
            params[name] = value
    return params


def _instantiate_step(
    engine: RuleEngine,
    reference: PyClassRef,
    params: Mapping[str, Any],
    index: int,
) -> CreationStep:
    """Resolve and instantiate one workflow step.

    Args:
        engine: Rule engine providing the reference resolution.
        reference: Reference of the step class.
        params: Already resolved constructor parameters.
        index: Position of the step (0-based), used in error messages.

    Returns:
        The instantiated step.

    Raises:
        WorkflowError: If the reference cannot be resolved, is not
            callable, cannot be instantiated with the parameters, or
            does not produce a
            :class:`~companion4soloplayer.core.creation.steps.base.CreationStep`.
    """
    try:
        target = engine.resolve(reference)
    except RuleEngineError as exc:
        raise WorkflowError(f"Step #{index + 1}: cannot resolve {reference.path!r}: {exc}") from exc
    logger.debug(
        "workflow._instantiate_step: step #%d target=%s resolved to %s (%s), params=%s",
        index + 1,
        reference.path,
        type(target).__name__,
        getattr(target, "__name__", None),
        {k: (type(v).__name__, getattr(v, "__name__", None)) for k, v in dict(params).items()},
    )
    if not callable(target):
        raise WorkflowError(f"Step #{index + 1}: {reference.path!r} is not a step class")
    try:
        instance = target(**dict(params))
    except Exception as exc:
        raise WorkflowError(
            f"Step #{index + 1}: cannot instantiate {reference.path!r} "
            f"with params {dict(params)!r}: {exc}"
        ) from exc
    if not isinstance(instance, CreationStep):
        raise WorkflowError(
            f"Step #{index + 1}: {reference.path!r} produced "
            f"{type(instance).__name__}, expected a CreationStep"
        )
    return instance
