# Companion4SoloPlayer (C4SP) - Context File and Development Guide

## Overview

**Companion4SoloPlayer (C4SP)** is a free, non-profit, open-source companion application designed to make it easy to manage dungeon crawler style board game sessions. The application is modular and can support several games through a plugin system.

**GitHub repository**: [to be created]
**License**: MIT
**Language**: Python 3.13+
**Target platform**: Windows (standalone binary)
**Status**: Project in development

---

## LEGAL CONSTRAINTS (CRITICAL)

### 1. Fundamental principles

#### 1.1 What is FORBIDDEN

- ❌ Using registered trademark names in source code, file names, or variable names
  - Forbidden examples: "HeroQuest", "HQ", "Zargon", "Morcar", "Fimir", "Chaos Warrior"
  - Forbidden examples: "4 Against Darkness" (as a file/variable name)
  - Forbidden examples: "2D6 Dungeon" (as a file/variable name)

- ❌ Reproducing official quest, item, or rule texts
  - Never copy-paste text from official booklets
  - Always rewrite in your own words

- ❌ Using official artwork
  - No scans, no reproductions, no adaptations of protected images

- ❌ Using official logos
  - No Hasbro, Games Workshop, Ganesha Games, DR Games, etc. logos

- ❌ Suggesting official affiliation or endorsement
  - Never write "Official application for HeroQuest"
  - Always specify "not affiliated, not endorsed"

#### 1.2 What is ALLOWED

- ✅ Using generic fantasy terms
  - Classes: Barbarian, Wizard, Dwarf, Elf, Cleric, Thief
  - Monsters: Skeleton, Goblin, Orc, Zombie, Dragon
  - Places: Dungeon, Fortress, Tower, Cave

- ✅ Implementing game mechanics
  - Rules as concepts are not protectable
  - Rewrite the rules in your own words

- ✅ Mentioning compatibility in descriptions
  - Use *nominative fair use*: "compatible with the mechanics of [GameName]"
  - Only in READMEs, descriptions, and communications

- ✅ Creating your own descriptions
  - Item, room, and monster descriptions (original)
  - Procedural encounter tables

- ✅ Integrating community content with permission
  - Fan-made quests with the author's written consent
  - Clearly credit the authors

#### 1.3 Plugin structure

Each plugin must contain a `README.md` file with a clear legal disclaimer.

#### 1.4 Global disclaimer (to include in the main README)

The complete disclaimer is available in the main README.md file.

---

## TECHNICAL ARCHITECTURE

