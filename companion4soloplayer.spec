
"""
PyInstaller spec for Companion4SoloPlayer.
Built by scripts/create_project.py

    python -m PyInstaller --clean --noconfirm companion4soloplayer.spec

Produces dist/companion4soloplayer/companion4soloplayer.exe (a minimal
executable) plus an _internal/ sub-folder holding every runtime
library, Python module and data file (one-dir mode).
"""

import os
import tomllib
from datetime import date
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

datas = [
    ("assets", "assets"),
]
# Skip empty source directories (fresh projects have no assets yet):
datas = [
    (source, destination)
    for source, destination in datas
    if os.path.isdir(source) and any(os.scandir(source))
]

# ---------------------------------------------------------------------------
# Compiled plugins (.pyd + YAML data), produced by scripts/compile_plugins.py
# (invoked by the nox 'release' session before PyInstaller). They are
# collected as binaries so PyInstaller places them in _internal/plugins/,
# next to the runtime libraries.
# ---------------------------------------------------------------------------
PLUGINS_BUILD_DIR = Path(SPECPATH) / "build" / "plugins"
if not PLUGINS_BUILD_DIR.is_dir():
    raise SystemExit(
        "Compiled plugins not found: run 'nox -s compile-plugins' "
        "(or scripts/compile_plugins.py) before building the executable."
    )

plugin_libraries = sorted(PLUGINS_BUILD_DIR.glob("*.pyd"))
plugin_datas = sorted(
    path
    for path in PLUGINS_BUILD_DIR.rglob("*")
    if path.is_file() and path.suffix != ".pyd"
)

# Plugin data files (plugin.yaml, classes.yaml, ...) keep the layout they
# have under build/plugins/, so the released layout mirrors it:
# _internal/plugins/<plugin_name>/datas/*.yaml
# The destination is the file's parent directory RELATIVE to the plugins
# build dir (not its bare name): using path.parent.name alone would flatten
# <plugin_name>/datas/ into plugins/datas/.
def _plugin_data_destination(path: Path) -> str:
    relative_parent = path.parent.relative_to(PLUGINS_BUILD_DIR)
    if relative_parent == Path("."):
        return "plugins"
    return "plugins/" + relative_parent.as_posix()


datas += [
    (str(path), _plugin_data_destination(path))
    for path in plugin_datas
]
binaries = [(str(path), "plugins") for path in plugin_libraries]

# ---------------------------------------------------------------------------
# Third-party imports of the compiled plugins.
# The .pyd libraries are opaque binaries: PyInstaller cannot follow the
# Python-level imports they perform at runtime (the demo plugin's manifest
# module does `from pydantic import BaseModel`, and pydantic is lazily
# loaded through __getattr__, so even a reachable package root would not
# pull its submodules in). The affected packages are force-collected so
# plugins can be loaded from the Plugins tab of the frozen application.
# A dependency used by a plugin must be listed here AND declared in the
# `dependencies` array of pyproject.toml.
# ---------------------------------------------------------------------------
PLUGIN_DEPENDENCIES = ("pydantic",)

hiddenimports: list[str] = []
for _package in PLUGIN_DEPENDENCIES:
    _package_datas, _package_binaries, _package_submodules = collect_all(_package)
    datas += _package_datas
    binaries += _package_binaries
    hiddenimports += _package_submodules

# ---------------------------------------------------------------------------
# Windows version metadata, sourced from pyproject.toml so the numbers can
# never drift from the package definition. scripts/build_exe.ps1 bumps the
# `build` entry BEFORE invoking PyInstaller, hence the freshly stamped value
# is the one read here.
# ---------------------------------------------------------------------------
# PEP 621 reserves the keys of [project] (setuptools rejects custom
# ones), so the build counter lives in the project's own tool table.
_pyproject = tomllib.loads(
    # PyInstaller exposes SPECPATH (the spec file's directory) instead
    # of __file__ when executing the recipe.
    (Path(SPECPATH) / "pyproject.toml").read_text(
        encoding="utf-8",
    ),
)

VERSION = _pyproject["project"]["version"]
BUILD_NUMBER = int(_pyproject["tool"]["companion4soloplayer"]["build"])

_file_version_tuple = (
    tuple(int(part) for part in VERSION.split(".")) + (BUILD_NUMBER,)
)
while len(_file_version_tuple) < 4:
    _file_version_tuple += (0,)

COPYRIGHT = f"© {date.today().year} ultra-sonic-28"

vs_version = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=_file_version_tuple[:4],
        prodvers=_file_version_tuple[:4],
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        VarFileInfo(
            # 1036 = French (France), 1200 = Unicode.
            [VarStruct("Translation", [1036, 1200])],
        ),
        StringFileInfo(
            [
                StringTable(
                    # Key = language id (040C) + charset id (04B0)
                    # hex-encoded: French (1036) + Unicode (1200).
                    "040C04B0",
                    [
                        StringStruct(
                            "FileDescription",
                            "Companion4SoloPlayer (C4SP) "
                            "Open-source companion application for "
                            "dungeon crawler style board games.",
                        ),
                        StringStruct(
                            "FileVersion",
                            f"{VERSION} build {BUILD_NUMBER}",
                        ),
                        StringStruct("InternalName", "companion4soloplayer"),
                        StringStruct("LegalCopyright", COPYRIGHT),
                        StringStruct(
                            "OriginalFilename",
                            "companion4soloplayer.exe",
                        ),
                        StringStruct("ProductName", "companion4soloplayer"),
                        StringStruct(
                            "ProductVersion",
                            f"{VERSION} build {BUILD_NUMBER}",
                        ),
                    ],
                ),
            ],
        ),
    ],
)

a = Analysis(
    ["src/companion4soloplayer/main.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc_data",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="companion4soloplayer",
    debug=False,
    console=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=vs_version,
    icon="assets/icons/icon.ico",
)

# One-dir bundle: keep the executable minimal and gather every runtime
# binary (Python DLLs, Qt libraries, ...) and data file into the
# _internal/ sub-folder next to it.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="companion4soloplayer",
)
