"""Train the relevance model the platform would promote on day 0 of the dev world and export it for the image.

    python scripts/build_model.py artefacts
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from screening.config import settings  # noqa: E402
from screening.platform import Platform  # noqa: E402
from world.generate import World, load  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "artefacts")
    world = World(load("world"))
    p = Platform(world, world.shares, settings(), artefacts=out)
    vol = {k: v for k, v in world.hourly_volume(0, 12).items() if "#" not in k}
    p.day(0, vol)
    assert p.state.champion is not None
    print(p.state.champion.version)


if __name__ == "__main__":
    main()
