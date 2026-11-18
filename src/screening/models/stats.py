"""Intervals for rates measured on small golden sets."""

from __future__ import annotations

import math


def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float, float]:
    if n <= 0:
        return (float("nan"), 0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))
