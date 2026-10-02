"""Compile the game plugins into extension modules (``*.pyd``).

Each plugin package under ``src/companion4soloplayer/plugins`` is compiled
with Nuitka (package mode) into a standalone extension library named after
the plugin (without the ``_plugin`` package suffix). The whole source
package -- one module per rule class under ``rules/``, the facade modules
(``plugin.py``, ``manifest.py``, ``data.py``) and the package ``__init__``
-- is fused into that single extension library:

    demo_plugin           ->  build/plugins/demo.pyd

Toolchain: Python -> Nuitka (``--mode=package --zig``) -> ``zig cc`` (clang).
Nuitka locates the Zig binary on the PATH (see SconsInterface.py: with
``--zig``, a ``zig`` executable found in the PATH is preferred over the
pip ``ziglang`` download), so the ``.bintools`` Zig directory is prepended
to the child process PATH.

The YAML data files of each plugin (``datas/plugin.yaml``,
``datas/classes.yaml``, ``datas/rules.yaml``, ...) plus the Markdown files
are copied into ``build/plugins/<name>/`` next to the compiled library,
preserving their relative layout, so the released application layout is::

    internal/plugins/
        demo.pyd
        demo/
            datas/
                plugin.yaml, classes.yaml, ...
            README.md
            ...

Usage:  python scripts/compile_plugins.py `[--output-dir build/plugins]` `[--force]`

Plugins are recompiled only when needed: if any plugin source file
(``*.py`` anywhere in the package or data file) is newer than the compiled
``.pyd``, the plugin is rebuilt; otherwise the existing library is kept.
Pass ``--force`` to rebuild every plugin regardless of timestamps.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_SRC = ROOT / "src" / "companion4soloplayer" / "plugins"
PLUGIN_PACKAGE_SUFFIX = "_plugin"

# Zig compiler shipped with the project (see .bintools/, git-ignored).
ZIG_DIR = ROOT / ".bintools" / "zig-x86_64-windows-0.16.0"
ZIG_EXE = ZIG_DIR / "zig.exe"

# Data files copied next to each compiled library (.json kept for
# plugins not yet migrated to YAML). The layout inside the plugin
# package is preserved (datas/*.yaml, README.md at the package root).
DATA_EXTENSIONS = {".yaml", ".yml", ".md"}

# Plugin manifests: YAML is canonical (in the datas/ data directory),
# the root and JSON locations are legacy fallbacks.
MANIFEST_NAMES = ("datas/plugin.yaml", "plugin.yaml")

# Code files mirrored into the Nuitka work directory.
CODE_EXTENSIONS = {".py"}


def _has_manifest(directory: Path) -> bool:
    """Tell whether a directory contains a plugin manifest.

    Args:
        directory: Plugin package directory.

    Returns:
        True if ``plugin.yaml`` (or legacy ``plugin.json``) is present.
    """
    return any((directory / name).is_file() for name in MANIFEST_NAMES)


def discover_plugin_packages() -> list[Path]:
    """Return plugin source package directories (with plugin manifest)."""
    return sorted(item for item in PLUGINS_SRC.iterdir() if item.is_dir() and _has_manifest(item))


def _nuitka_env(work_dir: Path | None = None) -> dict[str, str]:
    """Return the environment for Nuitka child processes.

    The Zig directory from ``.bintools`` is prepended to the PATH so
    Nuitka's ``--zig`` mode picks up the project-pinned compiler instead
    of downloading the ``ziglang`` pip package. ``PYTHONUTF8`` avoids
    cp1252 decoding issues in Nuitka/SCons child processes on Windows.
    """
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    # Keep the scratch build tree (ccache, clcache, ...) inside the work
    # directory instead of the per-user AppData cache: it is wiped with the
    # temporary work directory and avoids cross-run cache drift in CI.
    if work_dir is not None:
        env["NUITKA_CACHE_DIR"] = str(Path(work_dir) / "nuitka-cache")

    if ZIG_EXE.is_file():
        env["PATH"] = f"{ZIG_DIR}{os.pathsep}{env.get('PATH', '')}"
    else:
        print(
            f"WARNING: Zig compiler not found at {ZIG_EXE}; "
            "Nuitka will fall back to its own ziglang download.",
            file=sys.stderr,
        )

    if work_dir is not None:
        # Make the mirrored, suffix-less plugin package importable for the
        # Nuitka module resolution.
        env["PYTHONPATH"] = (
            f"{work_dir}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else str(work_dir)
        )

    return env


def _source_files(package_dir: Path) -> list[Path]:
    """Return every input file of a plugin package (code + data), recursively."""
    return [
        item
        for item in package_dir.rglob("*")
        if item.is_file()
        and (item.suffix.lower() in CODE_EXTENSIONS or item.suffix.lower() in DATA_EXTENSIONS)
    ]


def _needs_recompile(package_dir: Path, library_path: Path) -> tuple[bool, str]:
    """Tell whether a plugin must be recompiled.

    A recompilation is required when the compiled library is missing, or
    when any plugin source file is newer than the library build time.

    Args:
        package_dir: Source package directory of the plugin.
        library_path: Existing compiled library (may not exist yet).

    Returns:
        Tuple ``(needs_recompile, reason)`` where ``reason`` explains the
        decision (for the console output).
    """
    if not library_path.is_file():
        return True, "no compiled library yet"

    library_mtime = library_path.stat().st_mtime
    for source in _source_files(package_dir):
        if source.stat().st_mtime > library_mtime:
            return True, f"{source.name} is newer than {library_path.name}"

    return False, f"{library_path.name} is up to date"


def compile_plugin(package_dir: Path, output_dir: Path, work_dir: Path) -> Path:
    """Compile one plugin package into ``<output_dir>/<name>.pyd``.

    Args:
        package_dir: Source package directory of the plugin.
        output_dir: Directory receiving the compiled library and data files.
        work_dir: Scratch directory for the intermediate build artifacts.

    Returns:
        Path of the generated extension library.
    """
    plugin_name = package_dir.name.removesuffix(PLUGIN_PACKAGE_SUFFIX)

    # Mirror the plugin package under the work directory with the flat,
    # suffix-less module name expected in the released application, then
    # compile that package with Nuitka (package mode). Every Python file
    # of the package is mirrored, preserving the sub-directory layout
    # (``rules/``, ...), so the compiled library keeps all rule classes.
    # The generated extension keeps runtime imports (pydantic, core, ...)
    # external: plugins share the application environment.
    package_work = work_dir / plugin_name
    package_work.mkdir(parents=True)
    for source in package_dir.rglob("*"):
        if source.is_file() and source.suffix.lower() in CODE_EXTENSIONS:
            target = package_work / source.relative_to(package_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    nuitka_output_dir = work_dir / "out"
    nuitka_output_dir.mkdir(parents=True)

    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--mode=package",
        f"--output-dir={nuitka_output_dir}",
        "--zig",
        "--no-progressbar",
        plugin_name,
    ]

    print(f"  Nuitka command: {' '.join(command)}")
    result = subprocess.run(  # noqa: S603 - command list built internally
        command,
        cwd=work_dir,
        env=_nuitka_env(work_dir),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Nuitka failed for plugin {plugin_name} (exit {result.returncode})")

    candidates = sorted(nuitka_output_dir.glob(f"{plugin_name}.*.pyd"))
    if not candidates:
        raise RuntimeError(f"No compiled library found for plugin {plugin_name}")

    target = output_dir / f"{plugin_name}{candidates[0].suffix}"
    shutil.copy2(candidates[0], target)

    # Copy the data files into the sibling <plugin_name>/ directory,
    # preserving their relative layout (datas/*.yaml, README.md, ...).
    _copy_data_files(package_dir, output_dir / plugin_name)

    return target


def _copy_data_files(package_dir: Path, data_dir: Path) -> None:
    """Copy the data files of a package into ``data_dir``.

    The relative layout of the package is preserved, so ``datas/rules.yaml``
    lands in ``<data_dir>/datas/rules.yaml``.

    Args:
        package_dir: Source package directory of the plugin.
        data_dir: Destination directory (``<output>/<plugin_name>``).
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    for data_file in _source_files(package_dir):
        if data_file.suffix.lower() in DATA_EXTENSIONS:
            target = data_dir / data_file.relative_to(package_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(data_file, target)


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "build" / "plugins"),
        help="Directory receiving the compiled plugins (default: build/plugins)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompile every plugin, ignoring timestamps",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    packages = discover_plugin_packages()
    if not packages:
        print("No plugin package found.", file=sys.stderr)
        return 1

    compiled = 0
    skipped = 0

    for package in packages:
        plugin_name = package.name.removesuffix(PLUGIN_PACKAGE_SUFFIX)
        library_path = output_dir / f"{plugin_name}.pyd"

        if not args.force:
            needs_recompile, reason = _needs_recompile(package, library_path)
            if not needs_recompile:
                print(f"Skipping plugin: {package.name} ({reason})")
                skipped += 1

                # Data files are cheap to refresh: keep them in sync even
                # when the compiled library is up to date.
                _copy_data_files(package, output_dir / plugin_name)
                continue
            print(f"Compiling plugin: {package.name} ({reason})")
        else:
            print(f"Compiling plugin: {package.name} (forced rebuild)")

        with tempfile.TemporaryDirectory(prefix="c4sp-plugins-") as tmp:
            library = compile_plugin(package, output_dir, Path(tmp))
        print(f"  -> {library}")
        compiled += 1

    print(f"Done. {compiled} plugin(s) compiled, {skipped} skipped " f"(output: {output_dir})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

