# 2. A label floor for small languages, and per-language thresholds

## Context
Labelling by volume gives Swahili 0.4% of the budget: about 150 documents and 10 incidents, too few to learn from.
A single threshold of 0.5 then misses most incidents in small languages.

## Decision
- Every language gets at least 700 labels per round, paid for by the largest languages.
- For floored languages, analysts label documents the model flagged first, so about 30% of what they label is an
  incident.
- Each language's threshold is the highest that keeps 94% recall on its calibration golden set.

## Consequences
- Small languages pass more harmless documents to the LLM. That cost is gated in aggregate (ADR 1) and priced in the
  cost per 1,000 documents.
- English gets a higher threshold than 0.5, which cuts its harmless pass rate.
