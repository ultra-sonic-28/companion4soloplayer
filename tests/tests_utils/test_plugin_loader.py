"""Unit tests for the plugin loader (``companion4soloplayer.utils.plugin_loader``)."""

import importlib.machinery
import shutil
from pathlib import Path
from typing import get_type_hints

import pytest

import companion4soloplayer
from companion4soloplayer.core.interface.game_plugin import GamePlugin
from companion4soloplayer.utils.plugin_loader import PluginLoader

PLUGINS_SRC = Path(__file__).resolve().parents[2] / "src" / "companion4soloplayer" / "plugins"
EXPECTED_PLUGINS = {"demo"}


@pytest.fixture
def loader() -> PluginLoader:
    """Return a plugin loader pointing at the source plugins."""
    return PluginLoader(plugins_dir=str(PLUGINS_SRC))


# ----------------------------------------------------------------------
# Layout after the core/utils refactoring
# ----------------------------------------------------------------------


def test_plugin_loader_is_hosted_by_utils_not_core() -> None:
    """The loader is a utility: ``core`` must only host the generic engine.

    Checked against the source tree, the single source of truth for the
    architecture (an installed copy may lag behind in a reused venv).
    """
    source_pkg = Path(__file__).resolve().parents[2] / "src" / "companion4soloplayer"
    assert (source_pkg / "utils" / "plugin_loader.py").is_file()
    assert not (source_pkg / "core" / "plugin_loader.py").exists()


def test_gameplugin_contract_is_hosted_by_core_interface() -> None:
    """The plugin contract is a generic interface: it belongs to ``core``."""
    from companion4soloplayer.core.interface import game_plugin

    assert game_plugin.GamePlugin is GamePlugin


def test_loader_public_api_is_typed_with_the_core_gameplugin() -> None:
    """The loader returns objects typed against the core GamePlugin contract."""
    assert get_type_hints(PluginLoader.load_plugin)["return"] == GamePlugin | None
    assert get_type_hints(PluginLoader.get_plugin)["return"] == GamePlugin | None


def test_default_plugins_dir_is_the_plugins_package() -> None:
    """The automatic resolution still points at the plugins package."""
    package_dir = Path(companion4soloplayer.__file__).resolve().parent
    assert PluginLoader().plugins_dir == package_dir / "plugins"


# ----------------------------------------------------------------------
# Discovery and loading
# ----------------------------------------------------------------------


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


def test_load_compiled_plugin_extension(tmp_path: Path) -> None:
    """A compiled .pyd placed next to a plugin data dir is loaded directly."""
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
