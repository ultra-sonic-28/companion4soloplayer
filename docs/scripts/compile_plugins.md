# Plugin Compilation

This page describes how Companion4SoloPlayer compiles game plugins into
extension modules (`.pyd`) using Nuitka and the Zig compiler.

## Overview

Each plugin package under `src/companion4soloplayer/plugins` is compiled
with Nuitka (module mode) into a standalone extension library. The C
compilation backend is the Zig compiler shipped in `.bintools/`.

```
demo_plugin           ->  build/plugins/demo.pyd
```

**Toolchain:** Python → Nuitka (`--module --zig`) → `zig cc` (clang).

## Process Flow

The script `scripts/compile_plugins.py` orchestrates the entire build.
Plugins are recompiled only when needed: if any source file (`__init__.py`
or data file) is newer than the compiled `.pyd`, the plugin is rebuilt;
otherwise the existing library is kept. Pass `--force` to rebuild every
plugin regardless of timestamps.

```mermaid
flowchart TD
    classDef startEnd fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,color:#000
    classDef process fill:#e1f5fe,stroke:#01579b,stroke-width:1px,color:#000
    classDef decision fill:#fff3e0,stroke:#e65100,stroke-width:1px,color:#000
    classDef tool fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#000
    classDef file fill:#fce4ec,stroke:#880e4f,stroke-width:1px,color:#000

    Start([Start: python scripts/compile_plugins.py]):::startEnd
    Start --> ParseArgs[Parse arguments
--output-dir, --force]:::process
    ParseArgs --> Discover[Discover plugins
in src/.../plugins/*_plugin/]:::process

    Discover --> Loop{For each
plugin package}:::decision

    Loop --> CheckForce{--force flag
used?}:::decision
    CheckForce -- Yes --> PrepareBuild
    CheckForce -- No --> CheckTimestamps{Recompilation needed?
.pyd missing or
source is newer}:::decision

    CheckTimestamps -- No --> SkipCompile[Skip compilation
Refresh data files only]:::process
    CheckTimestamps -- Yes --> PrepareBuild

    subgraph Build [Compilation Phase]
        direction TB
        PrepareBuild[Create temp dir
Mirror package as name
strip _plugin suffix]:::process
        PrepareBuild --> SetupEnv[Setup environment
PATH += .bintools/zig
PYTHONPATH += temp
NUITKA_CACHE_DIR = temp]:::process
        SetupEnv --> RunNuitka[Run Nuitka
python -m nuitka --module --zig]:::tool
        RunNuitka --> ZigCC[Nuitka calls zig cc
Compile C backend]:::tool
        ZigCC --> GenPyd[Generates name.cp3xx.pyd]:::file
        GenPyd --> CopyPyd[Copy .pyd to
output_dir/name.pyd]:::file
    end

    SkipCompile --> CopyData
    CopyPyd --> CopyData[Copy .json and .md to
output_dir/name/]:::file

    CopyData --> Next{More plugins?}:::decision
    Next -- Yes --> Loop
    Next -- No --> Summary[Print summary
Plugins compiled / skipped]:::process
    Summary --> End([End of script]):::startEnd
```

## Compilation Toolchain

The following sequence diagram details how the script interacts with the
file system, Nuitka, and the Zig compiler during the actual compilation
of a single plugin.

```mermaid
sequenceDiagram
    participant Script as compile_plugins.py
    participant FS as File System
    participant Nuitka as Nuitka
    participant Zig as Zig (zig cc)

    Script->>FS: Read src/.../plugin/__init__.py and .json
    Script->>FS: Check timestamps (.pyd vs sources)

    alt Recompilation needed
        Script->>FS: Create temp dir, copy __init__.py as <name>
        Note over Script,FS: The '_plugin' suffix is stripped<br/>(e.g. demo_plugin → demo)

        Script->>Nuitka: Run `nuitka --module --zig <name>`
        Note over Script,Nuitka: PATH includes .bintools/zig<br/>PYTHONUTF8=1

        Nuitka->>Zig: Invoke `zig cc` to compile C
        Zig-->>Nuitka: Returns compiled object / .pyd

        Nuitka-->>Script: Success, .pyd generated in temp/out
        Script->>FS: Copy .pyd to build/plugins/<name>.pyd
    else Up to date
        Script->>FS: Skip compilation
    end

    Script->>FS: Copy .yaml/.md to build/plugins/<name>/
    Note over Script,FS: Data files are always synced<br/>even if the .pyd is not recompiled.
```

## Output Layout

The YAML data files of each plugin are copied into
`build/plugins/<plugin_name>/` next to the compiled library, so the
released application layout is:

```
internal/plugins/
    demo.pyd
    demo/
        plugin.yaml, classes.yaml, ...
        ...
```

## Usage

```bash
python scripts/compile_plugins.py [--output-dir build/plugins] [--force]
```

| Argument | Default | Description |
|---|---|---|
| `--output-dir` | `build/plugins` | Directory receiving the compiled plugins |
| `--force` | *(off)* | Recompile every plugin, ignoring timestamps |

## API Reference

::: compile_plugins
