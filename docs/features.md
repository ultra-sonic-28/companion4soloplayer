# Features

**Companion4SoloPlayer (C4SP)** is a modular, open-source desktop companion application designed for tabletop dungeon crawler board games and solo/co-op tabletop role-playing games (TTRPGs). It assists players and Game Masters alike by automating tedious bookkeeping, generating dynamic dungeon scenarios, rolling dice, tracking quest progression, resolving combat encounters, and supporting multiple game systems through a clean plugin architecture.

This document details every feature provided by Companion4SoloPlayer, organized by subsystem.

---

## Table of Contents

- [Overview and Key Strengths](#overview-and-key-strengths)
- [Character Management](#character-management)
  - [Character Data Model](#character-data-model)
  - [Party Tracking and Multi-Character Support](#party-tracking-and-multi-character-support)
  - [Hit Points and Status Management](#hit-points-and-status-management)
  - [Inventory and Equipment](#inventory-and-equipment)
  - [Customizable Statistics](#customizable-statistics)
- [Combat Resolution System](#combat-resolution-system)
  - [Damage Calculation Engine](#damage-calculation-engine)
  - [Damage Application and Health Modification](#damage-application-and-health-modification)
  - [Turn and Encounter Assistance](#turn-and-encounter-assistance)
- [Dice Rolling Engine](#dice-rolling-engine)
  - [Standard Polyhedral and Custom Sided Dice](#standard-polyhedral-and-custom-sided-dice)
  - [Multi-Dice Rolls](#multi-dice-rolls)
  - [Static Modifiers and Calculated Totals](#static-modifiers-and-calculated-totals)
  - [Cryptographic and Pseudo-Random Generation](#cryptographic-and-pseudo-random-generation)
- [Quest and Objective Tracking](#quest-and-objective-tracking)
  - [Quest Lifecycle and Status States](#quest-lifecycle-and-status-states)
  - [Granular Objectives](#granular-objectives)
  - [Active Quest Management](#active-quest-management)
  - [Quest Creation Wizard](#quest-creation-wizard)
  - [Scenario Rewards](#scenario-rewards)
- [Procedural Dungeon Generation](#procedural-dungeon-generation)
  - [Randomized Architecture](#randomized-architecture)
  - [Room Types and Geometric Variety](#room-types-and-geometric-variety)
  - [Level-Scaled Difficulty Modifiers](#level-scaled-difficulty-modifiers)
  - [Seeded Generation for Reproducibility](#seeded-generation-for-reproducibility)
- [Plugin Architecture and Multi-Game Systems](#plugin-architecture-and-multi-game-systems)
  - [Dynamic Plugin Discovery and Loading](#dynamic-plugin-discovery-and-loading)
  - [Compiled C-Extension (.pyd) Support](#compiled-c-extension-pyd-support)
  - [Standardized GamePlugin Contract](#standardized-gameplugin-contract)
  - [Built-In Plugins](#built-in-plugins)
    - [Demo Plugin](#demo-plugin)
  - [Legal Protection and Clean-Room Decoupling](#legal-protection-and-clean-room-decoupling)
- [User Interface (PySide6 and Qt)](#user-interface-pyside6-and-qt)
  - [Multi-Tab Desktop Experience](#multi-tab-desktop-experience)
  - [Interactive Character Panel](#interactive-character-panel)
  - [Quest and Adventure Tracker Panel](#quest-and-adventure-tracker-panel)
  - [Dungeon Exploration and Generation Panel](#dungeon-exploration-and-generation-panel)
  - [Plugin Manager Panel](#plugin-manager-panel)
  - [Settings Dialog](#settings-dialog)
  - [About and Licensing Dialog](#about-and-licensing-dialog)
- [Build, Packaging and Standalone Distribution](#build-packaging-and-standalone-distribution)

---

## Overview and Key Strengths

Companion4SoloPlayer provides a unified, distraction-free companion experience at the table. Rather than replacing the tactile joy of miniature movement and physical tokens, C4SP removes administrative friction:

1. **System Agnostic Core**: Core mechanics (dice, health, basic combat math, procedural layouts, quests) operate independently of any specific rulebook.
2. **Pluggable Game Rules**: Game-specific items, monsters, special abilities, and room tables are loaded dynamically via plugins.
3. **Pure Desktop Independence**: No cloud account, no telemetry, no mandatory internet connection. Everything runs locally on Windows.
4. **Fast and Lightweight**: Implemented with Python 3.13 and PySide6, packaged into an optimized standalone binary via PyInstaller or Nuitka.

---

## Character Management

The character management system is driven by `companion4soloplayer.core.character_tracker`, providing strict validation and state handling via Pydantic models.

### Character Data Model
Each character is represented as a strongly-typed `Character` record comprising:

- **Identity**: Character `name` (unique identifier within party) and `character_class` (e.g., Barbarian, Wizard, Dwarf, Cleric).
- **Vitality**: `max_hp` (derived or configured maximum health points) and `current_hp` (real-time health during an encounter).
- **Statistics Block**: A flexible dictionary mapping arbitrary stat identifiers to integer values (e.g., `body`, `mind`, `strength`, `defense`, `speed`).
- **Inventory**: A list of items, consumables, treasure tokens, and gear currently held in the hero's backpack.
- **Equipment**: Equipped weapons, armor, shields, and rings actively modifying attributes or usable in combat.

### Party Tracking and Multi-Character Support
The `CharacterTracker` engine coordinates party management:

- **Party Registry**: Store and manipulate multiple active adventurers simultaneously.
- **Creation Factory**: `create_character(name, character_class, stats)` validates uniqueness and computes initial maximum health based on system conventions (e.g., defaulting to the `body` stat or standard baseline).
- **Instant Retrieval**: Quick lookup by name (`get_character(name)`) for combat, inventory, or UI updates.
- **Party Maintenance**: Safe character removal (`remove_character(name)`) when characters retire or perish.

### Hit Points and Status Management
- Automatic clamping: Current hit points cannot drop below zero or exceed the character's maximum health pool.
- Visual feedback: In-app health displays and color-coded status indicators in the user interface.

### Inventory and Equipment
- Equipment slots can be adjusted during town or camp phases.
- Real-time inventory tracking for loot collected during dungeon runs (gold sacks, gems, potions, quest artifacts).

### Customizable Statistics
- Supports differing attribute systems across board games:
	- *Classic dungeon crawlers*: Body points, Mind points, Attack dice, Defend dice.
	- *Pen-and-paper crawlers*: Level, Life points, Attack bonus, Defense bonus, Gold.
	- *Cartographic games*: Agility, Brawn, Awareness, Discipline, Hit points.

---

## Combat Resolution System

The combat engine is implemented in `companion4soloplayer.core.combat_resolver` via `CombatResolver`, orchestrating encounters between players and adversaries.

### Damage Calculation Engine
- **`calculate_damage(attacker, defender, weapon_damage)`**:
	- Extracts the attacker's offensive modifiers (e.g., `strength` attribute or attack bonus).
	- Calculates base output: `base_damage = weapon_damage + attacker_strength`.
	- Determines defender mitigation based on active defense (e.g., `armor`, shield, or defense stat).
	- Yields final net damage: `max(0, base_damage - defense)`.
	- Guarantees non-negative damage values to prevent inadvertent healing from defense over-matching.

### Damage Application and Health Modification
- **`apply_damage(character, damage)`**:
	- Deducts the computed damage amount directly from the target character's `current_hp`.
	- Automatically bounds the remaining hit points at a minimum of `0`.
	- Returns the post-damage remaining HP, triggering UI death/downed alerts if vitality reaches zero.

### Turn and Encounter Assistance
- Provides automated arithmetic so players can resolve complex attack vs. defense rolls without manual table consultations.
- Easily customizable by plugins to incorporate system-specific mechanics (such as exploding dice or armor-piercing strikes).

---

## Dice Rolling Engine

The dice subsystem in `companion4soloplayer.core.dice_roller` handles all randomized dice requirements.

### Standard Polyhedral and Custom Sided Dice
- **Arbitrary Sides**: Simulates any polyhedral die size: d4, d6, d8, d10, d12, d20, d100, or any arbitrary custom integer value `sides >= 1`.
- Input validation safeguards against invalid parameters (e.g., 0-sided or negative dice counts).

### Multi-Dice Rolls
- **`roll_dice(count, sides)`**: Rolls an arbitrary number of dice (`count >= 1`) and returns the complete list of individual die rolls.
- Preserves individual dice values for game rules that require checking matching pairs, critical successes, or individual dice thresholds (such as skull/shield combat dice).

### Static Modifiers and Calculated Totals
- **`roll_with_modifier(count, sides, modifier)`**:
	- Rolls `count` dice of `sides`.
	- Returns a tuple `(results, total)` containing both the individual roll list and the total including positive or negative modifiers.
- **`roll_single(sides)`**: Convenience method for quick single-die checks, saving throws, or wandering monster tables.

### Cryptographic and Pseudo-Random Generation
- Uses Python's uniform random generation distribution (`random.randint`), guaranteeing statistically unbiased roll spreads across thousands of iterations.

---

## Quest and Objective Tracking

Implemented in `companion4soloplayer.core.quest_manager`, the quest manager tracks campaign arcs, scenario conditions, and mission progression.

### Quest Lifecycle and Status States
Each scenario is monitored through explicit states defined in `QuestStatus`:

- `NOT_STARTED`: The quest is planned or loaded, but party has not entered the dungeon.
- `IN_PROGRESS`: The heroes are actively pursuing objectives within the dungeon.
- `COMPLETED`: All primary objectives have been successfully fulfilled.
- `FAILED`: Failure conditions have been met (e.g., party wipe or turn counter expired).

### Granular Objectives
- Quests contain multiple structured `Objective` objects.
- Each objective tracks its description and a boolean `completed` state.
- **`complete_objective(quest_name, objective_index)`**:
	- Marks an objective completed.
	- Automatically inspects the remaining objectives: when the final objective is fulfilled, the quest status automatically transitions to `COMPLETED`.

### Active Quest Management
- **`start_quest(name)`**: Marks the specified quest as `IN_PROGRESS` and sets it as the currently active scenario in the companion context.
- **`get_active_quest()`**: Fast reference to the current scenario for UI status bars and quick lookups.

### Quest Creation Wizard
- User interface modal (`QuestWizard`) allowing players to quickly design adventures:
	- Scenario Title and Story Description.
	- Quest Template selection (e.g., "Dungeon Crawl", "Rescue", "Assassination", "Artifact Retrieval").
	- Target dungeon room count.
	- Difficulty rating (1–10).

### Scenario Rewards
- Quests support reward dictionaries (e.g., gold bounties, bonus experience, artifact codes) automatically granted upon completion.

---

## Procedural Dungeon Generation

The procedural layout engine (`companion4soloplayer.core.procedural_generator`) creates dynamic, non-repetitive dungeon layouts for solo exploration or randomized Game Master sessions.

### Randomized Architecture
- **`generate_dungeon(num_rooms, level)`**: Generates an ordered series of connected architectural spaces tailored to the target party experience level.
- Assigns sequential unique IDs, room classifications, and atmospheric flavor text.

### Room Types and Geometric Variety
- Supports distinct architectural categories generated via `generate_room(room_type, level)`:
	- **Corridors**: Narrow passages with varying lengths and widths (e.g., 1x5, 1x8, 2x6).
	- **Chambers / Rooms**: Square and rectangular combat spaces (4x4 small chambers, 5x5 medium halls, 6x8 grand halls).
	- **Intersections**: 3x3 crossroads and 4x4 four-way junctions creating branching path choices.
	- **Stairs**: Passages leading downward to deeper dungeon tiers.

### Level-Scaled Difficulty Modifiers
- Generates a difficulty coefficient scaled by dungeon tier: `difficulty = level / 10`.
- Enables plugins and combat engines to adjust trap hazards, monster spawns, and chest quality based on procedural room depth.

### Seeded Generation for Reproducibility
- Accepts an optional `seed` parameter upon initialization: `ProceduralGenerator(seed=12345)`.
- Guarantees identical dungeon layouts across sessions, enabling tournament play, shared seeds among community players, and bug-free save states.

---

## Plugin Architecture and Multi-Game Systems

The modular core uses `companion4soloplayer.core.plugin_loader` to support different board game systems without touching the core codebase.

### Dynamic Plugin Discovery and Loading
- Scans user directories, application directories, and built-in folders for compatible game extensions.
- Transparently discovers plugins packaged as either source packages or compiled libraries.

### Compiled C-Extension (.pyd) Support
- Fully compatible with compiled C-extensions (`.pyd`) generated by **Nuitka**.
- High performance, protected distribution, and instant loading via `importlib.machinery.ExtensionFileLoader`.
- Graceful development fallback: loads standard Python source packages (`*_plugin`) when running in development environments.

### Standardized GamePlugin Contract
Every plugin adheres to the abstract `GamePlugin` interface:

- **`name` / `version` / `description`**: Metadata properties describing the game system.
- **`get_classes()`**: Returns character classes available in the game, including starting attributes, starting equipment, and archetype traits.
- **`get_monsters()`**: Returns bestiary data (monster statistics, attack dice, body points, special rules).
- **`get_items()`**: Returns armory and equipment catalogs (weapons, armor, tools, prices, modifiers).
- **`get_rules()`**: Structured rulebook summaries, action limits, movement rules, and turn flow.
- **`generate_dungeon(config)`**: Custom dungeon layout and table-rolling logic customized for the specific game system.

### Built-In Plugins
Companion4SoloPlayer includes one example plugin:

#### Demo Plugin
- Illustrates the plugin architecture with a simple generic game system implementation.

### Legal Protection and Clean-Room Decoupling
- Strictly enforces clean-room design and legal safety:
	- No copyrighted rulebook verbatim texts or protected artwork.
	- No trademarked proper nouns; generic terms and nominative fair use compatibility indicators only.
	- System-specific plugins isolate proprietary rule concepts from the MIT-licensed core codebase.

---

## User Interface (PySide6 and Qt)

Companion4SoloPlayer features a desktop user interface built with **PySide6** (`src/companion4soloplayer/ui/`).

### Multi-Tab Desktop Experience
The `MainWindow` centralizes session management across three intuitive functional tabs:

1. **Characters Tab**: Inspect the active adventuring party, view current health gauges, review inventories, and create or recruit new characters.
2. **Quests Tab**: Browse active objectives, track completion milestones, and initiate new adventures.
3. **Dungeon Tab**: Procedurally roll and visualize new rooms, track corridors, and manage dungeon levels.

### Interactive Character Panel
- Live hit point modification buttons (+ / - damage).
- Form inputs for creating new characters on the fly.
- Real-time updates synchronized across all UI views.

### Quest and Adventure Tracker Panel
- Interactive objective checklists where players click to complete steps.
- Visual completion badges when a scenario objective concludes.
- Direct invocation of the **Quest Creation Wizard**.

### Dungeon Exploration and Generation Panel
- One-click procedural generation of rooms, corridors, and stairs.
- Real-time display of dimensions, descriptions, and danger ratings.

### Plugin Manager Panel
- The `PluginsDialog`, opened from the **Manage > Plugins** menu entry, renders every discovered plugin in a scrollable multi-column table (name, description, version, license, author, compatible games, loaded status) read from its `datas/plugin.yaml` manifest.
- Loading or unloading a plugin with its row button toggles its rules and content in real-time without restarting the desktop application.

### Settings Dialog
The `SettingsDialog` lets players personalize their desktop experience:

- **Appearance**: Toggle between **Light**, **Dark**, and **System** themes; customize font size (8 pt to 24 pt) for high-DPI displays or projector usage.
- **Gameplay Options**:
	- Toggle automatic background game saves.
	- Toggle sound effect cues for dice rolls and events.
	- Toggle UI animations.

### About and Licensing Dialog
The `AboutDialog` displays:

- Application logo (128x128 high-DPI asset).
- Version number, build number and build timestamp (`BUILD_DATETIME`).
- Project description and direct link to licensing/legal documentation.

---

## Build, Packaging and Standalone Distribution

Companion4SoloPlayer is equipped with automated developer tooling for testing and standalone packaging:

- **PyInstaller Bundling**: Packages the application into a standalone Windows executable (`dist/companion4soloplayer/companion4soloplayer.exe`) with all dependencies embedded.
- **Nuitka Compilation**: Compiles the core and plugins into high-performance native machine code binaries.
- **Nox Automation**: Orchestrates setup, formatting, linting, unit tests, coverage reporting, documentation generation, and release packaging with single commands:
	- `nox -s setup-dev`: Configures a complete virtual development environment.
	- `nox -s lint`: Run QoL checks: black, ruff, mypy.
	- `nox -s test-unit`: Executes the full unit test suite with coverage thresholds.
	- `nox -s test-ui`: Executes the full ui test suite with coverage thresholds.
	- `nox -s compile-plugins`: Compile every game plugin into a .pyd extension (build/plugins/).
	- `nox -s release`: Automatically increments build numbers, builds the executable, and generates release archives with SHA-256 checksums.
	- `nox -s check-venv`: Check if a virtual environment is active.
	- `nox -s docs`: Create technical documentation, static build
	- `nox -s docs-live`: Create technical documentation, live reloading server
	- `nox -s stats`: Compute code statistics (lines of code, etc.).
