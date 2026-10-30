
import hashlib
import json
import os
import re
import shutil
import tempfile
import tomllib
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import nox  # type: ignore
from nox.command import CommandFailed  # type: ignore

# Tentative d'import de packaging pour une comparaison de versions robuste (PEP 440).
# Fallback vers une comparaison par tuple numérique si la librairie n'est pas disponible.
try:
    from packaging.version import parse as parse_version
except ImportError:
    parse_version = None  # type: ignore[assignment]

def ver_cmp(v: str) -> Any:
    """Retourne un objet comparable pour la version donnée."""
    if parse_version is not None:
        return parse_version(v)

    # Fallback : extrait les séquences de chiffres et crée un tuple.
    # Le `or (0,)` garantit qu'on retourne au moins (0,) si aucun chiffre n'est trouvé,
    # évitant ainsi les erreurs de comparaison avec un tuple vide.
    return tuple(int(p) for p in re.findall(r'\d+', v)) or (0,)

# Empty list = no default session
nox.options.sessions = []

# ---------------------------------------------------------------------------
# Configuration for the backup session
# ---------------------------------------------------------------------------
BACKUP_INCLUDES = [
    ".vscode/",
    "assets/",
    "data/",
    "docs/",
    "scripts/",
    "src/",
    "tests/",
    ".gitignore",
    "companion4soloplayer.code-workspace",
    "companion4soloplayer.log",
    "companion4soloplayer.spec",
    "CONTEXT.md",
    "LICENSE",
    "mkdocs.yml",
    "noxfile.py",
    "pyproject.toml",
    "README.md",
    "stats_histo.txt",
    "stats.txt",
]

BACKUP_EXCLUDES = [
    ".mypy_cache/",
    "__pycache__/",
]

# ---------------------------------------------------------------------------
# Get pyproject.toml declared dependencies
# ---------------------------------------------------------------------------
def _get_dev_deps() -> list[str]:
    """Read development dependencies from pyproject.toml."""
    pyproject = Path("pyproject.toml").read_bytes()
    data = tomllib.loads(pyproject.decode())
    return cast(list[str], data["project"]["optional-dependencies"]["dev"])

def _get_test_deps() -> list[str]:
    """Read test dependencies from pyproject.toml."""
    pyproject = Path("pyproject.toml").read_bytes()
    data = tomllib.loads(pyproject.decode())
    return cast(list[str], data["project"]["optional-dependencies"]["test"])

def _get_lint_deps() -> list[str]:
    """Read lint dependencies from pyproject.toml."""
    pyproject = Path("pyproject.toml").read_bytes()
    data = tomllib.loads(pyproject.decode())
    return cast(list[str], data["project"]["optional-dependencies"]["lint"])

def _get_build_deps() -> list[str]:
    """Read build dependencies from pyproject.toml."""
    pyproject = Path("pyproject.toml").read_bytes()
    data = tomllib.loads(pyproject.decode())
    return cast(list[str], data["project"]["optional-dependencies"]["build"])

def _get_docs_deps() -> list[str]:
    """Read documentation dependencies from pyproject.toml."""
    pyproject = Path("pyproject.toml").read_bytes()
    data = tomllib.loads(pyproject.decode())
    return cast(list[str], data["project"]["optional-dependencies"]["docs"])

def _get_diagrams_deps() -> list[str]:
    """Read diagrams dependencies from pyproject.toml."""
    pyproject = Path("pyproject.toml").read_bytes()
    data = tomllib.loads(pyproject.decode())
    return cast(list[str], data["project"]["optional-dependencies"]["diagrams"])

