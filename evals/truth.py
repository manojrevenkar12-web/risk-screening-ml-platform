"""What a relevance model really does, per language and source, measured on documents the product never saw.
Only evals/ may do this."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from screening.models.relevance import RelevanceModel
from world.generate import World


@dataclass
class TrueRates:
    recall: float          # share of real incidents the model passes on
    harmless_pass: float   # share of harmless documents it passes on


_cache: dict[tuple[int, str, str, str, float], TrueRates] = {}


def rates(world: World, model: RelevanceModel, lang: str, source: str = "regular", n_rel: int = 400,
          n_neg: int = 1200) -> TrueRates:
    th = model.threshold(lang)
    key = (world.seed, model.version, lang, source, th)
    if key not in _cache:
        rel = world.relevant_sample(lang, n_rel, source)
        neg = [d for d in world.truth_sample(lang, n_neg, source, tag="truth_neg") if not d.relevant]
        r = float(np.mean(model.scores([d.text for d in rel]) >= th))
        f = float(np.mean(model.scores([d.text for d in neg]) >= th)) if neg else 0.0
        _cache[key] = TrueRates(r, f)
    return _cache[key]
