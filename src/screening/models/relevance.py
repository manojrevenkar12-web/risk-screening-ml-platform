"""The relevance filter: a multilingual text classifier trained on analyst labels, exported to ONNX for serving.

It stands in for the in-house transformer: TF-IDF over words and logistic regression train in seconds, so every
design can retrain on the same luck. The platform around it (label allocation, per-language thresholds and gates,
ONNX export, registry, serving) does not care which model sits inside.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


class Labelled(Protocol):
    language: str
    text: str
    label: bool


class LabelSource(Protocol):
    def labelled(self, lang: str, n: int, purpose: str, day: int = 0, relevant_share: float | None = None,
                 source: str = "regular") -> list[Any]: ...


def allocate(shares: dict[str, float], cfg: dict[str, Any]) -> dict[str, tuple[int, float | None]]:
    """How many labels to request per language, and whether analysts should label model-flagged documents first.
    proportional: by volume share. floor: at least min_per_language, enriched with incidents, paid for by the
    largest languages."""
    lab = cfg["labels"]
    budget = int(lab["budget_per_round"])
    if lab["allocation"] == "proportional":
        return {lang: (max(1, int(budget * s)), None) for lang, s in shares.items()}
    floor = int(lab["min_per_language"])
    small = {lang for lang, s in shares.items() if budget * s < floor}
    rest = budget - floor * len(small)
    big_total = sum(s for lang, s in shares.items() if lang not in small)
    out: dict[str, tuple[int, float | None]] = {}
    for lang, s in shares.items():
        if lang in small:
            out[lang] = (floor, float(lab["enrich_relevant_share"]))
        else:
            out[lang] = (max(floor, int(rest * s / big_total)), None)
    return out


@dataclass
class RelevanceModel:
    version: str
    pipeline: Pipeline
    thresholds: dict[str, float] = field(default_factory=dict)
    default_threshold: float = 0.5
    trained_on: dict[str, int] = field(default_factory=dict)

    def scores(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros(0)
        return self.pipeline.predict_proba(texts)[:, 1]

    def threshold(self, lang: str) -> float:
        return self.thresholds.get(lang, self.default_threshold)

    def passes(self, lang: str, texts: list[str]) -> np.ndarray:
        return self.scores(texts) >= self.threshold(lang)


def train(docs: list[Labelled], cfg: dict[str, Any], version: str) -> RelevanceModel:
    m = cfg["model"]
    # texts arrive lowercased by the ingestion step; lowercasing inside the graph would need a locale in the image
    pipe = Pipeline([("tfidf", TfidfVectorizer(min_df=int(m["min_df"]), lowercase=False)),
                     ("clf", LogisticRegression(C=float(m["C"]), max_iter=int(m["max_iter"]),
                                                class_weight="balanced"))])
    pipe.fit([d.text for d in docs], [bool(d.label) for d in docs])
    counts: dict[str, int] = {}
    for d in docs:
        counts[d.language] = counts.get(d.language, 0) + 1
    return RelevanceModel(version, pipe, {}, float(cfg["thresholds"]["global"]), counts)


def fit_thresholds(model: RelevanceModel, golden: dict[str, list[Labelled]], cfg: dict[str, Any]) -> None:
    """Per language, the highest threshold that keeps the target recall on that language's golden incidents: lower
    than the default where the model is unsure (small languages), higher where it is sure (English), which cuts the
    harmless documents sent on to the LLM."""
    t = cfg["thresholds"]
    if t["mode"] != "per_language":
        model.thresholds = {}
        return
    target = float(t["target_recall"])
    for lang, docs in golden.items():
        pos = np.sort(model.scores([d.text for d in docs if d.label]))
        if len(pos) == 0:
            continue
        k = int(np.floor((1 - target) * len(pos)))
        model.thresholds[lang] = float(max(float(t["min_threshold"]), pos[k]))


def version_of(docs: list[Labelled], tag: str) -> str:
    h = hashlib.sha1(usedforsecurity=False)
    for d in docs[:2000]:
        h.update(d.text.encode())
    return f"relevance-{tag}-{h.hexdigest()[:8]}"


def export_onnx(model: RelevanceModel, out_dir: Path) -> Path:
    """The serving artefact: the scikit-learn pipeline as ONNX plus the per-language thresholds as JSON."""
    from skl2onnx import to_onnx
    from skl2onnx.common.data_types import StringTensorType

    out_dir.mkdir(parents=True, exist_ok=True)
    onx = to_onnx(model.pipeline, initial_types=[("text", StringTensorType([None, 1]))],
                  options={id(model.pipeline.steps[-1][1]): {"zipmap": False}}, target_opset=17)
    path = out_dir / f"{model.version}.onnx"
    path.write_bytes(onx.SerializeToString())
    (out_dir / f"{model.version}.json").write_text(json.dumps(
        {"version": model.version, "thresholds": model.thresholds, "default_threshold": model.default_threshold,
         "trained_on": model.trained_on}, indent=1))
    return path
