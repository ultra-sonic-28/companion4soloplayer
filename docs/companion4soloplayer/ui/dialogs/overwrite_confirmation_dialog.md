# Overwrite Confirmation Dialog

The `OverwriteConfirmationDialog` is a Qt modal dialog shown when the user
attempts to save a player character over an existing save file.

It presents a side-by-side comparison of the old values (currently stored
in the save file) versus the new values (the character the user wants to
save). The compared fields are:

- **Date** — save timestamp of the old file vs. today's date
- **Plugin version** — plugin version stored in the old file vs. plugin
  version of the running application
- **Name** — character name
- **Race** — character race
- **Class** — character class

The left column shows the values of the existing save file and the right
column shows the values the user wants to save instead. Comparing the
plugin version lets the user spot saves created with an older (or newer)
plugin release before replacing them.

The user can either **Overwrite** (replace the old file with the new
values) or **Cancel** (keep the old file unchanged).

## When it appears

The dialog is shown by `MainWindow` when
`CharacterSaveManager.save_character()` raises
`OverwriteConfirmationError`. This happens when a save file already
exists for the slugified character name and the save is attempted
without `overwrite=True`.

The exception now carries both plugin versions:

- `old_version`: version read from the existing save file;
- `new_version`: version of the currently running plugin, read from the
  plugin configuration registry.

## Usage

```python
from companion4soloplayer.ui.dialogs.overwrite_confirmation_dialog import (
    OverwriteConfirmationDialog,
)
from companion4soloplayer.core.character_tracker import Character

dialog = OverwriteConfirmationDialog(
    old_character=old_character,
    new_character=new_character,
    old_saved_at="2026-01-15T10:30:00+00:00",
    old_version="1.0.0",
    new_version="2.0.0",
    file_path="/data/saves/demo_plugin/aragorn.yaml",
    parent=self,
)
if dialog.exec() == OverwriteConfirmationDialog.DialogCode.Accepted:
    # User clicked Overwrite: proceed with overwrite=True
    manager.save_character(character, overwrite=True)
else:
    # User clicked Cancel: keep the existing file
    pass
```

## Class diagram
```plantuml format="svg" source="docs/assets/diagrams/classes_companion4soloplayer_ui_dialogs_overwrite_confirmation_dialog.plantuml"
```

## API reference

::: utils.character_save.OverwriteConfirmationError
::: ui.dialogs.overwrite_confirmation_dialog.OverwriteConfirmationDialog