"""Plugin manifest (``datas/plugin.yaml``) schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PluginMetadata(BaseModel):
    """Plugin manifest (``plugin.yaml``) contents."""

    name: str
    version: str
    description: str
    author: str | None = None
    license: str | None = None
    compatible_games: list[str] = Field(default_factory=list)
    disclaimer: str = ""
    features: str = ""
    dependencies: dict[str, str] = Field(default_factory=dict)
