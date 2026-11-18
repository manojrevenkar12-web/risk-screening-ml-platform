# 6. A held-out market, run once

The dev world (seeds 21–23) is where the dedupe distance, the label floor, the threshold target and the PTU prices
were set. The held-out world (seed 913) changes what can be changed without rewriting the problem:
- six other languages missing from a later export;
- drift in Portuguese instead of Indonesian;
- a retirement on day 33;
- a successor that breaks the format 26% of the time under the old prompt and 3% under the new one;
- more and larger spikes, and more throttling;
- more hard negatives and noisier labels.

It runs once, behind `reports/heldout.lock`.
