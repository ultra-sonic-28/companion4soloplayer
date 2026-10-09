"""Dynamic player creation dialog.

The dialog chains the creation steps of the active game system in the
order declared by the plugin ``workflow.yaml``:

1. every step describing data (``CreationStep.describe_inputs``) is
   rendered as a section of empty widgets: a text zone, a label with a
   die button for a dice roll, or a choice list;
2. **Validate** collects the answers, runs the pipeline and closes the
   dialog on success (the report and the filled context are exposed to
   the caller); on failure the error messages are displayed and the
   dialog stays open;
3. **Cancel** discards everything.

The choice lists are re-evaluated whenever a selection or a dice roll
changes, so an option list depending on the state (the spells filtered
by the chosen class, for instance) always reflects the answers
collected so far.

The construction logic lives in
:class:`~companion4soloplayer.ui.builder.dialog_builder.CharacterCreationDialogBuilder`:
this class belongs to the application, not to the plugins, so every
game system exposing a creation pipeline gets the same dialog.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from companion4soloplayer.core.creation import (
    CharacterCreationContext,
    CharacterCreationPipeline,
    CreationReport,
    MappingInputProvider,
)
from companion4soloplayer.core.creation.steps import CreationStep
from companion4soloplayer.ui.builder.dialog_builder import (
    CharacterCreationDialogBuilder,
    StepSection,
)
from companion4soloplayer.ui.builder.fields import (
    ChoiceField,
    DiceField,
    TextAreaField,
    TextField,
)

#: Default window title of the dialog.
DEFAULT_TITLE = "Create Player"


class CharacterCreationDialog(QDialog):
    """Player creation form built dynamically from a pipeline.

    The sections, the number of fields and their widget kinds come
    from the steps declared by the plugin ``workflow.yaml``; every
    widget starts empty.

    The sections are laid out on a two-column grid: a multi-field
    section (identity, attributes) takes a whole row while two
    consecutive single-field sections (race + class, skills + spells)
    sit side by side; the dialog is at least 860 x 640 pixels.

    Args:
        pipeline: Creation pipeline of the loaded game system.
        parent: Owning widget.
        title: Window title.
    """

    def __init__(
        self,
        pipeline: CharacterCreationPipeline,
        parent: QWidget | None = None,
        *,
        title: str = DEFAULT_TITLE,
    ) -> None:
        """Initialize the dialog and build its sections.

        Args:
            pipeline: Creation pipeline of the loaded game system.
            parent: Owning widget.
            title: Window title.
        """
        super().__init__(parent)
        self._pipeline = pipeline
        self._builder = CharacterCreationDialogBuilder(pipeline)
        self._sections: list[StepSection] = []
        self._steps_by_id: dict[str, CreationStep] = {s.step_id: s for s in pipeline.steps}
        self._report: CreationReport | None = None
        self._context: CharacterCreationContext | None = None
        self._in_refresh = False
        self.setWindowTitle(title)
        self.setMinimumSize(860, 640)
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def sections(self) -> tuple[StepSection, ...]:
        """Return the rendered sections, in workflow order."""
        return tuple(self._sections)

    @property
    def report(self) -> CreationReport | None:
        """Return the pipeline report, set once Validate succeeded."""
        return self._report

    @property
    def context(self) -> CharacterCreationContext | None:
        """Return the filled creation context, set once Validate succeeded."""
        return self._context

    @property
    def answers(self) -> dict[str, Any]:
        """Return the answers collected from the widgets.

        Empty widgets are skipped (a blank text, an unselected
        single-choice option or an unrolled die stay unanswered), so
        the steps keep enforcing their own required/optional rules.
        """
        answers: dict[str, Any] = {}
        for section in self._sections:
            for field, widget in section.rows:
                value = widget.value()
                if value is None:
                    continue
                answers[field.key] = value
        return answers

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the scrollable form, the error area and the buttons."""
        root = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer_layout = QVBoxLayout(container)
        form_layout = QGridLayout()
        self._sections = self._builder.build(parent=container)
        self._builder.arrange(form_layout, self._sections)
        for section in self._sections:
            for _field, widget in section.rows:
                if isinstance(widget, DiceField):
                    widget.die_button.clicked.connect(
                        lambda checked=False, w=widget: self._on_roll(w)
                    )
                if not isinstance(widget, (TextField, TextAreaField)):
                    # Text edits never gate an option list: refreshing
                    # on every keystroke would be pure overhead.
                    widget.changed.connect(self._on_field_changed)
        outer_layout.addLayout(form_layout)
        outer_layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, stretch=1)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #c62828; font-weight: bold;")
        self.error_label.setVisible(False)
        root.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.validate_button = QPushButton("Validate")
        self.validate_button.setDefault(True)
        self.validate_button.clicked.connect(self._on_validate)
        buttons.addWidget(self.validate_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        root.addLayout(buttons)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _on_roll(self, widget: DiceField) -> None:
        """Roll the die of a dice field and display the result.

        Args:
            widget: Dice field whose button was clicked.
        """
        roller = widget.field.roll
        if roller is None:
            return
        try:
            value = int(roller())
        except Exception as exc:  # a broken strategy must not crash the dialog
            self.error_label.setText(f"{widget.field.label}: {exc}")
            self.error_label.setVisible(True)
            return
        widget.set_rolled_value(value)

    def _on_field_changed(self) -> None:
        """Re-evaluate the dependent option lists after a change."""
        if self._in_refresh:
            return
        self._refresh_options()

    def _refresh_options(self) -> None:
        """Recompute the choice options from the answers collected so far.

        The pipeline is replayed on a throwaway context with the
        current answers (``stop_on_error=False``): a step whose answers
        are still missing fails and leaves the state untouched, so an
        option list only reflects the data known so far. A broken step
        keeps the options already on screen instead of breaking the
        dialog.
        """
        self._in_refresh = True
        try:
            context = self._pipeline.create_context()
            self._pipeline.run(
                context,
                MappingInputProvider(self.answers),
                stop_on_error=False,
            )
            for section in self._sections:
                step = self._steps_by_id.get(section.step_id)
                if step is None:  # pragma: no cover - ids come from the pipeline
                    continue
                described = {field.key: field for field in step.describe_inputs(context)}
                for field, widget in section.rows:
                    if isinstance(widget, ChoiceField):
                        new_field = described.get(field.key)
                        if new_field is not None:
                            widget.set_options(new_field.options)
        except Exception:  # a broken plugin must not break the dialog
            return
        finally:
            self._in_refresh = False

    def _on_validate(self) -> None:
        """Run the pipeline with the collected answers."""
        self.error_label.clear()
        self.error_label.setVisible(False)
        context = self._pipeline.create_context()
        report = self._pipeline.run(context, MappingInputProvider(self.answers))
        if report.ok:
            self._report = report
            self._context = context
            self.accept()
            return
        messages = list(report.errors)
        if not messages:  # pragma: no cover - a failure always carries a message
            messages = ["The character could not be created."]
        self.error_label.setText("\n".join(messages))
        self.error_label.setVisible(True)
