"""Assemble the sections of the player creation dialog from a pipeline.

The dialog is *data-driven*: its content comes from the creation
pipeline built by the plugin from its ``workflow.yaml`` file. The
builder walks the pipeline steps in order and turns the fields
described by each step (``CreationStep.describe_inputs``) into a group
box holding one field widget per data item.

On top of that, :meth:`CharacterCreationDialogBuilder.arrange` lays the
group boxes out on a two-column grid (full row for the multi-field
sections, two single-field sections side by side), and a block made
only of dice/number fields spreads its own fields over two equal
columns.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtWidgets import QGridLayout, QGroupBox, QVBoxLayout, QWidget

from companion4soloplayer.core.creation import (
    CharacterCreationContext,
    CharacterCreationPipeline,
    InputField,
    InputKind,
)
from companion4soloplayer.ui.builder.fields import FieldWidget, create_field_widget

#: Field kinds rendered as a compact two-column block (attribute blocks).
COMPACT_KINDS: frozenset[InputKind] = frozenset({InputKind.DICE, InputKind.NUMBER})


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
            rows = self._fill_section(box, fields)
            sections.append(
                StepSection(
                    step_id=step.step_id,
                    label=step.label,
                    box=box,
                    rows=rows,
                )
            )
        return sections

    @staticmethod
    def _fill_section(
        box: QGroupBox,
        fields: Sequence[InputField],
    ) -> tuple[tuple[InputField, FieldWidget], ...]:
        """Create the widgets of one section inside its group box.

        A block made only of dice/number fields (an attribute block)
        is displayed on **two equal columns**: the first half of the
        fields goes to the left column, the rest to the right one. Any
        other section stacks its fields on a single column.

        Args:
            box: Group box hosting the section.
            fields: Fields described by the step, in display order.

        Returns:
            The ``(field, widget)`` pairs, in display order.
        """
        rows: list[tuple[InputField, FieldWidget]] = []
        if all(field.kind in COMPACT_KINDS for field in fields):
            layout = QGridLayout(box)
            half = (len(fields) + 1) // 2
            for position, field in enumerate(fields):
                widget = create_field_widget(field, box)
                if position < half:
                    layout.addWidget(widget, position, 0)
                else:
                    layout.addWidget(widget, position - half, 1)
                rows.append((field, widget))
        else:
            stack = QVBoxLayout(box)
            for field in fields:
                widget = create_field_widget(field, box)
                stack.addWidget(widget)
                rows.append((field, widget))
        return tuple(rows)

    def arrange(self, layout: QGridLayout, sections: Sequence[StepSection]) -> None:
        """Place the sections on a two-column grid.

        Two rules drive the rows:

        - a section describing **several** fields (identity,
          attributes) takes a whole row (two-column span);
        - consecutive **single-field** sections (race + class, skills +
          spells) share a row, side by side, in workflow order.

        Both columns stretch evenly and the sections keep their
        workflow order (top to bottom, left to right).

        Args:
            layout: Target grid layout.
            sections: Sections returned by :meth:`build`, in workflow
                order.
        """
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        row = 0
        index = 0
        while index < len(sections):
            if len(sections[index].rows) > 1:
                layout.addWidget(sections[index].box, row, 0, 1, 2)
                row += 1
                index += 1
                continue
            column = 0
            while index < len(sections) and len(sections[index].rows) == 1 and column < 2:
                layout.addWidget(sections[index].box, row, column)
                column += 1
                index += 1
            row += 1
