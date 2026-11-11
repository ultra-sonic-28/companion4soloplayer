# Overwrite Confirmation Dialog

The `OverwriteConfirmationDialog` is a Qt modal dialog shown when the user
attempts to save a player character over an existing save file.

It presents a side-by-side comparison of the old values (currently stored
in the save file) versus the new values (the character the user wants to
save). The compared fields are:

- **Date** — save timestamp of the old file vs. today's date
- **Name** — character name
- **Race** — character race
- **Class** — character class

The user can either **Overwrite** (replace the old file with the new
values) or **Cancel** (keep the old file unchanged).

## When it appears

The dialog is shown by `MainWindow` when
`CharacterSaveManager.save_character()` raises
`OverwriteConfirmationNeeded`. This happens when a save file already
exists for the slugified character name and the save is attempted
without `overwrite=True`.

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

## API reference

::: utils.character_save.OverwriteConfirmationError
::: ui.dialogs.overwrite_confirmation_dialog.OverwriteConfirmationDialog