"""Loot rule element (random draw from the item catalog in items.yaml)."""

from __future__ import annotations

import random

from ..data import load_data


class LootRule:
    """Random loot drawn from the item catalog (items.yaml)."""

    def __init__(self, *, catalog: str = "items.yaml", rolls: int = 1) -> None:
        """Initialize the rule.

        Args:
            catalog: YAML file holding the item catalog.
            rolls: Number of items drawn by a default loot action.
        """
        self.catalog = catalog
        self.rolls = rolls

    def roll(self, count: int | None = None) -> list[dict]:
        """Draw random loot entries from the catalog.

        Args:
            count: Number of draws; defaults to the ``rolls`` parameter.

        Returns:
            The drawn item records.
        """
        items = list(load_data(self.catalog))
        draws = self.rolls if count is None else count
        if not items or draws <= 0:
            return []
        return [random.choice(items) for _ in range(draws)]
