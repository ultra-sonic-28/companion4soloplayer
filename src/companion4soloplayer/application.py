"""
Application module.

Defines the ``QApplication`` subclass carrying the configuration shared by
every component of the application.
"""

from collections.abc import Iterable

from PySide6.QtWidgets import QApplication

from companion4soloplayer.utils.config_manager import ConfigManager


class CompanionApplication(QApplication):
    """QApplication subclass holding the data shared across the application.

    The configuration file is read once, at startup: the resulting
    :class:`ConfigManager` is kept as a member so that any component can
    reach the same settings through :func:`application_config`, whatever
    its context.
    """

    def __init__(self, arguments: Iterable[str], config: ConfigManager | None = None) -> None:
        """Initialize the application and load its configuration.

        Args:
            arguments: Command line arguments (Qt removes its own switches).
            config: Configuration to use instead of the default one.
        """
        super().__init__(arguments)
        self.config: ConfigManager = config if config is not None else ConfigManager()


def application_config() -> ConfigManager | None:
    """Return the configuration attached to the running application.

    Returns:
        The shared configuration, or ``None`` when the application was not
        started through :class:`CompanionApplication` (e.g. in tests).
    """
    app = QApplication.instance()
    return app.config if isinstance(app, CompanionApplication) else None
