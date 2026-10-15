# Companion4SoloPlayer (C4SP)

Open-source companion application for dungeon crawler style board games and solo/co-op tabletop role-playing games (TTRPGs).

## Description

**Companion4SoloPlayer (C4SP)** is a modular, open-source desktop companion application designed for tabletop dungeon crawler board games and solo/co-op tabletop role-playing games (TTRPGs). It assists players and Game Masters alike by automating tedious bookkeeping, generating dynamic dungeon scenarios, rolling dice, tracking quest progression, resolving combat encounters, and supporting multiple game systems through a clean plugin architecture.

## Legal Disclaimer

**Companion4SoloPlayer** is an independent, free, non-profit, open-source tool designed to make it easy to manage dungeon crawler style board game sessions.

This application is **neither affiliated with, nor endorsed by, nor sponsored by** Hasbro, Games Workshop, Ganesha Games, DR Games, BlackOath Entertainment, Nuts! Publishing, or any other rights holder related to the supported games.

All trademarks mentioned are the property of their respective owners.

This application does not reproduce any text, artwork, logo, or copyrighted element belonging to the official publishers. The implemented game mechanics are generic tabletop and role-playing game concepts that are not protectable by copyright.

Community plugins are used with the explicit permission of their respective authors or contain only rewritten generic terms.

All visual assets are either created specifically for this project or distributed under CC0 license (public domain) or compatible free licenses.

## Features

- Full character management (stats, HP, inventory)
- Dice rolling system (d6, d10, d100, custom dice)
- Procedural dungeon generation
- Combat resolution
- Quest and objective tracking
- Multi-game support via plugins
- Modern user interface with material-like stylesheets

## Installation

### Prerequisites

- Python 3.13 or higher
- Windows 10/11

### Installation from sources

Open a terminal and run the following commands:

    # Clone the repository
    git clone https://github.com/your-username/companion4soloplayer.git
    cd companion4soloplayer

    # Create a virtual environment and install development dependencies
    nox -s setup-dev

    # Activate virtual environnement for coding and tooling support in editors
    .venv\Scripts\activate


    # Start coding
    # using your favorite code editor

    # Run the application
    c4sp

### Windows Build

    # Install the build dependencies (PyInstaller)
    # Build the executable, the release zip and its SHA256 checksum
    nox -s release

The build script:
- increments the build counter stored in pyproject.toml
  ([tool.companion4soloplayer] build = N),
- stamps it into src/companion4soloplayer/build_info.py,
- runs PyInstaller on companion4soloplayer.spec,
- packages dist/companion4soloplayer/ (a minimal companion4soloplayer.exe
  plus its _internal/ runtime folder) into a release archive
  (zip + SHA256 checksum) in dist/.

## Usage

1. Launch the application
2. Select a game plugin from the menu
3. Create your characters
4. Generate a dungeon or load a quest
5. Play!

## Development

See the [CONTEXT.md](CONTEXT.md) file for the complete development guide.

### Project structure

    companion4soloplayer/
    ├── src/companion4soloplayer/                # Python sources (importable package)
    │   ├── main.py                              # Main entry point for Companion4SoloPlayer
    │   ├── app/                                 # Qt application
    │   ├── core/                                # Generic engine
    │   │   ├── interface/                       # Generic game interfaces
    │   │   ├── creation/                        # Character creation engine
    │   │   │   └── steps/                       # Generic creation steps
    │   │   └── rules/                           # Shared rule elements
    │   ├── plugins/                             # Game-specific modules
    │   │   └── demo_plugin/                     # Demo plugin
    │   │       ├── rules/                       # Plugin specific rules
    │   │       ├── creation/                    # Character creation (game system side)
    │   │       └── datas/                       # Plugin specific datas
    │   ├── utils/                               # Shared helpers
    │   └── ui/                                  # User interface
    │       ├── builder/                         # Dynamic player creation dialog
    │       └── dialogs/                         # Dialog windows
    ├── companion4soloplayer.spec                # PyInstaller build recipe
    ├── companion4soloplayer.code-workspace      # VS Code workspace file
    ├── pyproject.toml                           # Project configuration
    ├── README.md                                # Main README with disclaimer
    ├── CONTEXT.md                               # Complete development guide
    ├── LICENSE                                  # MIT license
    ├── .gitignore                               # Git ignore
    ├── .vscode/                                 # Visual Studio Code workspace settings
    ├── assets/                                  # Shared assets (CC0 only)
    ├── data/                                    # User data
    │   └── config/                              # config.toml (window, logging, appearance)
    ├── tests/                                   # Tests folders
    |   ├── test_core/                           # Core unit tests
    |   ├── test_ui/                             # Core UI tests
    │   ├── tests_utils/                         # Utils tests (config, logger, plugin loader, resources, yaml)
    |   └── test_plugins/                        # Plugins tests
    ├── docs/                                    # Technical documentation
    ├── scripts/                                 # Project scripts
    ├── build/                                   # Build folder, PyInstaller output (generated)
    └── dist/                                    # Release folder, PyInstaller output (generated)

### Tests

    # Run tests
    nox -s tests-unit
    nox -s tests-ui

    # Open the HTML coverage report
    # Or open 'htmlcov/index.html' with your favorite browser
    start htmlcov/index.html

## Contributing

Contributions are welcome! Please see the development guide in [CONTEXT.md](CONTEXT.md).

## License

This project is licensed under the MIT license. See the [LICENSE](LICENSE) file for more details.

---

**Last updated**: 2026-10-15
