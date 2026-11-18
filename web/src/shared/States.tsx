import type { ReactNode } from "react";
import "./states.css";

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => <span key={i} style={{ width: `${90 - i * 18}%` }} />)}
    </div>
  );
}

export function Failed({ message, retry }: { message: string; retry: () => void }) {
  return (
    <div className="failed" role="alert">
      <p>The console could not read its data: {message}.</p>
      <p className="muted small">Run <code>make report</code> to write web/public/console.json, then reload.</p>
      <button className="btn" onClick={retry}>Try again</button>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}
