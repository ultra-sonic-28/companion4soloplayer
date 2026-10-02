# Companion4SoloPlayer (C4SP)

Open-source companion application for dungeon crawler style board games.

## Description

**Companion4SoloPlayer** is a free, non-profit tool designed to make it easy to manage dungeon crawler style board game sessions. The application is modular and can support several games through a plugin system.

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
- Modern and responsive user interface

## Installation

### Prerequisites

- Python 3.13 or higher
- Windows 10/11

### Installation from sources

Open a terminal and run the following commands:

    # Clone the repository
    git clone https://github.com/your-username/companion4soloplayer.git
    cd companion4soloplayer

    # Create a virtual environment
    python -m venv .venv
    .venv\Scripts\activate

    # Install development dependencies
    nox -s setup-dev

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
    ├── src/companion4soloplayer/   # Python sources (importable package)
    │   ├── main.py
    │   ├── core/       # Generic engine
    │   ├── plugins/    # Game plugins
    │   └── ui/         # User interface
    ├── assets/         # Assets (CC0)
    ├── tests/          # Unit tests
    └── docs/           # Documentation

### Tests

    # Run tests
    pytest

    # With coverage (terminal + HTML report generated in htmlcov/)
    pytest --cov=companion4soloplayer.core --cov=companion4soloplayer.plugins

    # Open the HTML coverage report
    start htmlcov/index.html

## Contributing

Contributions are welcome! Please see the development guide in [CONTEXT.md](CONTEXT.md).

## License

This project is licensed under the MIT license. See the [LICENSE](LICENSE) file for more details.

## Resources

- [Legal documentation](docs/legal_guidelines.md)
- [Plugin development guide](docs/plugin_development.md)
- [User guide](docs/user_guide.md)

---

**Last updated**: 2026-09-11
