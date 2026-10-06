"""Unit tests for the generic ``GamePlugin`` interface (core contract)."""

from typing import Protocol, get_protocol_members

from companion4soloplayer.core.interface import GamePlugin, game_plugin


def test_gameplugin_is_declared_in_the_interface_package() -> None:
    """The contract lives in ``companion4soloplayer.core.interface``."""
    assert game_plugin.GamePlugin is GamePlugin


def test_gameplugin_is_a_protocol() -> None:
    """GamePlugin is a structural contract, not a base class to inherit."""
    assert issubclass(GamePlugin, Protocol)


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
    }
