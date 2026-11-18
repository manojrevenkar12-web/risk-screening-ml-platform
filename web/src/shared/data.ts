export type Language = { code: string; share: number; status_quo: number; platform: number };
export type Design = {
  label: string; worst_language_recall: number; missed_incident_share: number; missed_incidents_per_day: number;
  sla_breach_share: number; untagged_share: number; eur_per_day: number; eur_per_1k_documents: number;
  throttled_share: number; p95_delay_hours: number; bad_promotions: number; drift_detection_days: number | null;
  ptu_units: number; mean_replicas: number; eur_split: Record<string, number>;
};
export type Release = { day: number; trigger: string; promoted: boolean; reason: string };
export type Variant = { model: string; prompt: string; format_ok: number; tag_accuracy: number };
export type Migration = {
  retiring: string; successor: string; decided_day: number; retires_day: number; prompt: string | null;
  escalated: boolean; note: string; results: Variant[];
};
export type TagDay = { day: number; model: string; prompt: string; format_ok: number; accuracy: number };
export type Gate = { gate: string; metric: string; direction: string; threshold: number; value: number | null; passed: boolean };
export type Console = {
  seeds: number[];
  languages: Language[];
  designs: Record<string, Design>;
  releases: Record<string, Release[]>;
  alerts: { day: number; language: string; reason: string }[];
  breaches: { day: number; languages: Record<string, [number, number]>; repaired: boolean }[];
  bad_promotions: { day: number; version: string; languages: Record<string, [number, number]> }[];
  migration: Migration | null;
  tagging: Record<string, TagDay[]>;
  gates: Gate[];
};

export async function loadConsole(): Promise<Console> {
  const r = await fetch(`${import.meta.env.BASE_URL}console.json`);
  if (!r.ok) throw new Error(`console.json answered ${r.status}`);
  return (await r.json()) as Console;
}

export const pct = (x: number, d = 1) => `${(100 * x).toFixed(d)}%`;
