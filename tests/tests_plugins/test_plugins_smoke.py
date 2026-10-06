"""Tests for the dynamic plugin loader."""

import ast
import shutil
from pathlib import Path

import pytest

from companion4soloplayer.core.plugin_loader import PluginLoader
from companion4soloplayer.core.rule_engine import RULE_KINDS
from companion4soloplayer.core.rules import OracleRule
from companion4soloplayer.plugins.demo_plugin import PluginMetadata
from companion4soloplayer.utils.yaml_loader import load_yaml_file

PLUGINS_SRC = Path(__file__).resolve().parents[2] / "src" / "companion4soloplayer" / "plugins"
EXPECTED_PLUGINS = {"demo"}


@pytest.fixture
def loader() -> PluginLoader:
    """Return a plugin loader pointing at the source plugins."""
    return PluginLoader(plugins_dir=str(PLUGINS_SRC))


def test_discover_plugins_finds_all_source_plugins(loader: PluginLoader) -> None:
    names = set(loader.discover_plugins())
    assert names >= EXPECTED_PLUGINS


def test_load_plugin_from_source(loader: PluginLoader) -> None:
    plugin = loader.load_plugin("demo")
    assert plugin is not None
    assert plugin.name
    assert plugin.version
    assert plugin.description
    assert loader.get_plugin("demo") is plugin


def test_manifest_metadata_stores_multi_line_features() -> None:
    """The plugin.yaml 'features' metadata is stored in PluginMetadata."""
    manifest_path = PLUGINS_SRC / "demo_plugin" / "datas" / "plugin.yaml"
    metadata = PluginMetadata(**load_yaml_file(manifest_path))

    assert metadata.features.strip().startswith("- Features")
    assert "\n" in metadata.features
    # Nested section, whatever the indentation style (spaces or tabs).
    core_line = next(line for line in metadata.features.splitlines() if "Core Features" in line)
    assert core_line.startswith((" ", "\t"))
    assert "Dungeon Rolling" in metadata.features


def test_manifest_features_defaults_to_empty() -> None:
    """Plugins that do not declare 'features' get an empty description."""
    metadata = PluginMetadata(name="Demo", version="1.0.0", description="Demo plugin")
    assert metadata.features == ""


def test_load_unknown_plugin_returns_none(loader: PluginLoader) -> None:
    assert loader.load_plugin("does_not_exist") is None


def test_last_error_records_the_failure_reason(loader: PluginLoader) -> None:
    """A failed load stores a readable reason (releases have no console)."""
    assert loader.load_plugin("does_not_exist") is None
    reason = loader.last_errors["does_not_exist"]
    assert "not found" in reason


def test_last_error_is_dropped_after_a_successful_load(loader: PluginLoader) -> None:
    """A successful load clears any stale error recorded for the plugin."""
    assert loader.load_plugin("does_not_exist") is None
    assert "does_not_exist" in loader.last_errors
    plugin = loader.load_plugin("demo")
    assert plugin is not None
    assert "demo" not in loader.last_errors


def test_load_plugin_is_cached(loader: PluginLoader) -> None:
    first = loader.load_plugin("demo")
    second = loader.load_plugin("demo")
    assert first is second


def test_unload_plugin(loader: PluginLoader) -> None:
    loader.load_plugin("demo")
    assert loader.unload_plugin("demo") is True
    assert loader.get_plugin("demo") is None
    assert loader.unload_plugin("demo") is False


def test_plugin_exposes_gameplugin_api(loader: PluginLoader) -> None:
    plugin = loader.load_plugin("demo")
    assert plugin is not None
    assert isinstance(plugin.get_classes(), list)
    assert isinstance(plugin.get_monsters(), list)
    assert isinstance(plugin.get_items(), list)
    assert isinstance(plugin.get_rules(), dict)
    assert plugin.generate_dungeon({"size": 5})["config"] == {"size": 5}


def test_load_compiled_plugin_extension(tmp_path: Path) -> None:
    """A compiled .pyd placed next to a plugin data dir is loaded directly."""
    import importlib.machinery

    pytest.importorskip("setuptools")
    suffix = importlib.machinery.EXTENSION_SUFFIXES[0]
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()

    # Compile a tiny standalone extension module exposing Plugin.
    ext_src = tmp_path / "fake_plugin.c"
    ext_src.write_text(
        """
#include <Python.h>

static PyObject *Plugin_get_name(PyObject *self, PyObject *args) {
    return PyUnicode_FromString("fake");
}

static PyMethodDef plugin_methods[] = {
    {"get_name", Plugin_get_name, METH_NOARGS, NULL},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT, "fake", NULL, -1, plugin_methods
};

PyMODINIT_FUNC PyInit_fake(void) {
    return PyModule_Create(&moduledef);
}
""",
        encoding="utf-8",
    )
    from setuptools import Extension, setup
    from setuptools._distutils.errors import CompileError, DistutilsError  # type: ignore

    try:
        setup(
            name="fake",
            ext_modules=[Extension("fake", [str(ext_src)])],
            script_args=[
                "build_ext",
                f"--build-lib={tmp_path / 'lib'}",
                f"--build-temp={tmp_path / 'tmp'}",
            ],
        )
    except (CompileError, DistutilsError, OSError, SystemExit):
        pytest.skip("No C compiler available on this machine")
    built = next((tmp_path / "lib").rglob(f"fake_plugin{suffix}"))

    plugin_dir = plugins_dir / "fake"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.yaml").write_text("name: fake\n", encoding="utf-8")
    shutil.copy2(built, plugins_dir / f"fake{suffix}")

    loader = PluginLoader(plugins_dir=str(plugins_dir))
    assert loader.discover_plugins() == ["fake"]

    plugin = loader.load_plugin("fake")
    assert plugin is not None
    assert loader.get_plugin("fake") is plugin


