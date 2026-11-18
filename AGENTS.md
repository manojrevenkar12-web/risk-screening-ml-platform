# AGENTS.md

How to work in this repository, for people and coding agents alike.

## Fast feedback

| Command | What it does | Time |
|---|---|---|
| `make test` | All tests, including one short platform run | under a minute |
| `make lint` | ruff and mypy | |
| `make eval` | Every design on dev seeds 21, 22, 23 | about 15 min on 2 cores |
| `make report` | README results, charts and the console's data | |
| `make image` | Trains the day-0 model and builds the scorer image | |

Run the narrowest of these that covers your change, then `make test` before you commit.

## Invariants

1. **The truth stays in the world.** Only `world/` knows which documents are real incidents. It also holds what an
   LLM version really does under each prompt and when the cloud throttles.
   - `src/screening` never imports `world` or `evals`, and a test checks this.
   - Outcomes (missed incidents, true recall, SLA, cost) are computed in `evals/` against the truth.
2. **The world does not read the product's settings.** `world/` reads only `config/world.toml` or
   `config/heldout.toml`. Tuning the platform cannot change the luck it is judged on.
3. **Same luck for every design.** Every random draw is a hash of (seed, event). Designs run on the same seeds see
   the same documents, labels, traffic spikes, drift and throttling.
4. **The model reads and code decides.**
   - The LLM's answer counts only if it parses into the schema and every topic is known.
   - A relevance model reaches production only through the gate.
   - A model version changes only through a gated migration. The Terraform deployments say `NoAutoUpgrade`.
5. **Every language counts on its own.** Recall is gated per language on intervals. A language without enough
   labelled incidents to judge holds the release.
6. **A label export is checked before anything trains on it.** A language that comes back short is a broken
   export, not a quiet language.
7. **Settings in config.** Thresholds, prices, quotas, budgets and SLAs live in `config/platform.toml`. A test fails
   on a bare decimal threshold in the deciding modules.
8. **Generated reports.** `reports/*.json`, the README results section, `docs/charts` and `web/public/console.json`
   are written by `evals/`. Never edit them by hand.

## The held-out rule

`config/heldout.toml` describes a different market:
- other languages missing from the retraining export;
- drift in Portuguese;
- an earlier retirement, with a successor that breaks the format more often;
- more news spikes and more throttling.

Nobody tunes on it. When the code is final, `make heldout` runs it once and writes `reports/heldout.lock`; a second
run refuses. The numbers are reported as they come. To claim a fix afterwards, you need a new held-out world
declared in `docs/heldout.md` before it is run.
