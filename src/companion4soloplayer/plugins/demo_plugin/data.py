"""Data files shipped with the demo plugin.

Game data lives as commented YAML documents in the ``datas/``
sub-directory of the plugin package. In development the data directory
is ``src/companion4soloplayer/plugins/demo_plugin/datas``. When
the plugin is compiled (Nuitka -> demo.pyd), ``__file__`` points
inside ``internal/plugins/demo/`` and the data files sit in the
sibling ``datas/`` directory of that same folder.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from companion4soloplayer.utils.yaml_loader import load_yaml_file

# Data files (plugin.yaml, classes.yaml, ...) location.
DATA_DIR = Path(__file__).parent / "datas"
if not (DATA_DIR / "plugin.yaml").is_file():
    # Compiled build fallback: __file__ points at the plugin folder
    # itself, data files are kept in the sibling <name>/datas directory.
    DATA_DIR = Path(__file__).parent / "demo" / "datas"


def load_data(filename: str) -> Any:
    """Load a YAML data file shipped with the plugin.

    Args:
        filename: File name relative to the plugin data directory.

    Returns:
        Parsed document (mapping, sequence or scalar).

    Raises:
        YamlLoadError: If the file is not valid YAML.
    """
    return load_yaml_file(DATA_DIR / filename)


def get_stat(entity: Mapping[str, Any], keys: str | list[str]) -> int:
    """Return the first matching stat value of an entity.

    Stats may live at the top level of the entity or under the nested
    ``stats`` / ``base_stats`` mappings, depending on the data file.

    Args:
        entity: Character or monster record.
        keys: Stat name, or ordered list of fallback stat names.

    Returns:
        The stat value, or 0 when none of the keys is present.
    """
    names = [keys] if isinstance(keys, str) else list(keys)
    for name in names:
        for source in (entity, entity.get("stats", {}), entity.get("base_stats", {})):
            if isinstance(source, Mapping) and isinstance(source.get(name), (int, float)):
                return int(source[name])
    return 0
