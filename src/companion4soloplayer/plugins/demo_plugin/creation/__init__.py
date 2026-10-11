"""Character creation support of the demo game system.

This sub-package groups everything game-system specific about the
character creation feature:

- :mod:`~companion4soloplayer.plugins.demo_plugin.creation.strategies`:
  the attribute generation methods registered by name;
- :mod:`~companion4soloplayer.plugins.demo_plugin.creation.filters`:
  the availability filters referenced by ``workflow.yaml``;
- :mod:`~companion4soloplayer.plugins.demo_plugin.creation.workflow`:
  the assembly of the pipeline (workflow order + rules + catalogs).

The generic engine lives in
:mod:`companion4soloplayer.core.creation`; the declarative data lives in
the ``datas/`` directory of the plugin.
"""

from companion4soloplayer.plugins.demo_plugin.creation.filters import (
    can_cast_spells,
    skill_available,
    spell_available,
)
from companion4soloplayer.plugins.demo_plugin.creation.strategies import (
    FourSixKeepBestStrategy,
)
from companion4soloplayer.plugins.demo_plugin.creation.workflow import (
    ATTRIBUTES_FILE,
    build_system,
    create_character_creation,
    load_attributes,
)

__all__ = [
    "ATTRIBUTES_FILE",
    "FourSixKeepBestStrategy",
    "build_system",
    "can_cast_spells",
    "create_character_creation",
    "load_attributes",
    "skill_available",
    "spell_available",
]