# ----------------------------------------------------------------------
# Hybrid YAML/Python rule engine
# ----------------------------------------------------------------------

PLUGIN_RULE_KINDS = {
    "demo": {"character_creation", "combat", "loot", "oracle", "magic"},
}


@pytest.mark.parametrize("name", sorted(PLUGIN_RULE_KINDS))
def test_plugin_rule_engine_declares_standard_kinds(loader: PluginLoader, name: str) -> None:
    """Every plugin declares its rule elements using standard kinds."""
    plugin = loader.load_plugin(name)
    assert plugin is not None
    kinds = set(plugin.get_rule_engine().kinds)
    assert kinds == PLUGIN_RULE_KINDS[name]
    assert kinds <= set(RULE_KINDS)


@pytest.mark.parametrize("name", sorted(PLUGIN_RULE_KINDS))
def test_character_creation_component(loader: PluginLoader, name: str) -> None:
    """The character creation rule builds a character from the catalog."""
    plugin = loader.load_plugin(name)
    assert plugin is not None
    creator = plugin.create_component("character_creation")
    first_class = plugin.get_classes()[0]
    character = creator.create(first_class["name"], "Test Hero")
    assert character["name"] == "Test Hero"
    assert character["class"] == first_class["name"]
    assert character["stats"] == first_class["base_stats"]
    assert character["abilities"]
    # Components are cached by the rule engine.
    assert plugin.create_component("character_creation") is creator


def test_combat_component_resolves_attack(loader: PluginLoader) -> None:
    """The combat rule resolves an attack with the documented keys."""
    plugin = loader.load_plugin("demo")
    assert plugin is not None
    combat = plugin.create_component("combat")
    result = combat.resolve({"body": 8}, {"body": 4})
    assert {"attack", "defense", "net", "success", "damage"} <= set(result)
    assert result["success"] is (result["net"] >= 0)
    assert isinstance(result["damage"], int)
    assert 0 <= result["damage"] <= combat.max_damage


def test_magic_component_casts_spell(loader: PluginLoader) -> None:
    """The magic rule resolves a casting check for demo plugin."""
    plugin = loader.load_plugin("demo")
    assert plugin is not None
    magic = plugin.create_component("magic")
    result = magic.cast("Fireball", {"mind": 6})
    assert result["spell"] == "Fireball"
    assert isinstance(result["success"], bool)
    assert result["difficulty"] == 4


@pytest.mark.parametrize("name", sorted(PLUGIN_RULE_KINDS))
def test_loot_component_draws_items(loader: PluginLoader, name: str) -> None:
    """The loot rule draws entries from the item catalog."""
    plugin = loader.load_plugin(name)
    assert plugin is not None
    items = plugin.create_component("loot").roll(2)
    assert len(items) == 2
    assert all(item in plugin.get_items() for item in items)


@pytest.mark.parametrize("name", sorted(PLUGIN_RULE_KINDS))
def test_oracle_component_answers(loader: PluginLoader, name: str) -> None:
    """The oracle is the shared core rule element and answers a known outcome."""
    plugin = loader.load_plugin(name)
    assert plugin is not None
    oracle = plugin.create_component("oracle")
    assert type(oracle) is OracleRule
    assert oracle.ask() in set(oracle.OUTCOMES.values())


@pytest.mark.parametrize("name", sorted(PLUGIN_RULE_KINDS))
def test_get_rules_returns_declarative_document(loader: PluginLoader, name: str) -> None:
    """The declarative rules expose the combat section alongside tags."""
    plugin = loader.load_plugin(name)
    assert plugin is not None
    rules = plugin.get_rules()
    assert "combat" in rules
    assert "implementations" in rules
    assert rules["combat"]["steps"]


# ----------------------------------------------------------------------
# Source layout: one file per class, YAML data in datas/, rules in rules/
# ----------------------------------------------------------------------


def test_datas_directory_holds_the_yaml_files() -> None:
    """Every YAML data file lives in the plugin ``datas/`` sub-directory."""
    for name in sorted(PLUGIN_RULE_KINDS):
        package_dir = PLUGINS_SRC / f"{name}_plugin"
        assert list(package_dir.glob("*.yaml")) == []
        assert (package_dir / "datas" / "plugin.yaml").is_file()
        assert (package_dir / "datas" / "rules.yaml").is_file()


def test_package_init_declares_no_class() -> None:
    """The plugin ``__init__.py`` is a facade: classes live in their own modules."""
    for name in sorted(PLUGIN_RULE_KINDS):
        init_path = PLUGINS_SRC / f"{name}_plugin" / "__init__.py"
        tree = ast.parse(init_path.read_text(encoding="utf-8"))
        defined = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        assert defined == [], f"classes still defined in {init_path}: {defined}"


@pytest.mark.parametrize("name", sorted(PLUGIN_RULE_KINDS))
def test_local_rules_live_in_the_rules_subpackage(loader: PluginLoader, name: str) -> None:
    """'local:' components are classes of the plugin ``rules/`` sub-package."""
    plugin = loader.load_plugin(name)
    assert plugin is not None
    creator = plugin.create_component("character_creation")
    expected = f"companion4soloplayer.plugins.{name}_plugin.rules"
    assert creator.__class__.__module__.startswith(expected)


def test_oracle_is_shared_by_every_plugin(loader: PluginLoader) -> None:
    """The three plugins share the very same core OracleRule class."""
    oracle_classes = set()
    for name in sorted(PLUGIN_RULE_KINDS):
        plugin = loader.load_plugin(name)
        assert plugin is not None
        oracle_classes.add(type(plugin.create_component("oracle")))
    assert oracle_classes == {OracleRule}
