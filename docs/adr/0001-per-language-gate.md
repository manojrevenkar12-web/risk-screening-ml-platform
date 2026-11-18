# 1. Gate relevance models per language, as paired comparisons

## Context
English is 36% of the volume, and thirty languages share one model. An aggregate F1 that rises can hide five
languages whose recall fell, because their documents are a few percent of the golden sets.

## Decision
Each language is judged on its own test half of the golden set (300 incidents). Both models read the same incidents,
so the comparison is paired: count the incidents one model catches and the other misses.

A candidate fails if any of these holds:
- **A language drops.** It misses more than 2 points more of a language's incidents than the champion, and the sign
  test on the discordant incidents is significant after Holm's correction across the 30 languages.
- **A language is below the floor.** Even the upper end of a language's recall interval is under 0.85.
- **It costs more.** The volume-weighted share of harmless documents it passes to the LLM rises by more than
  3 points.

A language with fewer than 40 labelled incidents to judge holds the release.

## Consequences
- The paired test with Holm's correction sees a 5-point drop in one language without holding releases that changed
  nothing.
- Independent intervals per language, the first version of this gate, let a 5.5-point drop in Italian through on
  dev seed 22.
- Golden sets cost analyst time: 600 incidents and 600 random documents per language.
