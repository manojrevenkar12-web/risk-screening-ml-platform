"""The production pipeline's physics, hour by hour, around the platform's decisions.

Documents arrive (world traffic), are deduplicated (the product's Deduper, its catch rate measured on the world's
duplicate pairs), scored by as many replicas as the scaling policy runs, passed on by the serving model at its true
per-language rates, and tagged by the LLM deployment the platform chose, on provisioned or pay-as-you-go capacity
that the world throttles. Costs, delays, missed and untagged incidents are counted against the truth.
"""

from __future__ import annotations

import math
from typing import Any

from evals.truth import rates
from screening.capacity.autoscale import fixed_replicas, lag_replicas, ptu_units
from screening.llm.tagging import parse
from screening.platform import Platform
from screening.text import Deduper
from world.generate import World


def dedupe_rates(world: World, cfg: dict[str, Any], n: int = 300) -> tuple[float, float]:
    """(share of syndicated copies caught, share of different stories wrongly merged), measured with the product's
    Deduper on the world's pairs."""
    caught = copies = merged = others = 0
    for lang in ("en", "de", "id", "th"):
        for a, b, same in world.duplicate_pairs(lang, n):
            dd = Deduper(int(cfg["dedupe"]["max_hamming"]), int(cfg["dedupe"]["shingle"]))
            dd.seen(a.id, a.text)
            hit = dd.seen(b.id, b.text) is not None
            if same:
                copies += 1
                caught += hit
            else:
                others += 1
                merged += hit
    return caught / copies, merged / others


