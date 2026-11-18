"""A simulated news-screening market with hidden truth.

The world writes documents in 30 synthetic languages (each language its own words for the same concepts, related
languages sharing part of their vocabulary), decides which documents really describe a business-conduct incident,
delivers analyst labels (with a silent gap in one retraining export), sends hourly traffic with spikes, lets a new
source drift one language, and plays the LLM deployments a platform calls: their tagging accuracy, their answer
format under each prompt, their retirement dates, and the throttling of pay-as-you-go capacity.

The product never imports this module. Every draw is a hash of (seed, event), so all designs meet the same luck.
"""

from __future__ import annotations

import hashlib
import math
import random
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

TOPICS = {
    "environment": ["pollution", "spill", "emissions", "deforestation", "toxic_waste"],
    "labour": ["child_labour", "forced_labour", "unpaid_wages", "union_busting"],
    "corruption": ["bribery", "fraud", "money_laundering", "kickback"],
    "human_rights": ["displacement", "land_grab", "discrimination"],
    "product_safety": ["recall", "defect", "contamination"],
    "data_privacy": ["data_breach", "surveillance"],
    "governance": ["accounting_scandal", "insider_trading", "sanctions_breach"],
    "health_safety": ["fatality", "explosion", "injury"],
}
RISK = [c for cs in TOPICS.values() for c in cs]
TOPIC_OF = {c: t for t, cs in TOPICS.items() for c in cs}
INCIDENT = ["accused", "investigated", "fined", "sued", "charged", "reported", "exposed", "alleged"]
# words that look like risk but are harmless in one context and harmful in another
AMBIGUOUS = {"strike": ("deal", "workers"), "fine": ("dining", "regulator"), "leak": ("product_teaser", "chemical"),
             "fire": ("sale", "factory"), "crash": ("stock_rally", "plant"), "charge": ("battery", "court")}
NEUTRAL = [f"n{i}" for i in range(320)]
COMPANIES = [f"co{i}" for i in range(400)]
SYLL = ["ka", "lo", "mi", "ru", "te", "sa", "no", "vi", "da", "pe", "zu", "ri", "go", "ha", "be", "tu", "ne", "fo",
        "xi", "wa", "lu", "qe", "mo", "si", "ya", "ke", "do", "pu", "ze", "ro"]


def _u(*key: Any) -> float:
    d = hashlib.blake2b(repr(key).encode(), digest_size=8).digest()
    return int.from_bytes(d, "big") / 2**64


def _i(lo: int, hi: int, *key: Any) -> int:
    return lo + int(_u(*key) * (hi - lo + 1))


def _pick(seq: list[Any], *key: Any) -> Any:
    return seq[int(_u(*key) * len(seq)) % len(seq)]


def load(name: str = "world") -> dict[str, Any]:
    with open(ROOT / "config" / f"{name}.toml", "rb") as f:
        return tomllib.load(f)


@dataclass
class Doc:
    id: str
    language: str
    text: str
    relevant: bool         # the truth
    label: bool            # what an analyst would label (the truth, with label noise)
    topics: tuple[str, ...]
    source: str            # regular | drift
    duplicate_of: str | None = None


