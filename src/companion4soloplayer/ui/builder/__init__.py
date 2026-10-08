"""Dynamic player creation dialog (application-level UI builder).

The construction of the dialog belongs to the application, not to the
plugins: any game system exposing a creation pipeline through the
``GamePlugin`` contract gets the same form, built from the step order
declared by its ``workflow.yaml`` file.
"""

from companion4soloplayer.ui.builder.creation_dialog import (
    DEFAULT_TITLE,
    CharacterCreationDialog,
)
from companion4soloplayer.ui.builder.dialog_builder import (
    CharacterCreationDialogBuilder,
    StepSection,
)
from companion4soloplayer.ui.builder.fields import (
    ChoiceField,
    DiceField,
    FieldWidget,
    NumberField,
    TextField,
    create_field_widget,
    dice_icon,
)

__all__ = [
    "DEFAULT_TITLE",
    "CharacterCreationDialog",
    "CharacterCreationDialogBuilder",
    "ChoiceField",
    "DiceField",
    "FieldWidget",
    "NumberField",
    "StepSection",
    "TextField",
    "create_field_widget",
    "dice_icon",
]
