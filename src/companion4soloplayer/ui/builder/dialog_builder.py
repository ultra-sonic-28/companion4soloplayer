"""Assemble the sections of the player creation dialog from a pipeline.

The dialog is *data-driven*: its content comes from the creation
pipeline built by the plugin from its ``workflow.yaml`` file. The
builder walks the pipeline steps in order and turns the fields
described by each step (``CreationStep.describe_inputs``) into a group
box holding one field widget per data item.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QWidget

from companion4soloplayer.core.creation import (
    CharacterCreationContext,
    CharacterCreationPipeline,
    InputField,
)
from companion4soloplayer.ui.builder.fields import FieldWidget, create_field_widget


@dataclass(frozen=True)
class StepSection:
    """One workflow step rendered as a group of field widgets.

    Attributes:
        step_id: Identifier of the step (unique in the pipeline).
        label: Human-readable label displayed as the group title.
        box: Group box holding the section.
        rows: ``(field, widget)`` pairs, in display order.
    """

    step_id: str
    label: str
    box: QGroupBox
    rows: tuple[tuple[InputField, FieldWidget], ...]

    @property
    def widgets(self) -> tuple[FieldWidget, ...]:
        """Return the field widgets of the section, in display order."""
        return tuple(widget for _field, widget in self.rows)


class CharacterCreationDialogBuilder:
    """Build the dialog sections from a character creation pipeline.

    The builder keeps no state besides the pipeline: :meth:`build` may
    be called again (with another context) to rebuild the sections.

    Args:
        pipeline: Assembled creation pipeline; the plugin declares its
            step order in ``workflow.yaml``.
    """

    def __init__(self, pipeline: CharacterCreationPipeline) -> None:
        """Initialize the builder.

        Args:
            pipeline: Creation pipeline of the game system.
        """
        self._pipeline = pipeline

    @property
    def pipeline(self) -> CharacterCreationPipeline:
        """Return the pipeline driving the construction."""
        return self._pipeline

    def build(
        self,
        *,
        context: CharacterCreationContext | None = None,
        parent: QWidget | None = None,
    ) -> list[StepSection]:
        """Build one section per step describing data.

        Steps describing no data (``inherited`` skills, ``auto``
        spells, a game system without races, plugin-specific steps...)
        are skipped: they ask nothing to the player.

        Args:
            context: State used to resolve the descriptions (options,
                attribute names...). A fresh context of the pipeline
                is used when omitted.
            parent: Owning widget of the group boxes.

        Returns:
            The sections, in workflow (pipeline) order.
        """
        if context is None:
            context = self._pipeline.create_context()
        sections: list[StepSection] = []
        for step in self._pipeline.steps:
            fields = step.describe_inputs(context)
            if not fields:
                continue
            box = QGroupBox(step.label, parent)
            layout = QVBoxLayout(box)
            rows: list[tuple[InputField, FieldWidget]] = []
            for field in fields:
                widget = create_field_widget(field, box)
                layout.addWidget(widget)
                rows.append((field, widget))
            sections.append(
                StepSection(
                    step_id=step.step_id,
                    label=step.label,
                    box=box,
                    rows=tuple(rows),
                )
            )
        return sections
