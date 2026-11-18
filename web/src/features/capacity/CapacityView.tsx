import { pct, type Console } from "../../shared/data";
import "./capacity.css";

const NAMES: Record<string, string> = {
  status_quo: "Status quo", llm_on_everything: "LLM on everything", platform: "Platform", payg_only: "Pay-as-you-go only",
  ptu_peak: "Provisioned for the peak", no_secondary_region: "No second region", fixed_scorer_average: "Scorer fixed at average",
  fixed_scorer_peak: "Scorer fixed at peak", no_dedupe: "No deduplication",
};

export function CapacityView({ data }: { data: Console }) {
  const rows = Object.keys(NAMES).filter((k) => data.designs[k]);
  const max = Math.max(...rows.map((k) => data.designs[k].eur_per_day));
  return (
    <section>
      <header className="head">
        <h1>Cost against lateness</h1>
        <p className="muted">Per day over the dev runs. Late: incidents tagged after the four-hour SLA, mostly during news spikes when pay-as-you-go is throttled or the scorer cannot keep up.</p>
      </header>
      <table>
        <thead><tr><th>Design</th><th>Cost per day</th><th className="num">€ per million documents</th><th className="num">Late</th><th className="num">Throttled</th><th className="num">PTU</th></tr></thead>
        <tbody>
          {rows.map((k) => {
            const d = data.designs[k];
            return (
              <tr key={k} className={k === "platform" ? "me" : ""}>
                <td>{NAMES[k]}</td>
                <td>
                  <span className="stack" title={Object.entries(d.eur_split).map(([n, v]) => `${n} €${Math.round(v)}`).join(", ")}>
                    {Object.entries(d.eur_split).map(([n, v]) => (
                      <span key={n} className={`seg seg-${n}`} style={{ width: `${(v / max) * 100}%` }} />
                    ))}
                  </span>
                  <span className="num small"> €{Math.round(d.eur_per_day).toLocaleString("en")}</span>
                </td>
                <td className="num">{(d.eur_per_1k_documents * 1000).toFixed(0)}</td>
                <td className={`num ${d.sla_breach_share > 0.01 ? "bad" : ""}`}>{pct(d.sla_breach_share, 2)}</td>
                <td className="num">{pct(d.throttled_share)}</td>
                <td className="num">{d.ptu_units.toFixed(0)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="muted small legend"><span className="seg seg-scorer" /> scorer pods <span className="seg seg-payg" /> pay-as-you-go tokens <span className="seg seg-ptu" /> provisioned units</p>
    </section>
  );
}
