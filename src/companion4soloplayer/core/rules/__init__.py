"""Shared rule elements available to every game plugin.

This package hosts rule element classes that are identical across
plugins (the game masters of the solo catalog share a common rule
book). Plugin-specific rule elements stay inside their own plugin
package under ``<plugin>/rules/``.

Rule elements declared in a plugin ``rules.yaml`` can reference the
classes of this package with an absolute ``!pyclass`` reference (for
example ``companion4soloplayer.core.rules:OracleRule``); the core rule
engine resolves them through its module allow-list.
"""

from companion4soloplayer.core.rules.oracle_rule import OracleRule

__all__ = ["OracleRule"]
