import { type Console, type Release } from "../../shared/data";
import { Empty } from "../../shared/States";
import "./releases.css";

function Track({ title, items }: { title: string; items: Release[] }) {
  if (!items.length) return <Empty>No releases.</Empty>;
  return (
    <div>
      <h3>{title}</h3>
      <ol className="track">
        {items.map((r) => (
          <li key={`${r.day}-${r.trigger}`} className={r.promoted ? "promoted" : "held"}>
            <span className="day num">day {r.day}</span>
            <div>
              <p><strong>{r.promoted ? "Promoted" : "Held"}</strong> <span className="muted">after {r.trigger}</span></p>
              <p className="muted small">{r.reason}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function ReleasesView({ data }: { data: Console }) {
  const bad = data.bad_promotions[0];
  return (
    <section>
      <header className="head">
        <h1>What reached production, and why</h1>
        <p className="muted">Releases on dev seed {data.seeds[0]}. The platform judges every language on its own; the status quo judges the average.</p>
      </header>
      <div className="tracks">
        <Track title="Platform" items={data.releases.platform} />
        <Track title="Status quo" items={data.releases.status_quo} />
      </div>
      <div className="events">
        {data.breaches.map((b) => (
          <p key={b.day}>
            <strong>Day {b.day}: the label export came back short</strong> for {Object.entries(b.languages).map(([k, [got, want]]) => `${k} (${got} of ${want})`).join(", ")}.{" "}
            {b.repaired ? "The platform requested those languages again before training." : "Nothing noticed."}
          </p>
        ))}
        {data.alerts.map((a) => (
          <p key={`${a.day}-${a.language}`}><strong>Day {a.day}: drift in {a.language}</strong>, {a.reason}. Analysts labelled recent documents; the model was retrained and gated.</p>
        ))}
        {bad && (
          <p className="warn">
            <strong>What the status quo shipped on day {bad.day}:</strong>{" "}
            {Object.entries(bad.languages).map(([k, [a, b]]) => `${k} ${Math.round(a * 100)}% → ${Math.round(b * 100)}%`).join(", ")} of incidents kept.
          </p>
        )}
      </div>
    </section>
  );
}
