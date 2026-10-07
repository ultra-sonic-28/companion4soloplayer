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

from companion4soloplayer.plugins.demo_plugin.creation.filters import spell_available
from companion4soloplayer.plugins.demo_plugin.creation.strategies import (
    FourSixKeepBestStrategy,
)
from companion4soloplayer.plugins.demo_plugin.creation.workflow import (
    ATTRIBUTES,
    build_system,
    create_character_creation,
)

__all__ = [
    "ATTRIBUTES",
    "FourSixKeepBestStrategy",
    "build_system",
    "create_character_creation",
    "spell_available",
]
