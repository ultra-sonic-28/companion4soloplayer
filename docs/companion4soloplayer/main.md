# Main entry point

`main()` bootstraps the application: it reads the configuration file,
configures the logging, builds the Qt application and the main window,
then runs the event loop until the application is closed.

## Startup and shutdown flow

The order is strict: the logger needs the configuration, and both must be
ready before the first Qt object is created. The last message is written
once `app.exec()` returns, i.e. for **every** way of leaving the
application (window closed, *File > Exit*, `app.quit()`). When logging is
disabled (`enabled = false`), that message is blocked like any other
record.

```mermaid
flowchart TD
    classDef startEnd fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,color:#000
    classDef process fill:#e1f5fe,stroke:#01579b,stroke-width:1px,color:#000
    classDef file fill:#fce4ec,stroke:#880e4f,stroke-width:1px,color:#000
    classDef qt fill:#e8f5e9,stroke:#2e7d32,stroke-width:1px,color:#000

    Start(["main()"]):::startEnd
    Start --> ReadConfig["ConfigManager()<br/>read or create data/config/config.toml"]:::file
    ReadConfig --> SetupLogging["setup_logging(config)<br/>apply the [logging] table"]:::process
    SetupLogging --> CreateApp["CompanionApplication(sys.argv, config=config)<br/>same configuration instance, shared app-wide"]:::qt
    CreateApp --> Splash["SplashScreen(duration_ms).show()<br/>app.processEvents()"]:::qt
    Splash --> AppMeta["setApplicationName(...)<br/>setApplicationVersion(__version__)"]:::process
    AppMeta --> CreateWindow["MainWindow()<br/>restores geometry and maximized state"]:::qt
    CreateWindow --> Timer["QTimer.singleShot(SPLASH_DURATION_MS, window.show)"]:::process
    Timer --> EventLoop["app.exec()<br/>Qt event loop"]:::qt
    EventLoop --> ExitLog["logger.info('Application exiting with code n')<br/>last message of the session"]:::process
    ExitLog --> SysExit(["sys.exit(exit_code)"]):::startEnd
```

## Sequence diagram

The same flow seen as interactions between the modules: the configuration
is read first, the logging is configured from it, then the Qt objects are
created and the event loop takes over until the exit message is written.

```mermaid
sequenceDiagram
    participant M as main()
    participant C as ConfigManager
    participant L as logger (utils/logger.py)
    participant A as CompanionApplication
    participant S as SplashScreen
    participant W as MainWindow
    participant Q as Qt event loop

    M->>C: ConfigManager()
    C-->>M: data/config/config.toml (read or created)

    M->>L: setup_logging(config)
    L-->>M: file + console handlers, level from [logging]

    M->>A: CompanionApplication(sys.argv, config=config)
    A-->>A: self.config = config (read once)

    M->>S: SplashScreen.show()
    M->>A: processEvents()
    M->>A: setApplicationName(...) / setApplicationVersion(...)

    M->>W: MainWindow()
    W->>A: application_config()
    A-->>W: config
    W->>W: _restore_window_settings()

    M->>Q: QTimer.singleShot(SPLASH_DURATION_MS, window.show)
    M->>Q: app.exec()
    Q-->>M: exit code (window closed, menu Exit, app.quit())

    M->>L: logger.info('Application exiting with code n')
    M->>M: sys.exit(exit_code)
```

## API reference

::: main
    options:
      heading_level: 3