def tagging_quality(world: World, model: str, prompt: str, day: int, n: int = 200) -> tuple[float, float]:
    """(share of answers in the schema, share of parsed answers with the right topics) on today's incidents."""
    docs = (world.relevant_sample("en", n // 2) + world.relevant_sample("de", n // 4)
            + world.relevant_sample("ja", n // 4))
    ok = right = 0
    for doc in docs:
        raw, _ = world.llm_tag(model, prompt, doc, day)
        topics = parse(raw)
        if topics is None:
            continue
        ok += 1
        right += int(topics == sorted(set(doc.topics)))
    return ok / len(docs), right / max(1, ok)


def operate(world: World, platform: Platform, cfg: dict[str, Any], filter_on: bool = True) -> dict[str, Any]:
    st = platform.state
    sc, llm = cfg["scorer"], cfg["llm"]
    per_replica_hour = float(sc["docs_per_second_per_replica"]) * 3600
    catch, false_merge = dedupe_rates(world, cfg) if cfg["dedupe"].get("enabled", True) else (0.0, 0.0)
    dup = world.duplicate_share()
    rel_share = world.relevant_share()
    tokens_per_doc = world.mean_tokens()
    days = world.days
    # forecasts the platform plans with: the first week's hourly volume (it has seen it)
    first_week = [sum(world.hourly_volume(d, h).values()) for d in range(7) for h in range(24)]
    fixed = fixed_replicas(first_week, cfg)
    models_by_version = st.models
    totals = {k: 0.0 for k in ("arrived", "incidents", "missed_filter", "missed_merge", "kept", "breached",
                               "untagged", "eur_scorer", "eur_payg", "eur_ptu", "tokens", "throttled_tokens",
                               "llm_tokens_demand", "replica_hours")}
    lang_recall: dict[str, list[float]] = {}          # language -> [volume x recall, volume]
    degraded_days = 0
    quality_by_day = []
    backlog = 0.0
    llm_queue = 0.0
    replicas = fixed if sc["policy"] != "lag" else int(sc["min_replicas"])
    # size provisioned throughput on the first week of LLM demand under the day-0 model
    m0 = models_by_version[st.serving[0]]
    week_tokens = []
    for d in range(7):
        for h in range(24):
            vol = world.hourly_volume(d, h)
            passes = 0.0
            for key, v in vol.items():
                lang = key.split("#")[0]
                r = rates(world, m0, lang)
                passes += v * (1 - dup * catch) * (rel_share * r.recall + (1 - rel_share) * r.harmless_pass)
            week_tokens.append((passes if filter_on else sum(vol.values()) * (1 - dup * catch)) * tokens_per_doc)
    ptu = ptu_units(week_tokens, cfg)
    ptu_hour = ptu * float(llm["ptu_tokens_per_minute"]) * 60
    hourly_delay: list[float] = []
    for d in range(days):
        model = models_by_version[st.serving[d]]
        llm_model, prompt = st.llm_by_day[d]
        fmt_ok, acc = tagging_quality(world, llm_model, prompt, d)
        quality_by_day.append({"day": d, "model": llm_model, "prompt": prompt, "format_ok": fmt_ok, "accuracy": acc})
        if fmt_ok < float(cfg["lifecycle"]["min_format_ok"]) - 0.01:
            degraded_days += 1
        for h in range(24):
            vol = world.hourly_volume(d, h)
            arrived = sum(vol.values())
            unique = arrived * (1 - dup * catch)
            lost_merge = arrived * (1 - dup) * false_merge
            # scorer
            if sc["policy"] == "lag":
                replicas_now = lag_replicas(unique, backlog, cfg)
                # scaling up takes a few minutes: this hour runs part of the time on the old count
                lag = float(sc["scale_up_minutes"]) / 60
                cap = per_replica_hour * (replicas * lag + replicas_now * (1 - lag)) if replicas_now > replicas \
                    else per_replica_hour * replicas_now
                replicas = replicas_now
            else:
                cap = per_replica_hour * fixed
                replicas = fixed
            work = backlog + unique
            done = min(work, cap)
            backlog = work - done
            score_delay = backlog / max(cap, 1.0)
            totals["replica_hours"] += replicas
            totals["eur_scorer"] += replicas * float(sc["eur_per_replica_hour"])
            # relevance at true rates
            passes = incidents = kept = 0.0
            for key, v in vol.items():
                lang, source = (key.split("#")[0], "drift") if "#" in key else (key, "regular")
                r = rates(world, model, lang, source)
                u = v * (1 - dup * catch)
                inc = v * rel_share
                incidents += inc
                k = u * rel_share * r.recall if filter_on else u * rel_share
                kept += k
                passes += (k + u * (1 - rel_share) * r.harmless_pass) if filter_on else u
                acc = lang_recall.setdefault(lang, [0.0, 0.0])
                acc[0] += v * (r.recall if filter_on else 1.0)
                acc[1] += v
            missed_filter = incidents * (1 - dup * catch) - kept
            totals["arrived"] += arrived
            totals["incidents"] += incidents * (1 - dup * catch)
            totals["missed_filter"] += max(0.0, missed_filter)
            totals["missed_merge"] += lost_merge * rel_share
            totals["kept"] += kept
            # LLM tagging
            demand = passes * tokens_per_doc * (done / max(work, 1.0)) + llm_queue
            totals["llm_tokens_demand"] += passes * tokens_per_doc
            served_ptu = min(demand, ptu_hour)
            rest = demand - served_ptu
            quota = float(llm["payg_tokens_per_hour_quota"])
            # primary region: the deployment's quota, and 429s when the region is contended
            p1 = world.payg_throttle_rate(d, h, "primary")
            ok1 = min(rest, quota) * (1 - p1)
            throttled = rest - ok1
            served_payg = ok1
            if llm["secondary_region"] and throttled > 0:
                p2 = world.payg_throttle_rate(d, h, "secondary")
                ok2 = min(throttled, quota) * (1 - p2)
                served_payg += ok2
                throttled -= ok2
            totals["throttled_tokens"] += throttled
            llm_queue = throttled
            totals["tokens"] += served_ptu + served_payg
            totals["eur_payg"] += served_payg / 1000 * float(llm["eur_per_1k_tokens"])
            throughput = max(1.0, served_ptu + served_payg)
            llm_delay = llm_queue / throughput + (float(llm["retry_backoff_minutes"]) / 60 if llm_queue > 0 else 0.0)
            # a model version that no longer answers: nothing is tagged until someone moves the deployment
            if fmt_ok == 0.0:
                llm_delay = 24.0
            delay = score_delay + llm_delay
            hourly_delay.append(delay)
            if delay > float(cfg["pipeline"]["sla_hours"]):
                totals["breached"] += kept
            totals["untagged"] += kept * (1 - fmt_ok)
        totals["eur_ptu"] += ptu * float(llm["ptu_eur_per_hour"]) * 24
    worst = {lang: v[0] / v[1] for lang, v in lang_recall.items()}
    eur = totals["eur_scorer"] + totals["eur_payg"] + totals["eur_ptu"]
    return {
        "catch_rate": catch, "false_merge_rate": false_merge, "ptu_units": ptu, "fixed_replicas": fixed,
        "language_recall": worst, "worst_language": min(worst, key=lambda k: worst[k]),
        "worst_language_recall": min(worst.values()),
        "missed_incident_share": (totals["missed_filter"] + totals["missed_merge"]) / totals["incidents"],
        "missed_incidents_per_day": (totals["missed_filter"] + totals["missed_merge"]) / days,
        "sla_breach_share": totals["breached"] / max(1.0, totals["kept"]),
        "untagged_share": totals["untagged"] / max(1.0, totals["kept"]),
        "eur_per_day": eur / days, "eur_per_1k_documents": eur / totals["arrived"] * 1000,
        "eur_split": {"scorer": totals["eur_scorer"] / days, "payg": totals["eur_payg"] / days,
                      "ptu": totals["eur_ptu"] / days},
        "throttled_share": totals["throttled_tokens"] / max(1.0, totals["llm_tokens_demand"]),
        "llm_tokens_per_day": totals["llm_tokens_demand"] / days,
        "mean_replicas": totals["replica_hours"] / (days * 24),
        "p95_delay_hours": sorted(hourly_delay)[int(0.95 * len(hourly_delay))],
        "max_delay_hours": max(hourly_delay),
        "degraded_tagging_days": degraded_days,
        "tagging": quality_by_day,
        "documents_per_day": totals["arrived"] / days,
    }


def bad_promotions(world: World, platform: Platform, drop: float = 0.05) -> list[dict[str, Any]]:
    """Promotions after which some language's true recall fell by more than `drop` against the model replaced."""
    st = platform.state
    out = []
    prev = None
    for r in st.releases:
        if not r.promoted:
            continue
        cur = st.models[r.version]
        if prev is not None:
            worse = {}
            for lang in world.languages:
                a, b = rates(world, prev, lang).recall, rates(world, cur, lang).recall
                if b < a - drop:
                    worse[lang] = (round(a, 3), round(b, 3))
            if worse:
                out.append({"day": r.day, "version": r.version, "languages": worse})
        prev = cur
    return out


def drift_detection_days(world: World, platform: Platform) -> float:
    lang, day = world.cfg["drift"]["language"], int(world.cfg["drift"]["day"])
    hits = [a.day for a in platform.state.alerts if a.language == lang and a.day >= day]
    return float(min(hits) - day) if hits else math.inf
