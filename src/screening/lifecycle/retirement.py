"""Model-version retirements. Cloud LLM versions retire on announced dates; on that date the platform upgrades the
deployment to the successor, with whatever the successor does to the prompt's output format.

gated_migration: lead_days before a retirement, run every prompt variant on the successor against the analysts'
topic golden set; migrate early to the first variant that keeps the format and the tagging accuracy, or escalate to a
person with the date if none does. auto_upgrade: let the cloud switch on the retirement day (the status quo).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from screening.llm.tagging import parse


@dataclass
class VariantResult:
    model: str
    prompt: str
    format_ok: float
    tag_accuracy: float
    tokens: int


@dataclass
class MigrationPlan:
    retiring: str
    successor: str
    retires_day: int
    decided_day: int
    chosen_prompt: str | None
    results: list[VariantResult] = field(default_factory=list)
    escalated: bool = False
    note: str = ""


def evaluate(call: Callable[[str, str, Any], tuple[str | None, int]], model: str, prompt: str,
             golden: list[Any]) -> VariantResult:
    ok = right = tokens = 0
    for doc in golden:
        raw, t = call(model, prompt, doc)
        tokens += t
        topics = parse(raw)
        if topics is None:
            continue
        ok += 1
        right += int(topics == sorted(set(doc.topics)))
    n = max(1, len(golden))
    return VariantResult(model, prompt, ok / n, right / max(1, ok), tokens)


def plan(catalog: list[dict[str, Any]], current: str, current_prompt: str, day: int,
         call: Callable[[str, str, Any], tuple[str | None, int]], golden: list[Any],
         cfg: dict[str, Any]) -> MigrationPlan | None:
    lc = cfg["lifecycle"]
    mine = next((m for m in catalog if m["model"] == current), None)
    if mine is None or day < int(mine["retires_day"]) - int(lc["lead_days"]):
        return None
    successors = sorted((m for m in catalog if m["retires_day"] > mine["retires_day"]), key=lambda m: m["model"])
    if not successors:
        return MigrationPlan(current, "", int(mine["retires_day"]), day, None, [], True, "no successor announced")
    succ = successors[-1]["model"]
    base = evaluate(call, current, current_prompt, golden)
    results = [base]
    for prompt in lc["prompts"]:
        r = evaluate(call, succ, prompt, golden)
        results.append(r)
        if r.format_ok >= float(lc["min_format_ok"]) and \
                r.tag_accuracy - base.tag_accuracy >= float(lc["min_tag_accuracy_delta"]):
            return MigrationPlan(current, succ, int(mine["retires_day"]), day, prompt, results,
                                 False, f"{succ} with prompt {prompt}")
    return MigrationPlan(current, succ, int(mine["retires_day"]), day, None, results, True,
                         "no prompt keeps format and accuracy; a person decides before the retirement date")
