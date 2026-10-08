"""Generic character creation engine.

This package implements the game-system agnostic part of the character
creation feature (see ``docs/character_creation.md`` for the global
design):

- :class:`~companion4soloplayer.core.creation.context.CharacterCreationContext`:
  the state container holding the raw **choices** of the player and the
  **computed values** of the steps;
- :class:`~companion4soloplayer.core.creation.inputs.InputProvider`:
  the answer source decoupling the steps from any UI;
- :mod:`~companion4soloplayer.core.creation.rules`: the Condition/Effect
  rule engine evaluated after each step (bonuses from race, class,
  attribute values, other skills...);
- :mod:`~companion4soloplayer.core.creation.strategies`: the attribute
  generation strategies (dice methods, fixed values, plugin-defined);
- :mod:`~companion4soloplayer.core.creation.steps`: the abstract
  :class:`~companion4soloplayer.core.creation.steps.CreationStep` and
  the generic steps (identity, selection, attributes, skills, spells);
- :class:`~companion4soloplayer.core.creation.pipeline.CharacterCreationPipeline`:
  the ordered step pipeline evaluating the rules after every step;
- :mod:`~companion4soloplayer.core.creation.workflow`: the YAML loader
  declaring **the step order of each game system**.

Plugin-specific data (races, classes, skills, spells), rules
("if Race=Dwarf then +2 Constitution"), strategies and workflow order
live in the plugin package, under ``<plugin>/datas/`` and
``<plugin>/creation/``.
"""

from companion4soloplayer.core.creation.context import (
    CHOICES_NAMESPACE,
    NAMESPACES,
    VALUES_NAMESPACE,
    CharacterCreationContext,
    InvalidPathError,
    parse_path,
)
from companion4soloplayer.core.creation.inputs import (
    InputError,
    InputField,
    InputKind,
    InputProvider,
    InvalidAnswerError,
    MappingInputProvider,
    MissingInputError,
)
from companion4soloplayer.core.creation.pipeline import (
    CharacterCreationPipeline,
    CreationReport,
)
from companion4soloplayer.core.creation.rules import (
    Action,
    Condition,
    CreationRule,
    Effect,
    EvaluationReport,
    Operator,
    RuleDefinitionError,
    RuleEvaluationError,
    RulesEngine,
    load_creation_rules,
)
from companion4soloplayer.core.creation.steps import (
    AttributeGenerationStep,
    CreationStep,
    IdentityStep,
    SelectionStep,
    SkillSelectionStep,
    SpellSelectionStep,
    StepConfigurationError,
    StepResult,
    StepStatus,
)
from companion4soloplayer.core.creation.strategies import (
    AttributeGenerationStrategy,
    ConstantStrategy,
    RollStrategy,
)
from companion4soloplayer.core.creation.workflow import (
    WorkflowError,
    build_workflow,
    build_workflow_from_yaml,
)

__all__ = [
    "CHOICES_NAMESPACE",
    "NAMESPACES",
    "VALUES_NAMESPACE",
    "Action",
    "AttributeGenerationStep",
    "AttributeGenerationStrategy",
    "CharacterCreationContext",
    "CharacterCreationPipeline",
    "Condition",
    "ConstantStrategy",
    "CreationReport",
    "CreationRule",
    "CreationStep",
    "Effect",
    "EvaluationReport",
    "IdentityStep",
    "InputError",
    "InputField",
    "InputKind",
    "InputProvider",
    "InvalidAnswerError",
    "InvalidPathError",
    "MappingInputProvider",
    "MissingInputError",
    "Operator",
    "RollStrategy",
    "RuleDefinitionError",
    "RuleEvaluationError",
    "RulesEngine",
    "SelectionStep",
    "SkillSelectionStep",
    "SpellSelectionStep",
    "StepConfigurationError",
    "StepResult",
    "StepStatus",
    "WorkflowError",
    "build_workflow",
    "build_workflow_from_yaml",
    "load_creation_rules",
    "parse_path",
]