### 1. Project structure

    companion4soloplayer/
    ├── src/companion4soloplayer/                # Python sources (importable package)
    │   ├── main.py                              # Entry point: config, logging, Qt
    │   ├── app/                                 # Qt application
    │   │   └── application.py                   # CompanionApplication + config
    │   ├── core/                                # Generic engine
    │   │   ├── __init__.py
    │   │   ├── character_tracker.py             # HP, stats, inventory management
    │   │   ├── dice_roller.py                   # Dice rolls (d6, d10, d100, custom)
    │   │   ├── dice_expression.py               # Dice notation value (2d6, 1d20+3)
    │   │   ├── procedural_generator.py          # Procedural dungeon generation
    │   │   ├── combat_resolver.py               # Combat resolution
    │   │   ├── quest_manager.py                 # Objective and step tracking
    │   │   ├── rule_engine.py                   # Hybrid YAML/Python rule engine
    │   │   ├── interface/                       # Generic game interfaces
    │   │   │   ├── __init__.py
    │   │   │   └── game_plugin.py               # GamePlugin contract (every plugin)
    │   │   ├── creation/                        # Character creation engine
    │   │   │   ├── __init__.py
    │   │   │   ├── context.py                   # State container (choices + computed values)
    │   │   │   ├── inputs.py                    # Input providers (UI-agnostic answers)
    │   │   │   ├── rules.py                     # Condition/Effect rule engine
    │   │   │   ├── strategies.py                # Attribute generation strategies
    │   │   │   ├── pipeline.py                  # Ordered step pipeline + report
    │   │   │   ├── workflow.py                  # YAML workflow loader (step order)
    │   │   │   └── steps/                       # Generic creation steps
    │   │   │       ├── __init__.py
    │   │   │       ├── base.py                  # CreationStep ABC + step results
    │   │   │       ├── identity.py              # IdentityStep (name, background)
    │   │   │       ├── selection.py             # SelectionStep (race, class...)
    │   │   │       ├── attributes.py            # AttributeGenerationStep
    │   │   │       ├── skills.py                # SkillSelectionStep
    │   │   │       └── spells.py                # SpellSelectionStep
    │   │   └── rules/                           # Shared rule elements
    │   │       ├── __init__.py
    │   │       └── oracle_rule.py               # OracleRule (shared by all plugins)
    │   │
    │   ├── plugins/                             # Game-specific modules
    │   │   │                                    # Every plugin shares the same layout:
    │   │   │                                    # data.py, manifest.py, plugin.py,
    │   │   │                                    # rules/ (1 file per class), datas/
    │   │   └── demo_plugin/                     # Demo plugin
    │   │       ├── __init__.py                  # Facade: Plugin + rule re-exports
    │   │       ├── data.py                      # datas/ directory + YAML access
    │   │       ├── manifest.py                  # PluginMetadata schema
    │   │       ├── plugin.py                    # Plugin facade (GamePlugin API)
    │   │       ├── rules/                       # Plugin specific rules
    │   │       │   ├── __init__.py
    │   │       │   ├── character_creation_rule.py
    │   │       │   ├── combat_rule.py
    │   │       │   ├── loot_rule.py
    │   │       │   └── magic_rule.py
    │   │       ├── creation/                    # Character creation (game system side)
    │   │       │   ├── __init__.py
    │   │       │   ├── strategies.py            # Named generation methods (4d6 keep 3)
    │   │       │   ├── filters.py               # Spell availability filter
    │   │       │   └── workflow.py              # Pipeline assembly (data + rules)
    │   │       ├── datas/                       # Plugin specific datas
    │   │       │   ├── plugin.yaml
    │   │       │   ├── classes.yaml
    │   │       │   ├── monsters.yaml
    │   │       │   ├── items.yaml
    │   │       │   ├── rules.yaml
    │   │       │   ├── races.yaml               # Character creation catalogs
    │   │       │   ├── skills.yaml
    │   │       │   ├── spells.yaml
    │   │       │   ├── workflow.yaml            # Character creation step order
    │   │       │   └── creation_rules.yaml      # Bonuses (conditions/effects)
    │   │       └── README.md
    │   │
    │   ├── utils/                               # Shared helpers
    │   │   ├── __init__.py
    │   │   ├── resource_manager.py              # Centralized resource access
    │   │   ├── config_manager.py                # TOML configuration file
    │   │   ├── logger.py                        # Logging setup
    │   │   ├── plugin_loader.py                 # Discovery and safe loading of plugins
    │   │   └── yaml_loader.py                   # Safe YAML loader (custom tags)
    │   │
    │   └── ui/                                  # User interface
    │       ├── __init__.py
    │       ├── main_window.py                   # Main window
    │       ├── character_panel.py               # Character management panel
    │       ├── quest_panel.py                   # Quest management panel
    │       ├── grid_view.py                     # Dungeon grid view
    │       └── dialogs/                         # Dialog windows
    │           ├── quest_wizard.py              # Quest creation wizard
    │           └── settings_dialog.py           # Settings
    │
    ├── assets/                                  # Shared assets (CC0 only)
    │   ├── icons/                               # Icons (CC0)
    │   ├── fonts/                               # Fonts (free)
    │   └── sounds/                              # Sounds (CC0)
    │
    ├── data/                                    # User data
    │   ├── saves/                               # Game saves
    │   ├── custom_quests/                       # Custom quests
    │   └── config/                              # config.toml (window, logging)
    │
    ├── tests/                                   # Tests
    │   ├── tests_core/                          # Core unit tests
    │   ├── tests_plugins/                       # Plugins tests
    │   ├── tests_utils/                         # Utils tests (config, logger, plugin loader, resources, yaml)
    │   └── tests_ui/                            # Core UI tests
    │
    ├── docs/                                    # Documentation
    │   ├── user_guide.md                        # User guide
    │   ├── plugin_development.md                # Plugin development guide
    │   └── legal_guidelines.md                  # Legal guidelines
    │
    ├── scripts/                                 # Project scripts
    │   ├── create_project.py                    # This project generator
    │   ├── make_icon.py                         # Icon Creator script
    │   ├── resize_logo.py                       # Logo Resizer script
    │   └── compile_plugins.py                   # Compile the game plugins into extension modules
    │
    ├── companion4soloplayer.spec                # PyInstaller build recipe
    ├── build/, dist/                            # PyInstaller output (generated)
    │
    ├── .vscode/                                 # Visual Studio Code workspace
    │   └── settings.json                        # Editor settings
    ├── companion4soloplayer.code-workspace      # VS Code workspace file
    │
    ├── pyproject.toml                           # Project configuration
    ├── README.md                                # Main README with disclaimer
    ├── CONTEXT.md                               # Complete development guide
    ├── LICENSE                                  # MIT license
    └── .gitignore                               # Git ignore

