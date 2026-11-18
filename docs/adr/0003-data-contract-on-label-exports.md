# 3. Check the label export before training

## Context
An export job that drops languages looks like a normal export: rows arrive, training succeeds, and the aggregate
metrics move by a fraction of a point.

## Decision
- Before a retrain, compare labels received per language with labels requested.
- A language under half its request is a broken export: record it and request that language again.
- Train on everything learned so far plus the new export, not on the newest export alone.

## Consequences
On dev, the day-14 export lacks th, sw, tl, he and el. The platform re-requests them, and the retrained model passes
the gate.
