# SKILLS.md

## Release a relevance model
1. `Platform._release` trains on the checked label export and fits per-language thresholds on the calibration half
   of the golden sets.
2. The gate judges the model on the test half (`screening/models/gate.py`).
3. A promoted model is exported to ONNX with its thresholds (`export_onnx`).
4. Build the image with `make image` and deploy `deploy/k8s/overlays/canary`.
5. Watch `screening_documents_scored_total` per language and the latency histogram for an hour.
6. Point the stable track at the new version.

## Add a language
1. Add it to the traffic in the world config.
2. Make sure the label allocation gives it the floor (`labels.min_per_language`).
3. Collect a golden set of at least `gate.min_golden_incidents` incidents. Without one, the gate holds every release
   that would change the language.

## Prepare for an LLM retirement
`lifecycle.lead_days` before the date, the platform evaluates the successor under every prompt in
`lifecycle.prompts`:
- If a prompt keeps the format and the accuracy, it migrates early.
- If none does, it escalates with the date.

To add a prompt, add it to `screening/llm/tagging.py` and to `lifecycle.prompts`, then rerun `make eval`.

## Resize LLM capacity
`screening/capacity/autoscale.py:ptu_units` picks the cost-optimal number of provisioned units for a demand forecast.
Set the result as `ptu_units` in the Terraform variables. Spillover runs on pay-as-you-go in two regions.

## Give a team access to an LLM deployment
1. Add the Entra ID group to `[teams]` in `config/platform.toml` with its deployments, per-minute tokens and monthly
   budget.
2. Add it to `team_groups` in Terraform.

People never get the OpenAI role directly; the gateway's identity holds it.

## Run the held-out world
Run `make heldout`, once. Then run `make report` and commit the report, the lock, the README and the console data
together.