### 2. Tech stack

#### 2.1 Language and version
- **Python**: 3.13+ (latest stable version)
- **Type hints**: Mandatory for all public functions
- **Docstrings**: Google format for all functions and classes

#### 2.2 User interface
- **Framework**: PyQt6 or PySide6 (either one, but consistent throughout the project)
- **Style**: QSS (Qt Style Sheets) for theming
- **Responsive**: Support for high-resolution screens (4K)

#### 2.3 Data management
- **Format**: YAML (with comments) for plugin/rule data, loaded through a
  hardened `yaml.SafeLoader` subclass with custom tags (`!pyclass`, `!dice`);
  JSON for saves, TOML for the user configuration (`data/config/config.toml`)
- **Validation**: Pydantic for plugin manifest validation
- **Serialization**: Standard JSON for saves (no pickle for security reasons)

#### 2.4 Build and distribution
- **Packaging**: PyInstaller to create the standalone Windows binary
- **Distribution**: Portable ZIP + optional NSIS installer
- **Dependencies**: All dependencies included in the binary

#### 2.5 Testing
- **Framework**: pytest
- **Coverage**: Minimum target 80%
- **CI/CD**: GitHub Actions for automated tests

#### 2.6 Documentation
- **Format**: Markdown
- **Generation**: MkDocs for technical documentation
- **API docs**: Sphinx or pdoc for automatic documentation

### 3. Application runtime: configuration, logging and shared state

Three modules cooperate at startup, in a strict order: the logger needs the
configuration, and both must be ready before any Qt object is built.

    main()
      ├──> ConfigManager()                read/creates data/config/config.toml
      ├──> setup_logging(config)          applies the [logging] table
      ├──> CompanionApplication(...)      carries the config application-wide
      ├──> MainWindow()                   applies the [window] table
      └──> app.exec()                     logs the last message on return

#### 3.1 utils/config_manager.py — TOML configuration

- **File location** (`default_config_path()`), in priority order:
  1. Frozen (PyInstaller) build: `<executable_dir>/data/config/config.toml`,
     matching the portable layout (`data/` sits next to the executable);
  2. Source checkout: walk up from this module until a directory holding a
     `data/` folder is found (the project root);
  3. Fallback: the current working directory.
- **Creation**: when the file is missing, `ConfigManager.__init__` creates it
  with the default tables, and `save()` creates the missing parent folders.
  The file is local configuration: it is listed in `.gitignore`.
- **Loading**: the file is merged *over* the defaults, table by table
  (`[window]`, `[logging]`). A partial or hand-edited file keeps the default
  values for the keys it does not define; a corrupted file is rewritten with
  the defaults.
- **Access**: `window()` and `logging()` return live tomlkit tables. Writing
  a key updates the in-memory configuration, `save()` persists it. This is
  how `MainWindow` stores the geometry when the application closes.
- A **single** instance is created in `main()` and shared application-wide
  through `CompanionApplication` (see 3.3).

Default file:

    [window]
    x = 0
    y = 0
    width = 1280
    height = 720
    maximized = true

    [logging]
    enabled = true
    level = "DEBUG"
    file = "./companion4soloplayer.log"
    mode = "write"      # write -> overwrite, append -> keep previous content

