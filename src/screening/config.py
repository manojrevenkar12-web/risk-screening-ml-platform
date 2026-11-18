"""Product settings: config/platform.toml and config/gates.toml. Never the world's files."""

from __future__ import annotations

import copy
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def _settings() -> dict[str, Any]:
    with open(ROOT / "config" / "platform.toml", "rb") as f:
        return tomllib.load(f)


def settings(overrides: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """The settings with a design's overrides on top (section -> key -> value)."""
    s = copy.deepcopy(_settings())
    for section, values in (overrides or {}).items():
        s.setdefault(section, {}).update(values)
    return s


@lru_cache
def gates() -> dict[str, Any]:
    with open(ROOT / "config" / "gates.toml", "rb") as f:
        return tomllib.load(f)["gates"]
