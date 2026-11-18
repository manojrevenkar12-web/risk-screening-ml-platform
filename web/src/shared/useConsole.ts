import { useCallback, useEffect, useState } from "react";
import { loadConsole, type Console } from "./data";

export type State = { kind: "loading" } | { kind: "error"; message: string; retry: () => void } | { kind: "ready"; data: Console };

export function useConsole(): State {
  const [s, setS] = useState<State>({ kind: "loading" });
  const run = useCallback(() => {
    setS({ kind: "loading" });
    loadConsole().then((data) => setS({ kind: "ready", data })).catch((e: Error) => setS({ kind: "error", message: e.message, retry: run }));
  }, []);
  useEffect(run, [run]);
  return s;
}