#### 3.2 utils/logger.py — logging

- `setup_logging(config)` runs in `main()` right after the configuration is
  read and **before** any Qt object exists, so the whole startup can be logged.
- `[logging]` settings:
  - `enabled = false`: no handler is installed and every record is blocked
    through `logging.disable()`;
  - `level`: standard `logging` names (`DEBUG`, `INFO`, `WARNING`, ...),
    resolved with `logging.getLevelNamesMapping()`; an unknown name falls
    back to `INFO` and is reported in the log;
  - `file`: UTF-8 file handler **and** console handler; a relative path is
    resolved against the working directory;
  - `mode`: `LogMode` enum — `write` (overwrite, default) or `append`; an
    unknown value falls back to `write` and is reported in the log.
- **Idempotent**: the handlers installed by a previous call are removed
  first, so calling it twice never stacks duplicate handlers.
- Application records use the `companion4soloplayer` logger
  (`APP_LOGGER_NAME`). `main()` writes the last message of the session
  (`Application exiting with code <n>`) when the event loop returns.

#### 3.3 app/application.py — shared application state

- `CompanionApplication(QApplication)` holds the `ConfigManager` as a member
  (`app.config`): the configuration is read once and stays reachable from
  anywhere through `application_config()`, which returns `None` when the
  process was not started through `main()` (tests, stubs).
- `MainWindow(config=None)` uses the given configuration, or falls back to
  `application_config()`. It restores the geometry and the maximized state at
  startup — a position outside every connected screen is ignored so the
  window cannot be lost off-screen — and saves them in `closeEvent()`.
- Tests inject their own `ConfigManager` (temporary folder) instead of
  relying on the global state.

Tests: `tests/tests_utils/test_config_manager.py`,
`tests/tests_utils/test_logger.py`, `tests/tests_ui/test_window_config.py`
and the `main()` wiring test in `tests/tests_ui/test_main_window.py`.

---

## DEVELOPMENT CONVENTIONS

### 1. Code style

#### 1.1 Formatting
- **Black**: Automatic formatting (100-character max lines)
- **Ruff**: Linting and style checking
- **isort**: Automatic import sorting

#### 1.2 Typing
- **Type hints**: Mandatory for all public functions
- **mypy**: Static type checking
- **Pydantic**: JSON data validation

#### 1.3 Naming
- **Variables/functions**: snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **Modules**: snake_case
- **Plugins**: gamename_plugin (e.g. demo_plugin)

### 2. Plugin management

#### 2.1 Plugin interface

Each plugin must implement the `GamePlugin` interface defined in
`core/interface/game_plugin.py` (a generic contract of the engine). The
`PluginLoader` utility that discovers and safely loads the plugins lives
in `utils/plugin_loader.py`.

#### 2.2 plugin.yaml file

Each plugin must contain a `datas/plugin.yaml` file with the following
metadata:
- `name`: Generic plugin name (no registered trademark)
- `version`: Plugin version (semver format)
- `description`: Short description
- `author`: Author name
- `license`: License (MIT recommended)
- `compatible_games`: List of compatible games (descriptive information)
- `disclaimer`: Legal disclaimer
- `features`: Multi-line free-form description of the features covered by the plugin
- `dependencies`: Dependencies on the core

### 3. Data management

#### 3.1 Important rules
- **No pickle**: Plugin data is read through the safe YAML loader, saves
  through JSON and the configuration through TOML, for security reasons
- **UTF-8 encoding**: Mandatory for all data files
- **Strict validation**: Any non-compliant data must raise an explicit exception
- **Informative logs**: Log the file path and error type on failure

### 4. Testing

#### 4.1 Test structure

Tests must be organized as follows:
- `tests/tests_core/`: Tests for the generic engine
- `tests/tests_plugins/`: Tests for the plugins
- `tests/tests_utils/`: Tests for the shared utilities
- `tests/tests_ui/`: Tests for the user interface

#### 4.2 Requirements
- Each public function must have at least one unit test
- Tests must be fast and independent
- Use fixtures for test data
- Minimum code coverage: 80%

