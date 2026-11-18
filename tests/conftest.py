from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from world.generate import World, load  # noqa: E402


@pytest.fixture(scope="session")
def world() -> World:
    return World(load("world"))


@pytest.fixture(scope="session")
def short_world() -> World:
    """Three weeks with the same events packed in: the export gap on day 14, drift on day 16, a retirement on day 19."""
    cfg = copy.deepcopy(load("world"))
    cfg["days"] = 20
    cfg["drift"]["day"] = 16
    cfg["llm"]["catalog"][0]["retires_day"] = 19
    return World(cfg)
