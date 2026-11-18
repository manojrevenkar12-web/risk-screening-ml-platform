import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { CapacityView } from "./features/capacity/CapacityView";
import { LanguagesView } from "./features/languages/LanguagesView";
import { LifecycleView } from "./features/lifecycle/LifecycleView";
import { ReleasesView } from "./features/releases/ReleasesView";
import { Failed, Skeleton } from "./shared/States";
import { useConsole } from "./shared/useConsole";
import "./app.css";

const VIEWS = [
  ["languages", "Languages", LanguagesView],
  ["releases", "Releases", ReleasesView],
  ["lifecycle", "LLM retirement", LifecycleView],
  ["capacity", "Capacity and cost", CapacityView],
] as const;
type Key = (typeof VIEWS)[number][0];
const current = (): Key => (VIEWS.find(([k]) => `#${k}` === window.location.hash)?.[0] ?? "languages") as Key;

export function App() {
  const s = useConsole();
  const [view, setView] = useState<Key>(current());
  useEffect(() => {
    const on = () => setView(current());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const View = VIEWS.find(([k]) => k === view)![2];
  return (
    <div className="shell">
      <header className="bar">
        <p className="brand">Screening platform</p>
        <nav aria-label="Views">
          {VIEWS.map(([k, label]) => (
            <a key={k} href={`#${k}`} aria-current={view === k ? "page" : undefined}>{label}</a>
          ))}
        </nav>
      </header>
      <main className="main">
        {s.kind === "loading" && <Skeleton rows={5} />}
        {s.kind === "error" && <Failed message={s.message} retry={s.retry} />}
        {s.kind === "ready" && (
          <AnimatePresence mode="wait">
            <motion.div key={view} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
              <View data={s.data} />
            </motion.div>
          </AnimatePresence>
        )}
      </main>
    </div>
  );
}
