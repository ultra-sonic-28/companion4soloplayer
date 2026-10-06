# ![Logo Companion4SoloPlayer](assets/logo-64x64.png) Welcome to the Companion4SoloPlayer Technical Documentation

Welcome to the technical documentation for **Companion4SoloPlayer** (C4SP), an open-source, modular companion desktop application designed to streamline and enhance tabletop dungeon crawler board game sessions.

This site provides comprehensive technical documentation detailing the architecture, modules, classes, and APIs of the Companion4SoloPlayer application.

---

## Context & Vision

Companion4SoloPlayer is an independent, non-profit companion application created for players and Game Masters of dungeon crawler style board games and solo/co-op tabletop role-playing games.

The application assists players at the game table by managing:

- Character statistics, inventory, and health tracking.
- Combat resolution and damage calculation.
- Flexible dice rolling mechanics (standard polyhedrals, modifiers, roll histories).
- Quest objectives and scenario progression tracking.
- Procedural dungeon, room, and encounter generation.
- Game system expansion via an extensible, decoupled plugin architecture.

This documentation site is aimed at **developers, contributors, and technical enthusiasts** who wish to understand the inner workings of Companion4SoloPlayer, build and package the desktop application, develop custom game plugins, or contribute new features and bug fixes.

For a functional, user-oriented walkthrough of every capability provided by the application, please explore the [Features](features.md) guide.

---

## Goals of this Documentation

1. **Architecture & Design Principles**: Explain how Companion4SoloPlayer separates pure-Python, deterministic game logic (`core`) from the desktop graphical user interface (`ui`), and how dynamic plugin loading works at runtime.
2. **Complete API Reference**: Provide structured, automatically generated reference pages powered by [mkdocstrings](https://mkdocstrings.github.io/) for all public modules, classes, methods, and functions.
3. **Plugin Developer Onboarding**: Offer clear insights into the `GamePlugin` interface, YAML data formats, and plugin lifecycle to empower developers to create new system adaptations.
4. **Developer Enablement**: Document local environment setup, build workflows (PyInstaller / Nuitka / Nox), automated test suites, and documentation contribution processes.

---

## Documentation Structure

The documentation follows the architectural layout of the source repository and is divided into several main areas:

### 1. User & Functional Guides
- **[Features](features.md)**: A complete, granular breakdown of every functional capability in Companion4SoloPlayer, organized by subsystem (Character Tracking, Combat Resolution, Dice Rolling, Quest Management, Procedural Dungeon Generation, Plugin System, and UI).

### 2. Application Entry Points (`companion4soloplayer`)
- **[Package Root](companion4soloplayer/companion4soloplayer.md)**: Overview of the root package, metadata, build information, and version stamping.
- **[Main Entry Point](companion4soloplayer/main.md)**: Application bootstrap, Qt application initialization, and CLI argument handling.

### 3. Core Engine (`core`)
The `core` package contains pure-Python game mechanics, completely independent of any UI framework:

- **[Character Tracker](companion4soloplayer/core/character_tracker.md)**: Pydantic-based data models (`Character`) and multi-member party tracking logic (`CharacterTracker`).
- **[Combat Resolver](companion4soloplayer/core/combat_resolver.md)**: Attack calculations, strength modifiers, armor mitigation, and automated health updates (`CombatResolver`).
- **[Dice Roller](companion4soloplayer/core/dice_roller.md)**: Polyhedral dice rolling engine (`DiceRoller`), supporting single dice, multi-dice pools, and static modifiers.
- **[Dice Expression](companion4soloplayer/core/dice_expression.md)**: Dice notation parsing and evaluation value (`DiceExpression`) shared by rule elements and plugins (`2d6`, `1d20+3`, `d6-1`, ...).
- **[Game Plugin](companion4soloplayer/core/interface/game_plugin.md)**: The abstract `GamePlugin` contract implemented by every plugin (structural protocol shared by the engine and the plugins).
- **[Procedural Generator](companion4soloplayer/core/procedural_generator.md)**: Seeded random generation for dungeon layouts, room dimensions, corridors, intersections, and level-scaled difficulty (`ProceduralGenerator`).
- **[Quest Manager](companion4soloplayer/core/quest_manager.md)**: Quest definition, multi-step objective tracking, completion states, and reward distribution (`QuestManager`, `Quest`, `Objective`, `QuestStatus`).
- **[Oracle Rule](companion4soloplayer/core/rules/oracle_rule.md)**: Shared yes/no oracle rule element (`OracleRule`) used by every plugin through an absolute `!pyclass` reference.

### 4. Game Plugins (`plugins`)
Companion4SoloPlayer includes built-in game plugins demonstrating how game-specific rules, classes, monsters, and items plug into the core engine:

- **[Demo Plugin](companion4soloplayer/plugins/demo_plugin/plugin.md)**: Generic game system demo plugin integration.

### 5. User Interface (`ui`)
Desktop front-end built on **PySide6 (Qt for Python)**:

- **[Main Window](companion4soloplayer/ui/main_window.md)**: Multi-tab desktop application interface (Characters, Quests, Dungeon, Plugins), menu bars, and status updates.
- **Dialogs**:
	- **[About Dialog](companion4soloplayer/ui/dialogs/about_dialog.md)**: Application branding, version information, compilation timestamp, and legal notices.
	- **[Settings Dialog](companion4soloplayer/ui/dialogs/settings_dialog.md)**: Preferences for UI themes (Light/Dark/System), font sizing, auto-save, sound effects, and animations.
	- **[Quest Wizard](companion4soloplayer/ui/dialogs/quest_wizard.md)**: Interactive modal dialog guiding users through creating customized quests with room counts and difficulty levels.

### 6. Shared Utilities (`utils`)
Framework-agnostic helpers shared by every layer of the application:

- **[Config Manager](companion4soloplayer/utils/config_manager.md)**: TOML user configuration (`config.toml`) creation, loading, live access, and persistence.
- **[Logger](companion4soloplayer/utils/logger.md)**: Centralized logging setup driven by the `[logging]` configuration table.
- **[Plugin Loader](companion4soloplayer/utils/plugin_loader.md)**: Dynamic plugin discovery, compiled extension loading (`.pyd`), and fallback source loading.
- **[Resource Manager](companion4soloplayer/utils/resource_manager.md)**: Centralized access to shared assets (icons, fonts, sounds).
- **[YAML Loader](companion4soloplayer/utils/yaml_loader.md)**: Hardened `yaml.SafeLoader` subclass with the custom tags (`!pyclass`, `!dice`) used to read plugin and rule data files safely.

---

## Building and Browsing the Documentation Locally

The documentation is authored in Markdown and rendered using **MkDocs** with the **Material for MkDocs** theme and **mkdocstrings**.

### Local Live-Reload Server

To preview the documentation locally with automatic hot-reloading upon file edits:

```bash
nox -s docs-live
```

Once started, open [http://127.0.0.1:8001](http://127.0.0.1:8001) in your browser.

### Building Static Documentation

To build the static HTML site (output to the `site/` directory):

```bash
nox -s docs
```

The static site can be inspected locally or hosted on any static web hosting platform (such as GitHub Pages).

---

## Conventions & Documentation Standards

- **Google-Style Docstrings**: All Python modules, classes, and methods use Google-style docstring conventions. Type annotations are directly extracted from Python type hints.
- **Cross-Referencing**: Hyperlinks between symbols and modules are resolved automatically by `mkdocstrings`.
- **Legal Compliance**: Technical documentation adheres strictly to project guidelines (no copyrighted text, trademarked terms used strictly under nominative fair use or rewritten using generic equivalents).

