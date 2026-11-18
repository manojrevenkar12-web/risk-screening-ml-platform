# Held-out protocol

1. The code is final and committed.
2. `make heldout` runs the held-out world once. It writes `reports/heldout.json` and a lock with the commit and
   code fingerprint, and refuses a second run.
3. `make report`; then commit the report, the lock, the README and the console data together.
4. A bad number stays in the README. A fix needs a new held-out world declared here before it is run.

| world | seed | run | result |
|---|---|---|---|
| heldout | 913 | 2026-11-18, once (see `reports/heldout.lock`) | 5 of 7 gates passed; the retirement and SLA gates failed because an escalation with no fallback left the pipeline on a retired LLM |
