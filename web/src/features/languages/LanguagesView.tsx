import { motion, useReducedMotion } from "framer-motion";
import { useState } from "react";
import { pct, type Console } from "../../shared/data";
import { Empty } from "../../shared/States";
import "./languages.css";

const GATE = 0.85;

export function LanguagesView({ data }: { data: Console }) {
  const [design, setDesign] = useState<"platform" | "status_quo">("platform");
  const reduce = useReducedMotion();
  const langs = [...data.languages].sort((a, b) => b.share - a.share);
  if (!langs.length) return <Empty>No languages in the report.</Empty>;
  const below = langs.filter((l) => l[design] < GATE);
  const d = data.designs[design];
  return (
    <section>
      <header className="head">
        <h1>{below.length === 0 ? "Every language keeps 85% of its incidents" : `${below.length} of ${langs.length} languages lose more than 15% of their incidents`}</h1>
        <p className="muted">
          Each tile is a language, widest share of volume first. The fill is the share of real incidents the relevance filter passes on,
          averaged over {data.seeds.length} dev runs; the line is the gate.
        </p>
        <div className="switch" role="radiogroup" aria-label="Design">
          {(["platform", "status_quo"] as const).map((k) => (
            <button key={k} role="radio" aria-checked={design === k} className={design === k ? "on" : ""} onClick={() => setDesign(k)}>
              {k === "platform" ? "Platform" : "Status quo"}
            </button>
          ))}
        </div>
      </header>
      <div className="wall">
        {langs.map((l, i) => {
          const r = l[design];
          return (
            <div key={l.code} className="tile" aria-label={`${l.code}: ${pct(r)} of incidents kept`}>
              <div className="gauge">
                <motion.span
                  className={`fill ${r < GATE ? "fill-low" : ""}`}
                  initial={reduce ? false : { height: 0 }}
                  animate={{ height: `${r * 100}%` }}
                  transition={{ duration: 0.6, delay: reduce ? 0 : i * 0.015, ease: [0.2, 0.7, 0.2, 1] }}
                />
                <span className="gate" style={{ bottom: `${GATE * 100}%` }} />
              </div>
              <p className="caption">
                <span className="code">{l.code}</span>
                <span className={`val num ${r < GATE ? "low" : ""}`}>{pct(r, 0)}</span>
              </p>
              <p className="share num">{pct(l.share)} of volume</p>
            </div>
          );
        })}
      </div>
      <dl className="facts">
        <div><dt>Incidents missed</dt><dd className="num">{pct(d.missed_incident_share)}</dd></div>
        <div><dt>Missed per day</dt><dd className="num">{Math.round(d.missed_incidents_per_day).toLocaleString("en")}</dd></div>
        <div><dt>Worst language</dt><dd className="num">{pct(d.worst_language_recall)}</dd></div>
        <div><dt>Models shipped that hurt a language</dt><dd className="num">{d.bad_promotions.toFixed(0)}</dd></div>
      </dl>
    </section>
  );
}