def check_network_access(session: nox.Session, url: str = "https://pypi.org/", timeout: int = 5) -> bool:
    """
    Checks if the environment has network access and can reach a specific URL.

    Args:
        session: The nox session object.
        url: The URL to test (default is PyPI).
        timeout: Timeout in seconds.

    Returns:
        bool: True if accessible, False otherwise.
    """
    parsed_url = urlparse(url)
    if parsed_url.scheme not in ("http", "https"):
        session.log(f"Invalid URL scheme '{parsed_url.scheme}'. Only 'http' and 'https' are permitted.")
        return False

    session.log(f"Checking network connectivity to {url} ...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Nox-Connectivity-Check'})  # noqa: S310
        # Ruff S310 is explicitly suppressed here because we validated the scheme above.
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310
            session.log(f"Successfully connected to {url} (HTTP {response.status}).")
            session.log("Network access confirmed.")
            return True

    except urllib.error.URLError as e:
        reason = str(e.reason)
        session.log(f"Failed to connect to {url}.")

        if "getaddrinfo failed" in reason or "Name or service not known" in reason or "nodename nor servname provided" in reason:
            session.log(f"DNS resolution failed: {reason}")
            session.log("You might be offline or your DNS is blocked by a firewall.")
        else:
            session.log(f"URLError occurred: {reason}")
            session.log("Please check your internet connection, proxy, or firewall settings.")
        return False

    except TimeoutError:
        session.log(f"Connection to {url} timed out after {timeout} seconds.")
        session.log("You might be behind a strict firewall or experiencing network issues.")
        return False

    except Exception as e:
        session.log(f"An unexpected error occurred during connectivity check: {e}")
        return False

def _generate_docs(session: nox.Session, is_live: bool) -> None:
    """Internal helper to generate documentation (static or live)."""
    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    session.install(*_get_docs_deps())
    session.install(".")

    # Force UTF-8 for every child Python process: the default cp1252
    # console encoding on Windows crashes scripts printing non-ASCII
    # characters (e.g. make_icon.py prints an arrow "→").
    utf8_env = {"PYTHONUTF8": "1"}

    session.run("python", "scripts/resize_logo.py", env=utf8_env)

    root = Path(__file__).parent.resolve()
    pyproject_path = root / "pyproject.toml"

    # Read pyproject.toml
    pyproject_content = pyproject_path.read_text(encoding="utf-8")

    # Extract version from the (already updated) pyproject.toml
    version_match = re.search(r'(?m)^[ ]*version[ ]*=[ ]*"([^"]+)"[ ]*\r?$', pyproject_content)

    # FIX MYPI: Use else block so mypy knows version_match is not None in the success path
    if version_match is None:
        session.error("Cannot locate the 'version' entry in pyproject.toml.")
    else:
        version = version_match.group(1)

    # Get the build counter in pyproject.toml
    build_match = re.search(r'(?m)^(?P<indent>[ ]*)build[ ]*=[ ]*(?P<number>\d+)[ ]*\r?$', pyproject_content)

    number = int(build_match.group("number")) if build_match else 1

    content =  f"""/* Custom JavaScript for Companion4SoloPlayer */
document.addEventListener('DOMContentLoaded', function() {{
    const footer = document.querySelector('footer');
    footer.innerHTML = `
    <div class="md-footer-meta md-typeset">
        <div class="md-footer-meta__inner md-grid">
            <div class="md-copyright">
                Made with
                <a href="https://squidfunk.github.io/mkdocs-material/" target="_blank" rel="noopener">
                    Material for MkDocs
                </a>
                and
                <a href="https://mkdocstrings.github.io/" target="_blank" rel="noopener">
                mkdocstrings
                </a>
            </div>
            <span class="md-copyright c-white">Companion4SoloPlayer <i>v{version} build {number}</i></span>
        </div>
    </div>
`;
}});
"""

    with open("docs/assets/custom.js", "w", encoding="utf-8") as f:
        f.write(content)

    session.log("Custom JavaScript for the documentation footer has been regenerated in docs/assets/custom.js")

    if is_live:
        session.log("Starting MkDocs live server...")
        session.run(
            "mkdocs",
            "serve",
            "--strict",
            env=utf8_env
        )
    else:
        session.log("Building static documentation...")
        session.run(
            "mkdocs",
            "build",
            "--clean",
            "--strict",
            env=utf8_env
        )
        session.log("Static documentation built successfully in the 'site/' directory.")


# ---------------------------------------------------------------------------
# lint session
# Run QoL checks: black, ruff, mypy.
# ---------------------------------------------------------------------------
@nox.session(name="lint")
def lint(session: nox.Session) -> None:
    """ Run QoL checks: black, ruff, mypy. """
    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    # Install the same packages and versions as in pyproject.toml
    session.install(*_get_lint_deps())
    session.install(*_get_test_deps())
    session.install(".")
    #session.run("black", "--check", ".")

    ruff_has_errors = False

    # Attempt the check, and if it fails, apply the fixes.
    try:
        session.run("ruff", "check", ".")
    except CommandFailed:
        ruff_has_errors = True
        session.log("Ruff found errors, attempting automatic correction...")
        session.run("ruff", "check", "--fix", ".")

    # Verify if there are any remaining errors that couldn't be auto-fixed
    if ruff_has_errors:
        ruff_has_errors = False

        try:
            session.run("ruff", "check", ".")
        except CommandFailed:
            ruff_has_errors = True
            session.log("⚠️ Ruff: non-autofixable errors persist.")

    # mypy always runs
    session.run("mypy", "src")

    # Session failure if Ruff still has errors.
    if ruff_has_errors:
        session.error("Ruff check failed")

# ---------------------------------------------------------------------------
# test-unit session
# Run unit tests.
# ---------------------------------------------------------------------------
@nox.session(name="test-unit")
def tests_unit(session: nox.Session) -> None:
    """Run unit tests."""
    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    session.install(*_get_test_deps())
    session.install(".")
    session.run("pytest", "tests/tests_core", "tests/tests_plugins", "tests/tests_utils")

# ---------------------------------------------------------------------------
# test-ui session
# Run user interface tests.
# ---------------------------------------------------------------------------
@nox.session(name="test-ui")
def tests_ui(session: nox.Session) -> None:
    """Run user interface tests."""
    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    session.install(*_get_test_deps())
    session.install(".")
    # The UI tests never import the covered modules (core/plugins):
    # disable coverage to avoid "no data collected" warnings.
    session.run("pytest", "tests/tests_ui", "--no-cov")

# ---------------------------------------------------------------------------
# setup-dev session
# Create and / or activate the Python development environment.
# ---------------------------------------------------------------------------
@nox.session(name="setup-dev", venv_backend="none")
def setup_dev(session: nox.Session) -> None:
    """
    Create or activate the Python development environment in .venv.

    Creates the virtual environment if it doesn't exist, then installs
    the project in editable mode with the development extras.
    """

    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    root = Path(__file__).parent.resolve()
    venv_dir = root / ".venv"

    # Verify we're in the project root (pyproject.toml must exist)
    if not (root / "pyproject.toml").exists():
        session.error("This session must be run from the project root (where pyproject.toml is located).")

    # Create venv if it doesn't exist
    if not venv_dir.exists():
        session.log("Creating virtual environment in .venv...")
        session.run("python", "-m", "venv", str(venv_dir), external=True)
    else:
        session.log(f"Virtual environment already exists: {venv_dir}")

    # Determine the python executable in the venv (cross-platform)
    if os.name == "nt":
        python_exe = venv_dir / "Scripts" / "python.exe"
        pip_exe = venv_dir / "Scripts" / "pip.exe"
    else:
        python_exe = venv_dir / "bin" / "python"
        pip_exe = venv_dir / "bin" / "pip"

    # Verify the venv is valid
    if not python_exe.exists():
        session.error(f"Virtual environment is corrupted: {python_exe} not found. Delete .venv and retry.")

    # Install the project in editable mode with dev extras
    session.log("Installing the project in editable mode with dev extras...")
    session.run(python_exe, "-m", "pip", "install", "-e", ".[dev]", external=True)

    session.log("=" * 60)
    session.log("Development environment ready.")
    session.log("=" * 60)
    session.log(f"Python executable: {python_exe}")
    session.log(f"Pip executable: {pip_exe}")
    session.log("To activate the virtual environment, run:")
    if os.name == "nt":
        session.log(r"  PowerShell: .\.venv\Scripts\Activate.ps1")
        session.log(r"  CMD:        .venv\Scripts\activate.bat")
    else:
        session.log(r"  source .venv/bin/activate")
    session.log("Virtual environment is automatically activated in terminal windows in Visual Studio Code")

# ---------------------------------------------------------------------------
# compile-plugins session
# Compile every game plugin into a .pyd extension (build/plugins/).
# ---------------------------------------------------------------------------
@nox.session(name="compile-plugins")
def compile_plugins(session: nox.Session) -> None:
    """Compile every game plugin into a .pyd extension (build/plugins/)."""
    if os.name != "nt":
        session.skip("Plugin compilation targets Windows .pyd and should run on Windows.")

    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    session.install("nuitka>=4.2.2")
    session.run("python", "scripts/compile_plugins.py", env={"PYTHONUTF8": "1"})

# ---------------------------------------------------------------------------
# release session
# Build the standalone Windows executable.
# ---------------------------------------------------------------------------
@nox.session(name="release")
def release(session: nox.Session) -> None:
    """
    Build the standalone Windows executable, increment the build counter,
    stamp the build info, and package the release archive (zip + SHA256).
    """
    if os.name != "nt":
        session.skip("This session is designed to build a Windows executable and should run on Windows.")

    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    # Force UTF-8 for every child Python process: the default cp1252
    # console encoding on Windows crashes scripts printing non-ASCII
    # characters (e.g. make_icon.py prints an arrow "→").
    utf8_env = {"PYTHONUTF8": "1"}

    session.install(*_get_build_deps())
    session.install(".")
    session.run("python", "scripts/make_icon.py", env=utf8_env)

    # Compile the plugins into .pyd extensions before PyInstaller collects
    # them (the spec file raises if build/plugins/ is missing).
    session.install("nuitka>=4.2.2")
    session.run("python", "scripts/compile_plugins.py", env=utf8_env)

    root = Path(__file__).parent.resolve()
    pyproject_path = root / "pyproject.toml"
    build_info_path = root / "src" / "companion4soloplayer" / "build_info.py"
    dist_dir = root / "dist"

    # Install build dependencies
    session.install(*_get_build_deps())
    session.install(".")

    # Read pyproject.toml
    content = pyproject_path.read_text(encoding="utf-8")
    newline = "\r\n" if "\r\n" in content else "\n"

    # Increment the build counter in pyproject.toml
    build_match = re.search(r'(?m)^(?P<indent>[ ]*)build[ ]*=[ ]*(?P<number>\d+)[ ]*\r?$', content)

    if build_match:
        number = int(build_match.group("number")) + 1
        indent = build_match.group("indent")
        new_line = f"{indent}build = {number}"
        content = content[:build_match.start()] + new_line + content[build_match.end():]
    else:
        # First generation ever: append the dedicated table at the end of the file
        number = 1
        section = f"""# Numeric counter incremented by nox session 'build-exe' on every
# generated executable; displayed in the CLI banner after the
# version (e.g., "companion4soloplayer v0.1.0 build 12").
#
# Kept in a [tool.*] table on purpose: PEP 621 reserves the keys of
# [project], and setuptools rejects any custom entry found there.
[tool.companion4soloplayer]
build = {number}"""
        content = content.rstrip() + newline + newline + section + newline

    # Write back UTF-8 without BOM
    pyproject_path.write_text(content, encoding="utf-8")

    # Stamp the runtime module read by the CLI banner
    build_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stamp = f'''"""Generated by nox session 'release' - do not edit by hand.

This module is rewritten on every executable generation. Source-only
runs therefore always see the last generated value.
"""

BUILD_NUMBER = {number}
BUILD_DATETIME = "{build_datetime}"
'''
    build_info_path.write_text(stamp, encoding="utf-8")
    session.log(f"Build number: {number}")
    session.log(f"Build datetime: {build_datetime}")

    # Generate the executable
    session.run(
        "python",
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "companion4soloplayer.spec",
        env=utf8_env,
    )

    # Extract version from the (already updated) pyproject.toml
    version_match = re.search(r'(?m)^[ ]*version[ ]*=[ ]*"([^"]+)"[ ]*\r?$', content)

    # FIX MYPI: Use else block so mypy knows version_match is not None in the success path
    if version_match is None:
        session.error("Cannot locate the 'version' entry in pyproject.toml.")
    else:
        version = version_match.group(1)

    release_base_name = f"companion4soloplayer-win-x64-v{version}.{number}"
    zip_path = dist_dir / f"{release_base_name}.zip"
    sha_path = dist_dir / f"{release_base_name}.zip.sha256"

    # Stage the archive contents
    staging_dir = Path(tempfile.gettempdir()) / f"companion4soloplayer-release-{release_base_name}"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    # The one-dir build lives in dist/companion4soloplayer/: a minimal
    # executable next to an _internal/ folder with all runtime
    # libraries (Python DLLs, Qt, ...) and data files.
    app_dir = dist_dir / "companion4soloplayer"

    shutil.copy2(app_dir / "companion4soloplayer.exe", staging_dir / "companion4soloplayer.exe")
    shutil.copytree(app_dir / "_internal", staging_dir / "_internal")
    # TODO: Add future assets here (e.g., sample tilesets, docs)

    # Create fresh archive and SHA256
    if zip_path.exists():
        zip_path.unlink()
    if sha_path.exists():
        sha_path.unlink()

    # Create ZIP archive (recursive walk so the _internal/ folder is
    # fully included)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(staging_dir.rglob("*")):
            if file_path.is_dir():
                continue
            zf.write(file_path, arcname=file_path.relative_to(staging_dir))

    # Calculate SHA256 in "<HASH>  <FILENAME>" format (uppercase, standard Git)
    sha256_hash = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    hash_hex = sha256_hash.hexdigest().upper()
    sha_path.write_text(f"{hash_hex}  {release_base_name}.zip\n", encoding="ascii")

    # Cleanup staging directory
    shutil.rmtree(staging_dir)

    # Output summary
    session.log("")
    session.log(f"Built: {app_dir / 'companion4soloplayer.exe'} (build {number})")
    session.log(f"Release: {zip_path.name}")
    session.log(f"SHA256:  {hash_hex}  ({sha_path.name})")

# ---------------------------------------------------------------------------
# check-venv session
# Check if a virtual environment is active.
# ---------------------------------------------------------------------------
@nox.session(name="check-venv", venv_backend="none")
def check_venv(session: nox.Session) -> None:
    """Check if a virtual environment is active."""
    import sys

    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.log(f"✓ Virtual environment is active: {venv}")
        session.log(f"  Python: {sys.executable}")
    else:
        session.log("✗ No virtual environment is active")
        session.log(r"  Run: .\.venv\Scripts\Activate.ps1")

# ---------------------------------------------------------------------------
# docs session
# Create technical documentation, static build
# ---------------------------------------------------------------------------
@nox.session(name="docs")
def docs(session: nox.Session) -> None:
    """Create technical documentation, static build."""
    _generate_docs(session, is_live=False)

# ---------------------------------------------------------------------------
# docs-live session
# Create technical documentation, live reloading server
# ---------------------------------------------------------------------------
@nox.session(name="docs-live")
def docs_live(session: nox.Session) -> None:
    """Create technical documentation, live reloading server."""
    _generate_docs(session, is_live=True)

# ---------------------------------------------------------------------------
# stats session
# Compute code statistics
# ---------------------------------------------------------------------------
@nox.session(name="stats", venv_backend="none")
def stats(session: nox.Session) -> None:
    """Compute code statistics (lines of code, etc.)"""
    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(f"Virtual environment is active: {venv}. Please deactivate it or open a new terminal before running this session.")

    cloc_executable =  f"{os.getcwd()}/.bintools/cloc/cloc-2.06.exe"
    report_file = './stats.txt'
    history_file = './stats_histo.txt'

    # Force UTF-8 for every child Python process: the default cp1252
    # console encoding on Windows crashes scripts printing non-ASCII
    # characters (e.g. make_icon.py prints an arrow "→").
    utf8_env = {"PYTHONUTF8": "1"}

    retcode = session.run(
        cloc_executable,
        '--skip-uniqueness',
        '--quiet',
        '--exclude-ext=.pyc,".py,cover"',
        '--not-match-d=(.pytest_cache|.mypy_cache|companion4soloplayer.egg-info)',
        '--skip-archive=(zip|tar(.(gz|Z|bz2|xz|7z))?)',
        f'--report-file={report_file}',
        '--found=./.tmp/found.txt',
        '--ignored=./.tmp/ignored.txt',
        '--fmt=2',
        './src/',
        './tests/',
        './scripts/',
        './docs/',
        './noxfile.py',
        './*.md',
        './*.toml',
        './mkdocs.yml',
        env=utf8_env,
    )

    if retcode:
        # Display the content of the report file if cloc succeeded
        with open(report_file, encoding='utf-8') as file:
            content = file.read()
            print(content)

        # --- Gestion de l'historique ---
        now = datetime.now()
        date_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")

        # Format de la nouvelle entrée (précédée de la date et l'heure)
        new_entry = f"=== {date_time_str} ===\n{content}\n\n"

        existing_entries = []
        if os.path.exists(history_file):
            with open(history_file, encoding='utf-8') as f:
                histo_content = f.read()

            # Découpe le fichier en utilisant le marqueur de date/heure comme délimiteur.
            # Les parenthèses () dans re.split permettent de conserver le délimiteur dans la liste.
            parts = re.split(r'(=== \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ===\n)', histo_content)

            # Reconstruction des entrées (une entrée = entête + corps)
            for i in range(1, len(parts), 2):
                header = parts[i]
                body = parts[i+1] if i+1 < len(parts) else ""
                existing_entries.append(header + body)

        # Filtrage : on retire l'ancienne entrée si elle est à la même date (jour)
        filtered_entries = []
        for entry in existing_entries:
            match = re.match(r'=== (\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2} ===', entry)
            if match:
                entry_date = match.group(1)
                if entry_date == date_str:
                    continue # On ignore l'ancienne entrée du jour pour la remplacer
            filtered_entries.append(entry)

        # Insertion de la nouvelle entrée au début de la liste
        filtered_entries.insert(0, new_entry)

        # Réécriture du fichier historique
        with open(history_file, 'w', encoding='utf-8') as f:
            f.write("".join(filtered_entries))

# ---------------------------------------------------------------------------
# check-updates session
# Check for newer versions of Python packages referenced in pyproject.toml
# ---------------------------------------------------------------------------
@nox.session(name="check-updates", venv_backend="none")
def check_updates(session: nox.Session) -> None:
    """Check for newer versions of Python packages referenced in pyproject.toml."""

    try:
        with open("pyproject.toml", "rb") as f:
            pyproject = tomllib.load(f)
    except FileNotFoundError:
        session.error("pyproject.toml not found in the current directory.")

    packages: dict[str, str] = {}

    def process_deps(deps_list: list[str]) -> None:
        for dep_str in deps_list:
            # Ignore les commentaires en ligne
            dep_str = dep_str.split('#')[0].strip()
            if not dep_str:
                continue

            # Extraction du nom du package et du reste (spécificateurs, marqueurs, etc.)
            match = re.match(r'^([a-zA-Z0-9][-a-zA-Z0-9._]*)\s*(.*)$', dep_str)
            if not match:
                continue

            name = match.group(1).lower()
            rest = match.group(2).strip()

            # On ne garde que la partie spécificateur (avant un éventuel point-virgule de marqueur d'environnement)
            specifier_part = rest.split(';')[0].strip()

            # Extraction des chaînes ressemblant à des versions (ex: ">=26.5.1" -> "26.5.1")
            versions = re.findall(r'\d+(?:\.\d+)*(?:\.\w+)*', specifier_part)
            local_version = versions[0] if versions else "any"

            # Si un package est présent plusieurs fois (ex: dans dev et lint), on garde la version la plus élevée
            if name in packages:
                existing_ver = packages[name]
                if existing_ver != "any" and local_version != "any" and ver_cmp(local_version) > ver_cmp(existing_ver):
                    packages[name] = local_version
            else:
                packages[name] = local_version

    # Traitement des dépendances principales
    project_deps = pyproject.get("project", {}).get("dependencies", [])
    process_deps(project_deps)

    # Traitement des dépendances optionnelles
    optional_deps = pyproject.get("project", {}).get("optional-dependencies", {})
    for group_deps in optional_deps.values():
        process_deps(group_deps)

    # Vérification des mises à jour sur PyPI
    updates = []
    for name, local_version in packages.items():
        if local_version == "any":
            continue

        url = f"https://pypi.org/pypi/{name}/json"
        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                pypi_version = data["info"]["version"]

                if ver_cmp(pypi_version) > ver_cmp(local_version):
                    updates.append({
                        "name": name,
                        "local": local_version,
                        "pypi": pypi_version
                    })
        except urllib.error.HTTPError as e:
            session.warn(f"Could not fetch info for {name}: HTTP {e.code}")
        except Exception as e:
            session.warn(f"Could not fetch info for {name}: {e}")

    # Tri alphabétique croissant par nom de package
    updates.sort(key=lambda x: x["name"])

    if not updates:
        session.log("All packages are up to date!")
        return

    # Calcul dynamique des largeurs de colonnes pour un alignement parfait
    max_name_len = max(len(u["name"]) for u in updates)
    max_local_len = max(len(u["local"]) for u in updates)
    max_pypi_len = max(len(u["pypi"]) for u in updates)

    # Garantie que les en-têtes rentrent toujours
    max_name_len = max(max_name_len, len("Package"))
    max_local_len = max(max_local_len, len("Local version"))
    max_pypi_len = max(max_pypi_len, len("Pypi version"))

    # Affichage du tableau
    separator = "-" * (max_name_len + max_local_len + max_pypi_len + 6)
    print(separator)
    print(f"{'Package':<{max_name_len}}   {'Local version':<{max_local_len}}   {'Pypi version':<{max_pypi_len}}")
    print(separator)

    for u in updates:
        print(f"{u['name']:<{max_name_len}}   {u['local']:<{max_local_len}}   {u['pypi']:<{max_pypi_len}}")

    print(separator)
    print(f"{len(updates)} packages need to be updated")

# ---------------------------------------------------------------------------
# backup session
# Create a backup archive of the project sources
# ---------------------------------------------------------------------------
@nox.session(name="backup", venv_backend="none")
def backup(session: nox.Session) -> None:
    """Create a .7z backup archive of the project sources in the parent directory."""
    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(
            f"Virtual environment is active: {venv}. "
            "Please deactivate it or open a new terminal before running this session."
        )

    # Path to the 7z executable
    seven_zip_exe = os.path.join(os.getcwd(), ".bintools", "7-Zip", "7z.exe")
    if not os.path.exists(seven_zip_exe):
        session.error(f"7-Zip executable not found at: {seven_zip_exe}")

    # Generation of the archive name and target path (parent directory)
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M")
    archive_name = f"companion4soloplayer_{timestamp}.7z"

    # Using abspath to ensure a correct absolute path
    parent_dir = os.path.abspath(os.path.join(os.getcwd(), ".."))
    archive_path = os.path.join(parent_dir, archive_name)

    # Filtering of files/directories to include to only keep those that exist.
    # This avoids 7z from emitting errors if optional files
    # (like logs or stats) have not been generated yet.
    existing_includes = [path for path in BACKUP_INCLUDES if os.path.exists(path)]

    if not existing_includes:
        session.error("No files or directories to include in the backup.")

    # Preparation of exclusion arguments for 7z.
    # 7z uses the format -xr!<pattern> to exclude recursively.
    # We remove the trailing '/' so the pattern matches the directory name.
    exclude_args = [f"-xr!{path.rstrip('/')}" for path in BACKUP_EXCLUDES]

    session.log(f"Creating backup archive: {archive_path}")

    # Execution of the 7z command
    # Syntax: 7z a <archive_name> <files...> -xr!<exclude...>
    session.run(
        seven_zip_exe,
        "a",
        archive_path,
        *existing_includes,
        *exclude_args,
    )

    session.log(f"Backup successfully created: {archive_path}")

# ---------------------------------------------------------------------------
# diagrams session
# Create class and package diagrams of the project
# ---------------------------------------------------------------------------
@nox.session(name="diagrams")
def diagrams(session: nox.Session) -> None:
    """Create class and package diagrams of the project."""
    venv = os.environ.get("VIRTUAL_ENV")

    if venv:
        session.skip(
            f"Virtual environment is active: {venv}. "
            "Please deactivate it or open a new terminal before running this session."
        )

    if not check_network_access(session, url="https://pypi.org/simple/"):
        session.error("Network access to PyPI is required for this session. Please check your connection.")

    session.install(*_get_diagrams_deps())
    session.install(".")

    session.log("Creating diagrams of the project...")

    output_dir = "docs/assets/diagrams"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    source_dir = Path("src/companion4soloplayer")
    if not source_dir.exists():
        session.error(f"Source directory '{source_dir}' not found.")

    # 1. Discovery of packages and modules
    targets = []
    for path in source_dir.rglob("*"):
        # Include packages (directories containing an __init__.py)
        if path.is_dir() and (path / "__init__.py").exists() or path.is_file() and path.suffix == ".py" and not path.name.startswith("_"):
            targets.append(path)

    # Remove duplicates and sort for a predictable generation order
    targets = sorted(set(targets), key=lambda p: str(p))

    session.log(f"Discovery of {len(targets)} targets (packages/modules) for diagram generation.")

    # 2. Iterative generation
    for target in targets:
        # Create a secure project name from the relative path
        # Example: "src/companion4soloplayer/core/utils.py" -> "companion4soloplayer_core_utils"
        rel_path = target.relative_to(source_dir.parent)
        project_name = str(rel_path).replace("/", "_").replace("\\", "_").replace(".py", "")

        session.log(f"Generating diagrams for : {project_name}")

        # --project : project name (used in the diagram title)
        # --output : output format (plantuml, png, dot)
        # --ignore : directories to exclude (e.g., venv, tests)
        cmd = [
            "pyreverse",
            "--output", "plantuml",
            "--project", project_name,  # This is what names the output file: classes_<project_name>.puml
            "--ignore", "venv,tests,.git,__pycache__",
            "--output-directory", output_dir,
            "--colorized",
            "--filter-mode", "ALL",  # No filtering, include all classes and methods (public and private)
            str(target)
        ]

        session.run(*cmd)

    # 3. POST-PROCESSING: Injecting colors and Python visibility modifiers
    session.log("Application of custom style (Python visibility + colors)...")

    # Style block to be injected immediately after @startuml
    style_block = """' --- Custom Styling: Visibility & Colors ---
skinparam classAttributeFontColor #0055FF
skinparam classAttributeFontStyle normal
skinparam classFontColor #333333
skinparam classFontStyle normal
' -----------------------------------------------"""

    def get_python_visibility(name: str) -> str:
        """Determine UML visibility modifier from Python naming conventions."""
        if name.startswith("__") and name.endswith("__"):
            return "+"
        elif name.startswith("__"):
            return "-"
        elif name.startswith("_"):
            return "#"
        else:
            return "+"

    # Regex to detect the start of a PlantUML class block
    class_start_pattern = re.compile(r'^\s*class\s+["\w].*\{')

    # FIXED Regex: Captures 4 groups for both attributes and methods
    # Group 1: indent (\s+)
    # Group 2: optional existing visibility modifier ([\+\-\#~]\s*)?
    # Group 3: the actual name (\w+)
    # Group 4: the rest of the line, e.g., " : int" or "(duration_ms: int) -> None" (\s*[:\(].*)?$
    member_pattern = re.compile(r"^(\s+)([\+\-\#~]\s*)?(\w+)(\s*[:\(].*)?$")

    # Note: pyreverse generates .puml files. If you renamed them to .plantuml, keep *.plantuml
    puml_files = list(Path(output_dir).glob("*.puml")) + list(Path(output_dir).glob("*.plantuml"))
    # Remove duplicates if any
    puml_files = list(set(puml_files))
    
    total_matches = 0

    for puml_file in puml_files:
        session.log(f"Processing {puml_file.name}...")
        content = puml_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        processed_lines = []
        style_injected = False
        in_class_block = False

        for line in lines:
            processed_lines.append(line)

            # Inject the style block immediately after @startuml
            if not style_injected and line.strip().lower().startswith("@startuml"):
                processed_lines.append(style_block)
                style_injected = True

            # Detect the start of a PlantUML class block
            if class_start_pattern.match(line):
                in_class_block = True
                continue

            # Detect the end of a class block
            if in_class_block and line.strip() == "}":
                in_class_block = False
                continue

            # Process only members inside class blocks
            if in_class_block and "<color:" not in line:
                match = member_pattern.match(line)
                if match:
                    # Unpack the 4 groups correctly
                    indent, visibility_opt, name, rest = match.groups()

                    if name is None:
                        continue

                    rest = rest or ""
                    visibility = get_python_visibility(name)

                    # Method (contains parentheses in 'rest') → green and bold
                    if "(" in rest:
                        processed_lines[-1] = f"{indent}{visibility}<color:#008000><b>{name}{rest}</b></color>"
                    # Attribute → gets the correct visibility modifier, color handled by skinparam
                    else:
                        processed_lines[-1] = f"{indent}{visibility}{name}{rest}"

                    total_matches += 1

        puml_file.write_text("\n".join(processed_lines) + "\n", encoding="utf-8")

    session.log(f"Processing completed. {len(puml_files)} .puml files processed, {total_matches} members styled successfully.")

    if total_matches == 0:
        session.warn("ATTENTION : No members were detected. Check the content of a generated .puml file.")

    session.log("Diagrams successfully created")