### 5. Documentation

#### 5.1 Docstrings
Google format is mandatory for all public functions, with:
- Short description
- Detailed description (if necessary)
- `Args:` section for parameters
- `Returns:` section for the return value
- `Raises:` section for exceptions
- `Example:` section for a usage example

#### 5.2 README.md
The main README must contain:
1. Project description
2. Legal disclaimer
3. Features
4. Installation
5. Usage
6. Development
7. License

---

## DEVELOPMENT WORKFLOW

### 1. Development environment

    # Clone the repository
    git clone https://github.com/ultra-sonic-28/companion4soloplayer.git
    cd companion4soloplayer

    # Create a virtual environment and install development dependencies
    nox -s setup-dev

    # Check the installation using nox
    nox -s tests-unit
    nox -s tests-ui
    nox -s lint

### 2. Development cycle

    # 1. Create a feature branch
    git checkout -b feature/feature-name

    # 2. Develop and test
    # ... code ...
    nox -s tests-unit
    nox -s tests-ui
    nox -s lint

    # 3. Commit
    git add .
    git commit -m "feat: description of the feature"

    # 4. Push and create a Pull Request
    git push origin feature/feature-name
    # Create a PR on GitHub

    # 5. After approval, merge into main
    git checkout main
    git merge feature/feature-name

### 3. Commit messages

Conventional format:

    <type>(<scope>): <description>

    [optional body]

    [optional footer]

Allowed types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

Examples:
    feat(core): add the character management system
    fix(plugin): fix damage calculation
    docs(readme): update the legal disclaimer
    test(core): add tests for the dungeon generator

### 4. Windows Build

    # Build the executable, the release zip and its SHA256 checksum
    nox -s release

Each run:
1. increments the `build` entry of the `[tool.companion4soloplayer]`
   table in pyproject.toml,
2. stamps it into `src/companion4soloplayer/build_info.py`
   (read by the CLI banner, e.g. "companion4soloplayer v0.1.0 build 12"),
3. compiles plugins if necessary
4. runs PyInstaller on `companion4soloplayer.spec`,
5. packages the release archive with its SHA256 checksum.

---

## PRE-PUBLICATION CHECKLIST

### For each plugin

- [ ] The plugin name contains no registered trademark
- [ ] Class/monster names are generic
- [ ] Rules are rewritten in your own words
- [ ] The `README.md` file contains the legal disclaimer
- [ ] The `datas/plugin.yaml` file contains the correct metadata
- [ ] Visual assets are CC0 or created by you
- [ ] Unit tests pass
- [ ] Documentation is up to date

### For the overall project

- [ ] The main README contains the legal disclaimer
- [ ] The MIT license is present
- [ ] The `.gitignore` file is configured
- [ ] GitHub Actions are configured (automated tests)
- [ ] Code is formatted with Black
- [ ] Ruff linting passes without errors
- [ ] Types are checked with mypy
- [ ] Test coverage is >= 80%
- [ ] Documentation is complete

---

## USEFUL RESOURCES

### Legal documentation
- Nominative Fair Use (US): https://www.law.cornell.edu/wex/nominative_fair_use
- DMCA Takedown Process: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/dmca-takedown-policy
- Copyright vs Trademark: https://www.copyright.gov/help/faq/faq-differences.html

### Royalty-free assets
- Kenney.nl: https://kenney.nl/ - CC0 assets
- OpenGameArt.org: https://opengameart.org/ - Free assets
- Game-icons.net: https://game-icons.net/ - CC-BY icons

### Technical documentation
- PyQt6 Documentation: https://doc.qt.io/qtforpython/
- Pydantic Documentation: https://docs.pydantic.dev/
- PyInstaller Documentation: https://pyinstaller.org/en/stable/

### Community
- CasusNO: https://www.casusno.fr/ - French RPG forum
- TricTrac: https://forum.trictrac.net/ - Board game forum

---

## CONTACT AND SUPPORT

For any legal or technical question:
- Open an issue on GitHub
- Contact the maintainer: [your.email@example.com]

---

**Last updated**: 2026-10-06
**Document version**: 1.3.0
