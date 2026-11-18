"""Writes web/public/console.json, the console's data, from reports/dev.json. Generated, never edited."""

from __future__ import annotations

import json
from pathlib import Path

from world.generate import load

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["worst_language_recall", "missed_incident_share", "missed_incidents_per_day", "sla_breach_share",
        "untagged_share", "eur_per_day", "eur_per_1k_documents", "throttled_share", "p95_delay_hours",
        "bad_promotions", "drift_detection_days", "ptu_units", "mean_replicas"]


def main() -> None:
    dev = json.loads((ROOT / "reports" / "dev.json").read_text())
    d = dev["designs"]
    shares = load("world")["languages"]["shares"]
    total = sum(shares.values())
    out = {
        "seeds": dev["seeds"],
        "languages": [{"code": k, "share": shares[k] / total,
                       "status_quo": d["status_quo"]["language_recall"][k],
                       "platform": d["platform"]["language_recall"][k]} for k in shares],
        "designs": {n: {"label": r["label"], **{k: r[k]["mean"] for k in KEYS}, "eur_split": r["eur_split"]}
                    for n, r in d.items()},
        "releases": {n: d[n]["releases"] for n in ("platform", "status_quo")},
        "alerts": d["platform"]["alerts"],
        "breaches": d["platform"]["breaches"],
        "bad_promotions": d["status_quo"]["bad_promotion_detail"],
        "migration": d["platform"]["migrations"][0] if d["platform"]["migrations"] else None,
        "tagging": {n: d[n]["tagging"] for n in ("platform", "auto_upgrade") if n in d},
        "gates": dev["gates"],
    }
    path = ROOT / "web" / "public" / "console.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    print("console data written")


if __name__ == "__main__":
    main()
