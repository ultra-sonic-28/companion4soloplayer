# Application class

`app/application.py` defines `CompanionApplication`, the `QApplication`
subclass carrying the `ConfigManager` shared by every component of the
application, and `application_config()`, the accessor used to reach that
configuration from anywhere.

## Shared configuration flow

The configuration is read **once**, in `main()`, and travels through the
application as a member: every component sees the same instance.
`application_config()` returns `None` outside a normal launch (tests,
stubs), so components tolerate a missing configuration: the main window
then keeps the Qt defaults and persists nothing. Tests inject their own
`ConfigManager` (temporary folder) instead of relying on the global state.

```mermaid
flowchart TD
    classDef startEnd fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,color:#000
    classDef process fill:#e1f5fe,stroke:#01579b,stroke-width:1px,color:#000
    classDef qt fill:#e8f5e9,stroke:#2e7d32,stroke-width:1px,color:#000
    classDef warn fill:#fff3e0,stroke:#e65100,stroke-width:1px,color:#000

    subgraph Creation ["Creation (main.py)"]
        direction TB
        Cfg(["ConfigManager()"]):::startEnd
        App["CompanionApplication(sys.argv,<br/>config=config)"]:::qt
        Member["self.config = config<br/>read once, kept as a member"]:::process
        Cfg -->|"config= argument"| App
        App --> Member
    end

    Member --> Access["application_config()"]:::process
    Access --> Instance{"QApplication.instance() is a<br/>CompanionApplication?"}:::process
    Instance -->|"yes (normal launch)"| Shared["app.config"]:::process
    Instance -->|"no (tests, stubs)"| NoConfig["None"]:::warn

    Shared --> WindowDefault["MainWindow()<br/>production: uses application_config()"]:::qt
    NoConfig --> WindowInjected["MainWindow(config=...)<br/>tests: explicit temporary config"]:::qt
    WindowDefault --> Restore["_restore_window_settings()<br/>geometry + maximized, off-screen guard"]:::process
    WindowInjected --> Restore
    Restore --> Save["closeEvent -> _save_window_settings()<br/>update the tables, then save()"]:::process
```

## Sequence diagram

The same mechanism over time, including the two access paths (production
and tests) and the save performed when the window is closed.

```mermaid
sequenceDiagram
    participant M as main()
    participant F as config.toml
    participant A as CompanionApplication
    participant AC as application_config()
    participant W as MainWindow

    M->>F: ConfigManager(): read or create
    F-->>M: configuration tables ([window], [logging])
    M->>A: CompanionApplication(sys.argv, config=config)
    A-->>A: self.config = config (read once)

    M->>W: MainWindow()
    W->>AC: application_config()
    AC->>A: QApplication.instance() + isinstance check
    alt CompanionApplication (normal launch)
        AC-->>W: app.config
        W->>W: _restore_window_settings()<br/>geometry + maximized, off-screen guard
    else Plain QApplication (tests, stubs)
        AC-->>W: None
        Note over W: Qt defaults, nothing persisted<br/>tests inject MainWindow(config=...)
    end

    Note over W,A: When the window is closed
    W->>W: closeEvent() -> _save_window_settings()
    W->>A: window table updated, then config.save()
    A->>F: configuration rewritten (geometry + maximized)
```

## API reference

::: app.application
    options:
      heading_level: 3
