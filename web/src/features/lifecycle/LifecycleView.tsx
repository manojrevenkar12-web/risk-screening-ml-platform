import { pct, type Console, type TagDay } from "../../shared/data";
import { Empty } from "../../shared/States";
import "./lifecycle.css";

const W = 640, H = 160, PAD = 28;

function Lines({ series, days }: { series: Record<string, TagDay[]>; days: number }) {
  const y = (v: number) => H - PAD - ((v - 0.75) / 0.25) * (H - 2 * PAD);
  const x = (d: number) => PAD + (d / Math.max(1, days - 1)) * (W - 2 * PAD);
  const colors: Record<string, string> = { platform: "var(--steel)", auto_upgrade: "var(--risk)" };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Share of LLM answers in the expected schema per day">
      {[0.8, 0.9, 1].map((t) => (
        <g key={t}>
          <line x1={PAD} x2={W - PAD} y1={y(t)} y2={y(t)} stroke="var(--rule)" />
          <text x={4} y={y(t) + 4} fontSize="10" fill="var(--muted)">{Math.round(t * 100)}%</text>
        </g>
      ))}
      {Object.entries(series).sort(([a]) => (a === "platform" ? 1 : -1)).map(([k, pts]) => (
        <polyline key={k} fill="none" stroke={colors[k] ?? "var(--ink)"} strokeWidth="2"
          points={pts.map((p) => `${x(p.day)},${y(Math.max(0.75, p.format_ok))}`).join(" ")} />
      ))}
    </svg>
  );
}

export function LifecycleView({ data }: { data: Console }) {
  const m = data.migration;
  if (!m) return <Empty>No retirement fell inside the run.</Empty>;
  const days = data.tagging.platform?.length ?? 0;
  return (
    <section>
      <header className="head">
        <h1>{m.retiring} retires on day {m.retires_day}</h1>
        <p className="muted">
          On day {m.decided_day} the platform tried the successor under each prompt against the analysts' topic golden set.
          {m.escalated ? " No prompt passed; a person decides before the date." : ` It moved to ${m.successor} with prompt ${m.prompt}, ${m.retires_day - m.decided_day} days before the retirement.`}
        </p>
      </header>
      <table>
        <thead><tr><th>Model</th><th>Prompt</th><th className="num">Answers in schema</th><th className="num">Topics right</th></tr></thead>
        <tbody>
          {m.results.map((r) => (
            <tr key={`${r.model}-${r.prompt}`}>
              <td>{r.model}</td><td>{r.prompt}</td>
              <td className={`num ${r.format_ok < 0.99 ? "bad" : ""}`}>{pct(r.format_ok)}</td>
              <td className="num">{pct(r.tag_accuracy)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="chart">
        <h3>Answers the pipeline could parse, per day</h3>
        <p className="muted small"><span className="key steel" /> gated migration <span className="key risk" /> the cloud's upgrade at retirement</p>
        <Lines series={data.tagging} days={days} />
      </div>
    </section>
  );
}
