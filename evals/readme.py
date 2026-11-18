"""Writes the README results section and docs/charts from reports/*.json. Never edit those numbers by hand."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INK, MUTED, OK, BAD, GRID = "#101c2b", "#5c6878", "#2f6e8e", "#b23a3a", "#e3e8ee"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED, "svg.fonttype": "none",
                     "xtick.color": MUTED, "ytick.color": INK, "axes.labelcolor": INK})
MAIN = ["status_quo", "llm_on_everything", "platform"]


def v(row: dict[str, Any], k: str) -> float:
    m = row[k]["mean"]
    return math.inf if m is None else float(m)


def fmt(row: dict[str, Any], k: str, kind: str) -> str:
    x = row[k]
    m = x["mean"]
    if m is None:
        return "never"
    hw = x.get("half_width") or 0.0
    if kind == "pct":
        s = f"{100 * m:.1f}%"
        return s + (f" ±{100 * hw:.1f}" if hw >= 0.0005 else "")
    if kind == "eur":
        return f"€{m:.3f}"
    if kind == "days":
        return f"{m:.1f} d"
    if kind == "h":
        return f"{m:.1f} h"
    return f"{m:.1f}"


def table(head: list[str], rows: list[list[str]]) -> str:
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
                     + ["| " + " | ".join(r) + " |" for r in rows])


def chart_languages(d: dict[str, Any], path: Path) -> None:
    langs = sorted(d["platform"]["language_recall"], key=lambda k: -d["platform"]["language_recall"][k])
    order = sorted(langs, key=lambda k: d["status_quo"]["language_recall"][k])
    fig, ax = plt.subplots(figsize=(11, 3.4))
    xs = range(len(order))
    ax.bar([x - 0.2 for x in xs], [d["status_quo"]["language_recall"][k] for k in order], 0.4, color="#b9c2cd",
           label="status quo")
    ax.bar([x + 0.2 for x in xs], [d["platform"]["language_recall"][k] for k in order], 0.4, color=OK,
           label="platform")
    ax.axhline(0.85, color=BAD, lw=1, ls="--")
    ax.text(-0.6, 0.865, "gate 0.85", color=BAD, fontsize=8, ha="left")
    ax.set_xticks(list(xs), order)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("share of incidents kept")
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=GRID)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def chart_cost(d: dict[str, Any], path: Path) -> None:
    names = [n for n in ["status_quo", "llm_on_everything", "platform", "payg_only", "ptu_peak",
                         "no_secondary_region", "fixed_scorer_average", "fixed_scorer_peak", "no_dedupe"] if n in d]
    labels = {"status_quo": "Status quo", "llm_on_everything": "LLM on everything", "platform": "Platform",
              "payg_only": "PAYG only", "ptu_peak": "PTU for peak", "no_secondary_region": "No 2nd region",
              "fixed_scorer_average": "Scorer fixed avg", "fixed_scorer_peak": "Scorer fixed peak",
              "no_dedupe": "No dedupe"}
    rows = sorted(names, key=lambda k: v(d[k], "eur_per_1k_documents"))
    fig, ax = plt.subplots(figsize=(8.5, 3.9))
    for i, n in enumerate(rows):
        cost, late = 1000 * v(d[n], "eur_per_1k_documents"), 100 * v(d[n], "sla_breach_share")
        c = BAD if late > 1 else (OK if n == "platform" else "#9aa6b4")
        ax.barh(i, cost, color=c, height=0.62)
        ax.text(cost + 3, i, f"€{cost:.0f}" + (f"   {late:.1f}% of incidents late" if late > 0.05 else ""),
                va="center", fontsize=9, color=BAD if late > 1 else INK)
    ax.set_yticks(range(len(rows)), [labels[n] for n in rows])
    ax.axvline(100, color=BAD, lw=1, ls="--")
    ax.text(101, len(rows) - 0.6, "cost gate", color=BAD, fontsize=8)
    ax.set_xlabel("€ per million documents (scorer + LLM); red: more than 1% of incidents tagged after the SLA")
    ax.set_xlim(0, max(1000 * v(d[n], "eur_per_1k_documents") for n in rows) * 1.45)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def chart_tagging(d: dict[str, Any], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 2.8))
    for n, c, lab in (("auto_upgrade", BAD, "cloud auto-upgrade at retirement"), ("platform", OK, "gated migration")):
        if n not in d:
            continue
        t = d[n]["tagging"]
        ax.plot([x["day"] for x in t], [100 * x["format_ok"] for x in t], color=c, lw=2, label=lab)
    mig = d["platform"]["migrations"]
    if mig:
        ax.axvline(mig[0]["retires_day"], color=MUTED, lw=1, ls=":")
        ax.text(mig[0]["retires_day"] + 0.3, 88, "retirement", color=MUTED, fontsize=8)
        ax.axvline(mig[0]["decided_day"], color=OK, lw=1, ls=":")
        ax.text(mig[0]["decided_day"] + 0.3, 88, "migrated (prompt v2)", color=OK, fontsize=8)
    ax.set_ylim(78, 101)
    ax.set_xlabel("day (dev seed 21)")
    ax.set_ylabel("answers in schema, %")
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def section(dev: dict[str, Any], held: dict[str, Any] | None) -> str:
    d = dev["designs"]
    p = d["platform"]
    out = [f"Generated by `make report` from `reports/dev.json` (dev seeds {', '.join(map(str, dev['seeds']))}; "
           "mean over seeds, ± half a 95% interval; gates judged on the worst seed)"
           + (" and `reports/heldout.json` (held-out world, run once)." if held else
              ". The held-out world has not been run yet.")]
    hg = {g["gate"]: g for g in held["gates"]} if held else {}

    def gv(g: dict[str, Any] | None) -> str:
        if g is None:
            return "not run"
        val = g["value"]
        if val is None:
            s = "never"
        elif g["metric"] in ("worst_language_recall", "missed_incident_share", "sla_breach_share"):
            s = f"{100 * val:.1f}%"
        elif g["metric"] == "eur_per_1k_documents":
            s = f"€{val:.3f}"
        elif g["metric"] == "drift_detection_days":
            s = f"{val:.0f} d"
        else:
            s = f"{val:.0f}"
        return s + (" ✅" if g["passed"] else " ❌")

    rows = [[g["gate"].replace("_", " "), f"{'≥' if g['direction'] == 'min' else '≤'} {g['threshold']}", gv(g),
             gv(hg.get(g["gate"]))] for g in dev["gates"]]
    out += ["", "### Release gates (platform)", "", table(["gate", "threshold", "dev (worst seed)", "held-out"], rows)]
    head = ["design", "worst language recall", "incidents missed", "incidents tagged late", "incidents untagged",
            "€ per 1,000 docs", "bad promotions", "drift noticed after"]

    def row(name: str, label: str | None = None) -> list[str]:
        r = d[name]
        return [label or r["label"].split(":")[0], fmt(r, "worst_language_recall", "pct"),
                fmt(r, "missed_incident_share", "pct"), fmt(r, "sla_breach_share", "pct"),
                fmt(r, "untagged_share", "pct"), fmt(r, "eur_per_1k_documents", "eur"),
                fmt(r, "bad_promotions", "n"), fmt(r, "drift_detection_days", "days")]

    out += ["", "### Designs on the same luck (dev)", "", table(head, [row(n) for n in MAIN if n in d]), "",
            f"Per day that is {v(d['status_quo'], 'missed_incidents_per_day'):,.0f} incidents missed by the status "
            f"quo against {v(p, 'missed_incidents_per_day'):,.0f} by the platform, "
            f"at €{v(d['status_quo'], 'eur_per_day'):,.0f} and €{v(p, 'eur_per_day'):,.0f} a day. Running the LLM "
            f"on everything costs €{v(d['llm_on_everything'], 'eur_per_day'):,.0f} a day.",
            "", "![Recall per language](docs/charts/languages.svg)", ""]
    abl = [row(n, d[n]["label"]) for n in d if n not in MAIN]
    out += ["### Ablations: the platform with one part changed (dev)", "",
            table(head, [row("platform", "nothing (platform)")] + abl),
            "", "![Cost against lateness](docs/charts/cost.svg)", ""]
    rel = [[str(r["day"]), r["trigger"], "promoted" if r["promoted"] else "held", r["reason"]] for r in p["releases"]]
    rel_sq = [[str(r["day"]), r["trigger"], "promoted" if r["promoted"] else "held", r["reason"]]
              for r in d["status_quo"]["releases"]]
    out += ["### Releases on dev seed 21", "", "Platform:", "", table(["day", "trigger", "decision", "why"], rel), "",
            "Status quo (aggregate gate, newest export only):", "",
            table(["day", "trigger", "decision", "why"], rel_sq)]
    bad = d["status_quo"]["bad_promotion_detail"]
    if bad:
        langs = ", ".join(f"{k} {a:.0%}→{b:.0%}" for k, (a, b) in list(bad[0]["languages"].items())[:6])
        out += ["", f"What the status quo shipped on day {bad[0]['day']}, true recall before → after: {langs}."]
    br = p["breaches"]
    if br:
        out += ["", "Label exports the platform caught: " + "; ".join(
            f"day {b['day']}: {', '.join(f'{k} {x[0]}/{x[1]}' for k, x in b['languages'].items())} "
            f"({'requested again' if b['repaired'] else 'not repaired'})" for b in br) + "."]
    mig = p["migrations"]
    if mig:
        m = mig[0]
        res = table(["model", "prompt", "answers in schema", "topics right"],
                    [[r["model"], r["prompt"], f"{100 * r['format_ok']:.1f}%", f"{100 * r['tag_accuracy']:.1f}%"]
                     for r in m["results"]])
        out += ["", f"### LLM retirement (dev seed 21): {m['retiring']} retires on day {m['retires_day']}", "",
                f"Evaluated on day {m['decided_day']}; decision: {m['note']}.", "", res, "",
                "![Tagging around the retirement](docs/charts/tagging.svg)"]
    out += ["", f"Deduplication caught {100 * v(p, 'catch_rate'):.1f}% of syndicated copies and merged "
                f"{100 * v(p, 'false_merge_rate'):.2f}% of different stories. The planner bought "
                f"{v(p, 'ptu_units'):.0f} provisioned units; the scorer averaged {v(p, 'mean_replicas'):.2f} pods. "
                f"Cost per day: " + ", ".join(f"{k} €{x:,.0f}" for k, x in p["eur_split"].items()) + "."]
    if held:
        h = held["designs"]
        out += ["", "### Held-out world (run once)", "",
                "Six other languages missing from a later export, drift in Portuguese, an earlier retirement with a "
                "successor that breaks the format more often, more spikes and throttling.", "",
                table(head, [[h[n]["label"].split(":")[0]] + row_h(h[n]) for n in MAIN if n in h])]
        hm = h["platform"]["migrations"]
        if hm:
            m = hm[0]
            out += ["", f"LLM retirement on the held-out world: {m['retiring']} retires on day {m['retires_day']}; "
                        f"on day {m['decided_day']} the platform found that "
                        + ", ".join(f"{r['model']} {r['prompt']} parses {100 * r['format_ok']:.1f}%"
                                    for r in m["results"][1:])
                        + f". Decision: {m['note']}."]
        hb = h["platform"]["bad_promotion_detail"]
        if hb:
            out += ["", "Platform promotions that hurt a language on the held-out world: " + "; ".join(
                f"day {b['day']}: " + ", ".join(f"{k} {x[0]:.0%}→{x[1]:.0%}" for k, x in b["languages"].items())
                for b in hb) + "."]
    return "\n".join(out)


def row_h(r: dict[str, Any]) -> list[str]:
    return [fmt(r, "worst_language_recall", "pct"), fmt(r, "missed_incident_share", "pct"),
            fmt(r, "sla_breach_share", "pct"), fmt(r, "untagged_share", "pct"), fmt(r, "eur_per_1k_documents", "eur"),
            fmt(r, "bad_promotions", "n"), fmt(r, "drift_detection_days", "days")]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    dev = json.loads((ROOT / "reports" / "dev.json").read_text())
    hp = ROOT / "reports" / "heldout.json"
    held = json.loads(hp.read_text()) if hp.exists() else None
    readme = (ROOT / "README.md").read_text()
    a, b = readme.index("<!-- results:start -->"), readme.index("<!-- results:end -->")
    fresh = readme[:a] + "<!-- results:start -->\n" + section(dev, held) + "\n" + readme[b:]
    if "--check" in args:
        ok = fresh == readme
        print("README results match the reports" if ok else "README results are stale: run `make report`")
        return 0 if ok else 1
    charts = ROOT / "docs" / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    chart_languages(dev["designs"], charts / "languages.svg")
    chart_cost(dev["designs"], charts / "cost.svg")
    chart_tagging(dev["designs"], charts / "tagging.svg")
    (ROOT / "README.md").write_text(fresh)
    print("README results and charts written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
