"""Drift: a language whose score distribution or share of the daily volume moves away from its reference.

Both are measured on what the pipeline already sees (scores and counts); no labels are needed to raise the alert.
Labels come after: the alert asks analysts for an enriched batch in that language, which feeds a targeted retrain.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def histogram(scores: np.ndarray, edges: list[float]) -> np.ndarray:
    """Share of scores per bin, smoothed so an empty bin does not divide by zero."""
    h, _ = np.histogram(np.clip(scores, 0, 1), bins=np.array(edges))
    return (h + 0.5) / (h.sum() + 0.5 * len(h))


def psi(reference: np.ndarray, current: np.ndarray) -> float:
    """Population stability index between two binned distributions."""
    return float(np.sum((current - reference) * np.log(current / reference)))


@dataclass
class DriftAlert:
    language: str
    day: int
    psi: float
    mix_change: float
    reason: str


def check(language: str, day: int, ref_hist: np.ndarray, cur_hist: np.ndarray, ref_share: float, cur_share: float,
          psi_alert: float, mix_alert: float) -> DriftAlert | None:
    p = psi(ref_hist, cur_hist)
    mix = abs(cur_share - ref_share) / max(ref_share, 1e-9)
    if p >= psi_alert or mix >= mix_alert:
        why = []
        if p >= psi_alert:
            why.append(f"score distribution PSI {p:.2f}")
        if mix >= mix_alert:
            why.append(f"share of volume {ref_share:.2%} -> {cur_share:.2%}")
        return DriftAlert(language, day, p, mix, " and ".join(why))
    return None