class World:
    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.seed = int(cfg["seed"])
        self.days = int(cfg["days"])
        self.shares: dict[str, float] = dict(cfg["languages"]["shares"])
        total = sum(self.shares.values())
        self.shares = {k: v / total for k, v in self.shares.items()}
        self.languages = list(self.shares)
        self.family = dict(cfg["languages"]["families"])
        self._vocab: dict[tuple[str, str], str] = {}
        self._drift_vocab: dict[tuple[str, str], str] = {}

    # ------------------------------------------------------------------ languages
    def _word(self, concept: str, lang: str, drift: bool = False) -> str:
        """The word a language uses for a concept. Related languages share part of their words."""
        key = (concept, lang)
        if drift and _u(self.seed, "driftword", concept) < self.cfg["drift"]["new_vocabulary_share"]:
            if key not in self._drift_vocab:
                self._drift_vocab[key] = self._make(concept, lang + "#new")
            return self._drift_vocab[key]
        if key not in self._vocab:
            fam = self.family.get(lang, "other")
            shared = fam != "other" and _u(self.seed, "share", concept, lang) < self.cfg["languages"]["family_overlap"]
            self._vocab[key] = self._make(concept, "fam:" + fam if shared else lang)
        return self._vocab[key]

    def _make(self, concept: str, space: str) -> str:
        n = _i(2, 4, self.seed, "len", concept, space)
        return "".join(_pick(SYLL, self.seed, "syl", concept, space, j) for j in range(n))

    # ------------------------------------------------------------------ documents
    def document(self, lang: str, key: Any, source: str = "regular", relevant: bool | None = None) -> Doc:
        """One article. All its draws come from one generator seeded by (seed, language, key, source)."""
        c = self.cfg["documents"]
        rng = random.Random(int(_u(self.seed, "doc", lang, key, source) * 2**63))
        drift = source == "drift"
        if relevant is None:
            relevant = rng.random() < c["relevant_share"]
        else:
            rng.random()
        n = rng.randint(c["tokens"][0], c["tokens"][1])
        words = [self._word(NEUTRAL[int(rng.random() * len(NEUTRAL))], lang, drift) for _ in range(n)]
        topics: tuple[str, ...] = ()
        company = COMPANIES[int(rng.random() * len(COMPANIES))]
        ins: list[str] = [company]
        hard = rng.random() < c["hard_negative_share"]
        amb = list(AMBIGUOUS)[int(rng.random() * len(AMBIGUOUS))]
        verb = INCIDENT[int(rng.random() * len(INCIDENT))]
        if relevant:
            concepts = [RISK[int(rng.random() * len(RISK))] for _ in range(rng.randint(1, 3))]
            topics = tuple(sorted({TOPIC_OF[x] for x in concepts}))
            ins += [self._word(x, lang, drift) for x in concepts]
            ins.append(self._word(verb, lang, drift))
            if rng.random() < 0.3:          # an ambiguous word used in its harmful sense
                ins += [self._word(AMBIGUOUS[amb][1], lang, drift), self._word(amb, lang, drift)]
        elif hard:
            ins += [self._word(amb, lang, drift), self._word(AMBIGUOUS[amb][0], lang, drift)]
            if rng.random() < 0.4:          # an incident verb about something harmless
                ins.append(self._word(verb, lang, drift))
        for w in ins:
            words.insert(rng.randint(0, len(words)), w)
        label = relevant if rng.random() >= c["label_noise"] else not relevant
        return Doc(f"{lang}-{source}-{key}", lang, " ".join(words), bool(relevant), bool(label), topics, source)

    def labelled(self, lang: str, n: int, purpose: str, day: int = 0, relevant_share: float | None = None,
                 source: str = "regular") -> list[Doc]:
        """Analyst-labelled documents. Analysts can be pointed at documents a model flagged, which raises the share
        of incidents in what they label (relevant_share). The retraining export silently drops some languages."""
        if purpose == "retrain" and lang in self.cfg["data_feed"]["missing_languages_in_retrain"]:
            return []
        out = []
        for i in range(n):
            forced = None
            if relevant_share is not None:
                forced = _u(self.seed, "enrich", lang, purpose, day, i) < relevant_share
            src = source
            if purpose in ("recent", "retrain") or purpose.startswith("recent"):
                src = self.traffic_source(lang, day, (purpose, i))
            out.append(self.document(lang, (purpose, day, i), src, relevant=forced))
        return out

    def traffic_source(self, lang: str, day: int, key: Any) -> str:
        """Which source a document of this language and day comes from (the drifted source once it appears)."""
        d = self.cfg["drift"]
        if lang == d["language"] and self.drift_active(day):
            share = (d["volume_multiplier"] - 1) / d["volume_multiplier"]
            if _u(self.seed, "src", lang, day, key) < share:
                return "drift"
        return "regular"

    def traffic(self, lang: str, day: int, n: int) -> list[Doc]:
        """Unlabelled documents as they arrive in the pipeline that day (the product may score them)."""
        return [self.document(lang, ("traffic", day, i), self.traffic_source(lang, day, ("t", i))) for i in range(n)]

    def truth_sample(self, lang: str, n: int, source: str = "regular", tag: str = "truth") -> list[Doc]:
        """Fresh documents never shown to the product, to measure a model's true recall per language."""
        return [self.document(lang, (tag, i), source) for i in range(n)]

    def duplicate_pairs(self, lang: str, n: int) -> list[tuple[Doc, Doc, bool]]:
        """Pairs for the dedupe benchmark: a syndicated copy with light edits (same story) or a different story by
        the same company with the same template (not a duplicate)."""
        out = []
        for i in range(n):
            a = self.document(lang, ("dup", i))
            words = a.text.split()
            if _u(self.seed, "dupkind", lang, i) < 0.6:
                edited = [w if _u(self.seed, "edit", lang, i, j) > 0.06 else self._make(f"edit{j}", lang)
                          for j, w in enumerate(words)]
                cut = _i(0, 4, self.seed, "cut", lang, i)
                out.append((a, Doc(a.id + "-copy", lang, " ".join(edited[cut:]), a.relevant, a.label, a.topics,
                                   a.source, a.id), True))
            else:
                b = self.document(lang, ("dupother", i))
                shared = words[: len(words) // 3] + b.text.split()[len(b.text.split()) // 3:]
                out.append((a, Doc(b.id + "-near", lang, " ".join(shared), b.relevant, b.label, b.topics, b.source),
                            False))
        return out

    def relevant_sample(self, lang: str, n: int, source: str = "regular") -> list[Doc]:
        return [self.document(lang, ("relevant", i), source, relevant=True) for i in range(n)]

    # ------------------------------------------------------------------ traffic
    def drift_active(self, day: int) -> bool:
        return day >= int(self.cfg["drift"]["day"])

    def hourly_volume(self, day: int, hour: int) -> dict[str, float]:
        """Documents arriving in one hour, by language (expected counts; the pipeline handles millions a day)."""
        t = self.cfg["traffic"]
        base = float(self.cfg["documents_per_day"]) / 24
        weekday = t["weekend_factor"] if day % 7 in (5, 6) else t["weekday_factor"]
        diurnal = 1 + (t["hourly_peak"] - 1) * 0.5 * (1 - math.cos(2 * math.pi * (hour - 3) / 24))
        diurnal /= 1 + (t["hourly_peak"] - 1) * 0.5
        spike = 1.0
        week = day // 7
        for s in range(int(math.ceil(t["spikes_per_week"])) + 1):
            if _u(self.seed, "spike?", week, s) > t["spikes_per_week"] - s:
                continue
            sday = week * 7 + _i(0, 6, self.seed, "sday", week, s)
            sh = _i(0, 20, self.seed, "shour", week, s)
            length = _i(t["spike_hours"][0], t["spike_hours"][1], self.seed, "slen", week, s)
            if sday == day and sh <= hour < sh + length:
                spike = max(spike, t["spike_size"][0] + (t["spike_size"][1] - t["spike_size"][0])
                            * _u(self.seed, "ssize", week, s))
        vol = base * weekday * diurnal * spike * (0.95 + 0.1 * _u(self.seed, "noise", day, hour))
        out = {lang: vol * share for lang, share in self.shares.items()}
        d = self.cfg["drift"]
        if self.drift_active(day):
            out[d["language"] + "#drift"] = out[d["language"]] * (d["volume_multiplier"] - 1)
        return out

    def duplicate_share(self) -> float:
        return float(self.cfg["documents"]["duplicate_share"])

    def relevant_share(self) -> float:
        return float(self.cfg["documents"]["relevant_share"])

    # ------------------------------------------------------------------ LLM deployments
    def catalog(self) -> list[dict[str, Any]]:
        """What the cloud tells customers: model versions and their retirement days (not their behaviour)."""
        return [{"model": m["model"], "retires_day": m["retires_day"]} for m in self.cfg["llm"]["catalog"]]

    def _model(self, name: str) -> dict[str, Any]:
        return next(m for m in self.cfg["llm"]["catalog"] if m["model"] == name)

    def llm_tag(self, model: str, prompt: str, doc: Doc, day: int) -> tuple[str | None, int]:
        """(raw answer, tokens). A retired model answers nothing. The raw answer may break the expected format."""
        m = self._model(model)
        k = (self.seed, "llm", model, prompt, doc.id)
        lo, hi = self.cfg["llm"]["tokens_per_document"]
        tokens = _i(lo, hi, *k, "tok")
        if day >= int(m["retires_day"]):
            return None, 0
        if _u(*k, "fmt") > m["format_ok"][prompt]:
            return "Topics: " + ", ".join(t.upper() for t in doc.topics or ("none",)), tokens
        topics = list(doc.topics) if doc.topics else []
        if _u(*k, "acc") > m["tag_accuracy"]:
            topics = [_pick(list(TOPICS), *k, "wrong")]
        return '{"topics": [' + ", ".join(f'"{t}"' for t in topics) + "]}", tokens

    def payg_throttle_rate(self, day: int, hour: int, region: str) -> float:
        """Share of pay-as-you-go calls answered 429 in an hour. The primary region is contended in business hours;
        the secondary region (another time zone) is contended at different hours."""
        lo, hi = self.cfg["llm"]["payg_regional_busy_hours"]
        if region == "secondary":
            hour = (hour + 9) % 24
        busy = lo <= hour < hi and day % 7 not in (5, 6)
        base = self.cfg["llm"]["payg_throttle_when_busy"] * (1.0 if busy else 0.12)
        return base * (0.8 + 0.4 * _u(self.seed, "429", region, day, hour))

    def mean_tokens(self) -> float:
        lo, hi = self.cfg["llm"]["tokens_per_document"]
        return (lo + hi) / 2
