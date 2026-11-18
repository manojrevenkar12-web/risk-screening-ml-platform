"""The platform's control loop, one day at a time, the same code for every design.

Day 0: build golden sets, allocate labels, train the first relevance model, fit per-language thresholds, gate it,
export it to ONNX. Every day: watch each language's score distribution and share of volume for drift; on a schedule
or a drift alert, retrain and gate; plan capacity for the scorer and the LLM; watch LLM retirements and migrate
before them. The market is anything that provides labels, traffic samples, the deployment catalog and LLM answers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from screening.lifecycle.retirement import MigrationPlan, plan
from screening.models import gate as gating
from screening.models.registry import log_release
from screening.models.relevance import RelevanceModel, allocate, export_onnx, fit_thresholds, train, version_of
from screening.monitoring.drift import DriftAlert, check, histogram


class Market(Protocol):
    def labelled(self, lang: str, n: int, purpose: str, day: int = 0, relevant_share: float | None = None,
                 source: str = "regular") -> list[Any]: ...

    def traffic(self, lang: str, day: int, n: int) -> list[Any]: ...

    def catalog(self) -> list[dict[str, Any]]: ...

    def llm_tag(self, model: str, prompt: str, doc: Any, day: int) -> tuple[str | None, int]: ...


@dataclass
class Release:
    day: int
    version: str
    promoted: bool
    reason: str
    trigger: str
    decision: gating.Decision | None = None


@dataclass
class ContractBreach:
    day: int
    purpose: str
    languages: dict[str, tuple[int, int]]      # language -> (received, requested)
    repaired: bool


@dataclass
class State:
    champion: RelevanceModel | None = None
    train_docs: list[Any] = field(default_factory=list)
    releases: list[Release] = field(default_factory=list)
    alerts: list[DriftAlert] = field(default_factory=list)
    serving: dict[int, str] = field(default_factory=dict)            # day -> model version
    models: dict[str, RelevanceModel] = field(default_factory=dict)
    llm_model: str = ""
    llm_prompt: str = ""
    llm_by_day: dict[int, tuple[str, str]] = field(default_factory=dict)
    migrations: list[MigrationPlan] = field(default_factory=list)
    ref_hist: dict[str, np.ndarray] = field(default_factory=dict)
    ref_share: dict[str, float] = field(default_factory=dict)
    recent_scores: dict[str, list[np.ndarray]] = field(default_factory=dict)
    drift_handled: set[str] = field(default_factory=set)
    breaches: list[ContractBreach] = field(default_factory=list)


class Platform:
    def __init__(self, market: Market, shares: dict[str, float], cfg: dict[str, Any], artefacts: Path | None = None):
        self.m, self.shares, self.cfg = market, shares, cfg
        self.artefacts = artefacts
        self.state = State()
        lab = cfg["labels"]
        self.golden_cal: dict[str, list[Any]] = {}
        self.golden_test: dict[str, list[Any]] = {}
        for lang in shares:
            docs = (market.labelled(lang, int(lab["golden_relevant"]), "golden", 0, relevant_share=1.0)
                    + market.labelled(lang, int(lab["golden_random"]), "golden_random", 0))
            self.golden_cal[lang] = docs[0::2]
            self.golden_test[lang] = docs[1::2]
        self.topic_golden = [d for lang in shares for d in market.labelled(
            lang, max(4, int(int(lab["topic_golden"]) * shares[lang])), "topic_golden", 0, relevant_share=1.0)]
        cat = market.catalog()
        oldest = min(cat, key=lambda m: m["retires_day"])
        self.state.llm_model, self.state.llm_prompt = oldest["model"], str(cfg["llm"]["prompt"])

    # ------------------------------------------------------------------ relevance models
    def _labels(self, purpose: str, day: int) -> list[Any]:
        """The label export for a training round. With the data contract on, a language that came back short is a
        broken export: the shortfall is recorded and those languages are requested again before anything trains."""
        docs: list[Any] = []
        short: dict[str, tuple[int, int]] = {}
        floor = float(self.cfg["retraining"]["contract_min_share"])
        for lang, (n, enrich) in allocate(self.shares, self.cfg).items():
            got = self.m.labelled(lang, n, purpose, day, relevant_share=enrich)
            if len(got) < floor * n:
                short[lang] = (len(got), n)
                if self.cfg["retraining"]["data_contract"]:
                    got = self.m.labelled(lang, n, purpose + "_reexport", day, relevant_share=enrich)
            docs += got
        if short:
            repaired = bool(self.cfg["retraining"]["data_contract"])
            self.state.breaches.append(ContractBreach(day, purpose, short, repaired))
        return docs

    def _release(self, docs: list[Any], day: int, trigger: str) -> Release:
        cand = train(docs, self.cfg, version_of(docs, f"d{day:02d}"))
        fit_thresholds(cand, self.golden_cal, self.cfg)
        dec = gating.decide(cand, self.state.champion, self.golden_test, self.cfg, self.shares)
        rel = Release(day, cand.version, dec.promote, "; ".join(dec.reasons[:4]), trigger, dec)
        self.state.models[cand.version] = cand
        artefact = None
        if dec.promote:
            self.state.champion = cand
            self.state.train_docs = docs
            if self.artefacts is not None:
                artefact = export_onnx(cand, self.artefacts)
            if day > 0:
                self._reference(day)        # a new model scores differently: compare against its own reference
        self.state.releases.append(rel)
        log_release(cand.version, day, trigger, dec.promote, dec.reasons,
                    {"labels": self.cfg["labels"]["allocation"], "thresholds": self.cfg["thresholds"]["mode"],
                     "gate": self.cfg["gate"]["mode"], "documents": len(docs)}, dec.candidate, artefact)
        return rel

    def _reference(self, day: int) -> None:
        assert self.state.champion is not None
        for lang in self.shares:
            docs = self.m.traffic(lang, day, 4 * int(self.cfg["drift"]["sample"]))
            scores = self.state.champion.scores([d.text for d in docs])
            self.state.ref_hist[lang] = histogram(scores, self.cfg["drift"]["bins"])
            self.state.recent_scores[lang] = []

    # ------------------------------------------------------------------ one day
    def day(self, d: int, observed_volume: dict[str, float]) -> None:  # noqa: C901
        cfg, st = self.cfg, self.state
        if d == 0:
            self._release(self._labels("train", 0), 0, "initial")
            self._reference(0)
            total = sum(observed_volume.values())
            st.ref_share = {lang: v / total for lang, v in observed_volume.items()}
        if d in cfg["retraining"]["schedule_days"] and d > 0:
            # scheduled retrain on the latest analyst export, as the pipeline is set up to do
            # scheduled retrain: everything the champion learned from plus the latest analyst export
            new = self._labels("retrain", d)
            docs = self.state.train_docs + new if cfg["retraining"]["window"] == "cumulative" else new
            self._release(docs, d, "schedule")
        # drift watch on today's traffic
        if cfg["drift"].get("enabled", True) and d > 0 and st.champion is not None:
            total = sum(observed_volume.values())
            for lang in self.shares:
                docs = self.m.traffic(lang, d, int(cfg["drift"]["sample"]))
                window = st.recent_scores.setdefault(lang, [])
                window.append(st.champion.scores([x.text for x in docs]))
                del window[:-int(cfg["drift"]["window_days"])]
                cur = histogram(np.concatenate(window), cfg["drift"]["bins"])
                alert = check(lang, d, st.ref_hist[lang], cur, st.ref_share.get(lang, 0.0),
                              observed_volume.get(lang, 0.0) / total, float(cfg["drift"]["psi_alert"]),
                              float(cfg["drift"]["mix_alert"]))
                if alert and lang not in st.drift_handled:
                    st.alerts.append(alert)
                    st.drift_handled.add(lang)
                    if cfg["retraining"]["drift_retrain"]:
                        self._drift_retrain(lang, d)
        st.serving[d] = st.champion.version if st.champion else ""
        # LLM lifecycle
        cat = self.m.catalog()
        lc = cfg["lifecycle"]
        if lc["mode"] == "gated_migration":
            pending = next((p for p in st.migrations if p.retiring == st.llm_model), None)
            if pending is None:
                p = plan(cat, st.llm_model, st.llm_prompt, d,
                         lambda model, prompt, doc: self.m.llm_tag(model, prompt, doc, d), self.topic_golden, cfg)
                if p is not None:
                    st.migrations.append(p)
                    if p.chosen_prompt:
                        st.llm_model, st.llm_prompt = p.successor, p.chosen_prompt
        else:
            mine = next((x for x in cat if x["model"] == st.llm_model), None)
            if mine and d >= int(mine["retires_day"]):
                succ = max((x for x in cat if x["retires_day"] > mine["retires_day"]), key=lambda x: x["retires_day"])
                st.migrations.append(MigrationPlan(st.llm_model, succ["model"], int(mine["retires_day"]), d,
                                                   st.llm_prompt, [], False, "auto-upgraded at retirement"))
                st.llm_model = succ["model"]
        st.llm_by_day[d] = (st.llm_model, st.llm_prompt)

    def _drift_retrain(self, lang: str, d: int) -> None:
        """Analysts label recent traffic in the drifting language (incidents first); the golden sets for that
        language get recent documents too, so the gate judges the model on what it now has to read."""
        n = int(self.cfg["drift"]["relabel"])
        enrich = float(self.cfg["labels"]["enrich_relevant_share"])
        new = self.m.labelled(lang, n, "recent", d, relevant_share=enrich)
        gold = (self.m.labelled(lang, int(self.cfg["labels"]["golden_relevant"]), "recent_golden", d,
                                relevant_share=1.0)
                + self.m.labelled(lang, int(self.cfg["labels"]["golden_random"]) // 2, "recent_golden_random", d))
        self.golden_cal[lang] = self.golden_cal[lang] + gold[0::2]
        self.golden_test[lang] = self.golden_test[lang] + gold[1::2]
        self._release(self.state.train_docs + new, d, f"drift in {lang}")
