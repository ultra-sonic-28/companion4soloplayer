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
version: "1"
character:
  name: Aragorn
  character_class: Ranger
  max_hp: 14
  current_hp: 14
  stats:
    body: 14
    agility: 12
  inventory: []
  equipment: []
```

## Usage

```python
from companion4soloplayer.core.character_tracker import CharacterTracker
from companion4soloplayer.utils.character_save import CharacterSaveManager

tracker = CharacterTracker()
character = tracker.create_character("Aragorn", "Ranger", {"body": 14})

manager = CharacterSaveManager("demo_plugin")
path = manager.save_character(character)
# path == <project root>/data/saves/demo_plugin/aragorn.yaml

reloaded = manager.load_character("aragorn")
assert reloaded.name == "Aragorn"
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

The save happens under ``data/saves/<plugin_name>/<slug>.yaml``. A save
failure is reported to the user but never blocks a successfully created
character: creation is committed first, persistence is best-effort.