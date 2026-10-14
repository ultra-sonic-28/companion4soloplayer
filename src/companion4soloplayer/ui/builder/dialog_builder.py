"""Assemble the sections of the player creation dialog from a pipeline.

The dialog is *data-driven*: its content comes from the creation
pipeline built by the plugin from its ``workflow.yaml`` file. The
builder walks the pipeline steps in order and turns the fields
described by each step (``CreationStep.describe_inputs``) into a group
box holding one field widget per data item.

On top of that, :meth:`CharacterCreationDialogBuilder.arrange` lays the
group boxes out on a two-column grid (full row for the multi-field
sections, two single-field sections side by side), and a block made
only of dice/number/read-only fields spreads its own fields over ``n``
equal columns (``n`` comes from the ``attributes_columns`` entry of the
plugin configuration, see
:class:`~companion4soloplayer.utils.plugin_config.PluginConfigRegistry`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtWidgets import QGridLayout, QGroupBox, QVBoxLayout, QWidget

from companion4soloplayer.core.creation import (
    CharacterCreationContext,
    CharacterCreationPipeline,
    CreationStep,
    InputField,
    InputKind,
)
from companion4soloplayer.ui.builder.fields import FieldWidget, create_field_widget
from companion4soloplayer.utils.plugin_config import DEFAULT_ATTRIBUTES_COLUMNS

#: Field kinds rendered as a compact multi-column block (attribute blocks).
COMPACT_KINDS: frozenset[InputKind] = frozenset(
    {InputKind.DICE, InputKind.NUMBER, InputKind.READONLY}
)


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

    def __init__(
        self,
        pipeline: CharacterCreationPipeline,
        *,
        attributes_columns: int = DEFAULT_ATTRIBUTES_COLUMNS,
    ) -> None:
        """Initialize the builder.

        Args:
            pipeline: Creation pipeline of the game system.
            attributes_columns: Number of columns an attribute block
                (dice/number/read-only fields) spreads over; comes from
                the ``attributes_columns`` entry of the plugin
                configuration (``datas/config.yaml``).
        """
        self._pipeline = pipeline
        self._attributes_columns = max(1, attributes_columns)

    @property
    def attributes_columns(self) -> int:
        """Return the number of columns an attribute block spreads over."""
        return self._attributes_columns

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
            section = self.build_section(step, context=context, parent=parent)
            if section is not None:
                sections.append(section)
        return sections

    def build_section(
        self,
        step: CreationStep,
        *,
        context: CharacterCreationContext | None = None,
        parent: QWidget | None = None,
    ) -> StepSection | None:
        """Build the single section of one workflow step.

        This is the incremental counterpart of :meth:`build`: a dialog
        refreshing itself as the answers come in can materialize a
        section whose step starts describing data (the spells block
        appearing once a spellcasting race/class is chosen, for
        instance).

        Args:
            step: Workflow step describing the data to render.
            context: State used to resolve the descriptions. A fresh
                context of the pipeline is used when omitted.
            parent: Owning widget of the group box.

        Returns:
            The section, or None when the step currently describes no
            data (the block must not be rendered).
        """
        if context is None:
            context = self._pipeline.create_context()
        fields = step.describe_inputs(context)
        if not fields:
            return None
        # The section title may come from the game data (an
        # attribute block of a plugin attributes.yaml), so the
        # step resolves it against the current context.
        label = step.display_label(context)
        box = QGroupBox(label, parent)
        rows = self._fill_section(box, fields)
        return StepSection(
            step_id=step.step_id,
            label=label,
            box=box,
            rows=rows,
        )

    def _fill_section(
        self,
        box: QGroupBox,
        fields: Sequence[InputField],
    ) -> tuple[tuple[InputField, FieldWidget], ...]:
        """Create the widgets of one section inside its group box.

        A block made only of dice/number/read-only fields (an
        attribute block) is displayed on **n equal columns** (``n`` is
        :attr:`attributes_columns`): the fields are dealt column by
        column, the first columns getting one extra field when the
        count does not divide evenly, so the columns differ by at most
        one row. Any other section stacks its fields on a single
        column.

        Args:
            box: Group box hosting the section.
            fields: Fields described by the step, in display order.

        Returns:
            The ``(field, widget)`` pairs, in display order.
        """
        rows: list[tuple[InputField, FieldWidget]] = []
        if all(field.kind in COMPACT_KINDS for field in fields) and fields:
            layout = QGridLayout(box)
            columns = min(self._attributes_columns, len(fields))
            base, extra = divmod(len(fields), columns)
            # Row where each column starts, and how many rows it holds.
            starts: list[int] = []
            start = 0
            for column in range(columns):
                starts.append(start)
                start += base + (1 if column < extra else 0)
            for position, field in enumerate(fields):
                widget = create_field_widget(field, box)
                column = 0
                for candidate in range(columns):
                    size = base + (1 if candidate < extra else 0)
                    if position < starts[candidate] + size:
                        column = candidate
                        break
                layout.addWidget(widget, position - starts[column], column)
                rows.append((field, widget))
            # Every column stretches evenly.
            for column in range(columns):
                layout.setColumnStretch(column, 1)
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

        - a section describing **several** fields (identity, an
          attribute block) takes a whole row (two-column span);
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
