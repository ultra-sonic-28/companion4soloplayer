# Character Save

The `CharacterSaveManager` persists every piece of information of a newly
created player character into a structured file located under
`data/saves/<plugin_name>/`.

The save directory (and every missing parent folder) is created
automatically on first use. Each character is stored in its own file
named after the *slugified* character name (see
[Slugify](../utils/slugify.md)).

## Why YAML?

The serialization format is **YAML**. It was chosen because:

- it is already a hard dependency of the project (`PyYAML`);
- every plugin data file already ships as YAML (see `plugins/*/datas`);
- YAML maps naturally onto nested mappings and sequences, which keeps the
  saved character human-readable and easy to hand-edit;
- re-using the YAML ecosystem keeps the codebase consistent with the
  hardened [YAML Loader](../utils/yaml_loader.md) safe loader.

## Save file structure

Each save file is a self-describing YAML document:

```yaml
plugin_name: demo_plugin
saved_at: 2026-11-09T14:32:00+00:00
version: "2"
character:
  name: Aragorn
  character_class: Warrior
  race: Dwarf
  background: Born under the mountain
  max_hp: 16
  current_hp: 14
  stats:
    body: 16
    agility: 12
  saving_throws:
    magic: 12
    poison: 14
  skills:
    - Athletics
    - Perception
  spells: []
  inventory: []
  equipment: []
```

## Backward compatibility

Save files written with format version ``1`` (before the
``race``, ``background``, ``skills``, ``spells`` and ``saving_throws``
fields were added) still load correctly: the missing fields fall back on
their pydantic defaults (empty string, empty list, empty mapping).

## Overwrite confirmation

When a character with the same name already has a save file,
`CharacterSaveManager.save_character()` raises an
`OverwriteConfirmationNeeded` exception instead of silently replacing
the file. The exception carries:

- `file_path`: path of the existing save file;
- `old_character`: the character currently stored in the file;
- `new_character`: the character the user wants to save instead;
- `old_saved_at`: ISO-8601 timestamp of the existing save file.

The caller (typically the main window) is responsible for catching this
exception and presenting an overwrite confirmation dialog to the user.
If the user accepts, the caller retries the save with `overwrite=True`.

```python
from companion4soloplayer.utils.character_save import (
    CharacterSaveManager,
    OverwriteConfirmationError,
)

manager = CharacterSaveManager("demo_plugin")
try:
    manager.save_character(character)
except OverwriteConfirmationError as exc:
    # Show a dialog comparing exc.old_character vs exc.new_character
    # If the user accepts:
    manager.save_character(character, overwrite=True)
```

## Usage

```python
from companion4soloplayer.core.character_tracker import CharacterTracker
from companion4soloplayer.utils.character_save import CharacterSaveManager

tracker = CharacterTracker()
character = tracker.create_character("Aragorn", "Ranger", {"body": 14})
character.race = "Dwarf"
character.background = "Ranger of the North"
character.skills = ["Athletics", "Perception"]
character.saving_throws = {"magic": 12}

manager = CharacterSaveManager("demo_plugin")
path = manager.save_character(character)
# path == <project root>/data/saves/demo_plugin/aragorn.yaml

reloaded = manager.load_character("aragorn")
assert reloaded.name == "Aragorn"
assert reloaded.race == "Dwarf"
```

## Class diagram
```plantuml format="svg" source="docs/assets/diagrams/classes_companion4soloplayer_utils_character_save.plantuml"
```

## API reference

::: utils.character_save

## Integration with character creation

When the player validates the creation dialog (Manage > Player),
:class:`MainWindow` builds a :class:`Character` from the filled creation
context and persists it through
:class:`~companion4soloplayer.utils.character_save.CharacterSaveManager`:

```python
manager = CharacterSaveManager(plugin_name)
manager.save_character(character)
```

The save happens under ``data/saves/<plugin_name>/<slug>.yaml``. The
following creation data is persisted:

- **name** and **background** from ``choices.identity``
- **race** and **class** from ``choices``
- **skills** and **spells** from the selected lists in ``choices``
- **attributes** (base stats) from ``values.attributes``
- **saving throws** from ``values.save`` (by save name)

A save failure is reported to the user but never blocks a successfully
created character: creation is committed first, persistence is
best-effort.

## Overwrite confirmation dialog

The
[:class:`~companion4soloplayer.ui.dialogs.overwrite_confirmation_dialog.OverwriteConfirmationDialog`]
is a Qt dialog shown when the user attempts to save a character over an
existing file. It presents a side-by-side comparison of the old and new
values for **date**, **name**, **race** and **class**, letting the user
decide whether to replace the old save.

See the [Overwrite Confirmation Dialog](../ui/dialogs/overwrite_confirmation_dialog.md)
page for details.
