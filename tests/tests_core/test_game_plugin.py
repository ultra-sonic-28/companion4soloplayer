"""Unit tests for the generic ``GamePlugin`` interface (core contract)."""

from typing import get_protocol_members

from companion4soloplayer.core.interface import GamePlugin, game_plugin


def test_gameplugin_is_declared_in_the_interface_package() -> None:
    """The contract lives in ``companion4soloplayer.core.interface``."""
    assert game_plugin.GamePlugin is GamePlugin


def test_gameplugin_is_a_protocol() -> None:
    """GamePlugin is a structural contract, not a base class to inherit.

    ``issubclass(..., Protocol)`` is avoided on purpose: mypy types the
    ``Protocol`` import as a special form while ``issubclass`` expects a
    ``_ClassInfo``. ``_is_protocol`` is the flag CPython sets on every
    class derived from ``typing.Protocol`` (``typing.get_protocol_members``
    in the test below also raises ``TypeError`` on a non-protocol).
    """
    assert getattr(GamePlugin, "_is_protocol", False) is True


def test_gameplugin_declares_the_documented_api() -> None:
    """The protocol surface is exactly the documented plugin contract."""
    assert get_protocol_members(GamePlugin) == {
        "name",
        "version",
        "description",
        "get_classes",
        "get_monsters",
        "get_items",
        "get_rules",
        "generate_dungeon",
        "get_rule_engine",
        "create_component",
        "create_character_creation",
    }
