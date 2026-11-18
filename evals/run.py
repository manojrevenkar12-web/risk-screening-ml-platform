"""Every design on the same dev worlds, the gates, and (once) the held-out world.

    python -m evals.run             # dev seeds -> reports/dev.json
    python -m evals.run --heldout   # held-out world, once -> reports/heldout.json + reports/heldout.lock
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

from evals.operate import bad_promotions, drift_detection_days, operate
from screening.config import gates, settings
from screening.platform import Platform
from world.generate import World, load

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
RELEVANCE_SECTIONS = ("labels", "model", "thresholds", "gate", "retraining", "drift", "lifecycle")


def designs() -> dict[str, dict[str, Any]]:
    with open(ROOT / "config" / "designs.toml", "rb") as f:
        return tomllib.load(f)


def overrides(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {k: v for k, v in spec.items() if isinstance(v, dict)}


def run_platform(world: World, cfg: dict[str, Any]) -> Platform:
    p = Platform(world, world.shares, cfg)
    for d in range(world.days):
        vol: dict[str, float] = {}
        for h in range(24):
            for k, v in world.hourly_volume(d, h).items():
                lang = k.split("#")[0]
                vol[lang] = vol.get(lang, 0.0) + v
        p.day(d, vol)
    return p


def run_world(wcfg: dict[str, Any], names: list[str]) -> dict[str, Any]:
    world = World(wcfg)
    cache: dict[str, Platform] = {}
    out: dict[str, Any] = {}
    for name in names:
        spec = designs()[name]
        cfg = settings(overrides(spec))
        key = json.dumps({s: cfg.get(s) for s in RELEVANCE_SECTIONS}, sort_keys=True)
        t = time.perf_counter()
        if key not in cache:
            cache[key] = run_platform(world, cfg)
        p = cache[key]
        m = operate(world, p, cfg, filter_on=bool(cfg.get("filter", {}).get("enabled", True)))
        bad = bad_promotions(world, p)
        m["bad_promotions"] = len(bad)
        m["bad_promotion_detail"] = bad
        m["drift_detection_days"] = drift_detection_days(world, p)
        m["releases"] = [{"day": r.day, "trigger": r.trigger, "promoted": r.promoted, "reason": r.reason}
                         for r in p.state.releases]
        m["alerts"] = [{"day": a.day, "language": a.language, "reason": a.reason} for a in p.state.alerts]
        m["breaches"] = [{"day": b.day, "languages": {k: list(v) for k, v in b.languages.items()},
                          "repaired": b.repaired} for b in p.state.breaches]
        m["migrations"] = [{"retiring": x.retiring, "successor": x.successor, "decided_day": x.decided_day,
                            "retires_day": x.retires_day, "prompt": x.chosen_prompt, "escalated": x.escalated,
                            "note": x.note, "results": [r.__dict__ for r in x.results]} for x in p.state.migrations]
        m["seconds"] = time.perf_counter() - t
        out[name] = m
        print(f"  {world.cfg['name']} seed {world.seed} {name}: {m['seconds']:.0f}s", file=sys.stderr)
    return out


SCALARS = ["worst_language_recall", "missed_incident_share", "missed_incidents_per_day", "sla_breach_share",
           "untagged_share", "eur_per_day", "eur_per_1k_documents", "throttled_share", "llm_tokens_per_day",
           "mean_replicas", "p95_delay_hours", "max_delay_hours", "degraded_tagging_days", "bad_promotions",
           "drift_detection_days", "catch_rate", "false_merge_rate", "ptu_units"]


def summarise(per_seed: list[dict[str, Any]], names: list[str]) -> dict[str, Any]:
    out = {}
    for name in names:
        runs = [s[name] for s in per_seed]
        row: dict[str, Any] = {"label": designs()[name]["label"]}
        for k in SCALARS:
            vals = [float(r[k]) for r in runs]
            finite = all(math.isfinite(v) for v in vals)
            mean = sum(vals) / len(vals) if finite else math.inf
            sd = (sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5 if finite and len(vals) > 1 else 0.0
            row[k] = {"mean": mean, "half_width": 1.96 * sd / math.sqrt(len(vals)) if finite else None,
                      "per_seed": vals, "worst": max(vals) if k != "worst_language_recall" else min(vals)}
        row["language_recall"] = {lang: sum(r["language_recall"][lang] for r in runs) / len(runs)
                                  for lang in runs[0]["language_recall"]}
        row["eur_split"] = {k: sum(r["eur_split"][k] for r in runs) / len(runs) for k in runs[0]["eur_split"]}
        for k in ("releases", "alerts", "breaches", "migrations", "tagging", "bad_promotion_detail"):
            row[k] = runs[0][k]
        out[name] = row
    return out


def judge(row: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for gid, g in gates().items():
        v = row[g["metric"]]
        value = v["worst"]               # the worst seed, not the average
        ok = value >= g["threshold"] if g["direction"] == "min" else value <= g["threshold"]
        out.append({"gate": gid, "metric": g["metric"], "direction": g["direction"], "threshold": g["threshold"],
                    "value": value, "passed": bool(ok), "why": g["why"]})
    return out


def fingerprint() -> str:
    h = hashlib.sha256()
    for p in sorted([*ROOT.glob("src/screening/**/*.py"), *ROOT.glob("config/*.toml"), *ROOT.glob("world/*.py")]):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _clean(x: Any) -> Any:
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heldout", action="store_true")
    ap.add_argument("--seeds", type=int, nargs="*")
    ap.add_argument("--designs", nargs="*")
    args = ap.parse_args(argv)
    names = args.designs or list(designs())
    REPORTS.mkdir(exist_ok=True)
    if args.heldout:
        lock = REPORTS / "heldout.lock"
        if lock.exists():
            print(f"held-out world already run ({lock.read_text().strip()}); it is run once.", file=sys.stderr)
            return 2
        wcfg = load("heldout")
        per_seed = [run_world(wcfg, names)]
        seeds = [wcfg["seed"]]
        out_name = "heldout.json"
    else:
        base = load("world")
        seeds = args.seeds or base["dev_seeds"]
        per_seed = [run_world(dict(base, seed=s), names) for s in seeds]
        out_name = "dev.json"
    summary = summarise(per_seed, names)
    report = {"world": "heldout" if args.heldout else "dev", "seeds": seeds, "fingerprint": fingerprint(),
              "designs": summary, "gates": judge(summary["platform"]) if "platform" in summary else []}
    (REPORTS / out_name).write_text(json.dumps(_clean(report), indent=1, default=str))
    if args.heldout:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                cwd=ROOT).stdout.strip()
        (REPORTS / "heldout.lock").write_text(f"run {time.strftime('%Y-%m-%d')} at commit {commit or 'uncommitted'}, "
                                              f"code fingerprint {report['fingerprint']}\n")
    for g in report["gates"]:
        print(f"{'PASS' if g['passed'] else 'FAIL'} {g['gate']}: {g['value']} ({g['direction']} {g['threshold']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
