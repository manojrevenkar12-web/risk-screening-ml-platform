"""Promotion: may a candidate relevance model replace the champion?

aggregate: compare F1 over all golden documents together (what most teams do; a regression in five small languages
disappears in the average). per_language: every language must keep its recall, judged as a paired comparison on the same
golden incidents with a correction for testing thirty languages, and a language with too few labelled incidents to
judge holds the release instead of passing it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.stats import binom

from screening.models.relevance import Labelled, RelevanceModel
from screening.models.stats import wilson


@dataclass
class LanguageReport:
    language: str
    incidents: int
    recall: tuple[float, float, float]
    fpr: tuple[float, float, float]
    threshold: float


@dataclass
class Decision:
    promote: bool
    mode: str
    reasons: list[str] = field(default_factory=list)
    candidate: dict[str, LanguageReport] = field(default_factory=dict)
    champion: dict[str, LanguageReport] = field(default_factory=dict)


def report(model: RelevanceModel, golden: dict[str, list[Labelled]]) -> dict[str, LanguageReport]:
    out = {}
    for lang, docs in golden.items():
        s = model.scores([d.text for d in docs])
        y = np.array([d.label for d in docs])
        th = model.threshold(lang)
        hit = s >= th
        out[lang] = LanguageReport(lang, int(y.sum()), wilson(int((hit & y).sum()), int(y.sum())),
                                   wilson(int((hit & ~y).sum()), int((~y).sum())), th)
    return out


def _f1(reports: dict[str, LanguageReport]) -> float:
    tp = sum(r.recall[0] * r.incidents for r in reports.values())
    fn = sum((1 - r.recall[0]) * r.incidents for r in reports.values())
    fp = sum(r.fpr[0] * 300 for r in reports.values())
    return 2 * tp / max(1e-9, 2 * tp + fn + fp)


def _sign_test(worse: int, better: int) -> float:
    """One-sided p-value that the candidate misses more incidents than the champion, from the discordant pairs."""
    n = worse + better
    if n == 0:
        return 1.0
    return float(binom.sf(worse - 1, n, 0.5))


def decide(candidate: RelevanceModel, champion: RelevanceModel | None, golden: dict[str, list[Labelled]],
           cfg: dict[str, Any], shares: dict[str, float] | None = None) -> Decision:
    g = cfg["gate"]
    cand = report(candidate, golden)
    if champion is None:
        return Decision(True, g["mode"], ["first model"], cand, {})
    champ = report(champion, golden)
    if g["mode"] == "aggregate":
        gain = _f1(cand) - _f1(champ)
        ok = gain >= float(g["aggregate_min_f1_gain"])
        return Decision(ok, "aggregate", [f"aggregate F1 {gain:+.3f}"], cand, champ)
    reasons = []
    # Both models read the same golden incidents, so each language is a paired comparison: the documents one model
    # catches and the other misses. Thirty languages are thirty tests; Holm's correction keeps false holds rare.
    tests: list[tuple[float, str, float]] = []
    for lang, docs in golden.items():
        r = cand[lang]
        if r.incidents < int(g["min_golden_incidents"]):
            reasons.append(f"{lang}: only {r.incidents} labelled incidents, cannot judge")
            continue
        pos = [d.text for d in docs if d.label]
        a = candidate.scores(pos) >= candidate.threshold(lang)
        b = champion.scores(pos) >= champion.threshold(lang)
        worse, better = int((~a & b).sum()), int((a & ~b).sum())
        drop = (worse - better) / len(pos)
        if drop > float(g["max_language_recall_drop"]):
            tests.append((_sign_test(worse, better), lang, drop))
        if r.recall[2] < float(g["min_language_recall"]):
            reasons.append(f"{lang}: recall {r.recall[0]:.2f}, clearly under {g['min_language_recall']}")
    alpha = float(g["family_alpha"])
    m = len(golden)
    for i, (p, lang, drop) in enumerate(sorted(tests)):
        if p > alpha / (m - i):
            break
        reasons.append(f"{lang}: misses {drop:.1%} more incidents than the champion (p={p:.4f})")
    # keeping recall by lowering thresholds sends more harmless documents to the LLM; judged on the volume it costs
    if shares:
        load_c = sum(shares.get(lang, 0.0) * r.fpr[0] for lang, r in cand.items())
        load_o = sum(shares.get(lang, 0.0) * r.fpr[0] for lang, r in champ.items())
        if load_c > load_o + float(g["max_harmless_pass_increase"]):
            reasons.append(f"passes {load_c:.1%} of harmless volume to the LLM vs {load_o:.1%}")
    return Decision(not reasons, "per_language", reasons or ["every language holds its recall"], cand, champ)
