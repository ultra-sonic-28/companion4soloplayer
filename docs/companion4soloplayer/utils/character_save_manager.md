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
