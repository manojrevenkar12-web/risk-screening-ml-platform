"""Who may call which LLM deployment, how fast, and at what cost: Entra ID groups mapped to policies.

The production screening pipeline has its own deployment and no budget cap; analyst tools and developers share
smaller deployments with per-minute token quotas and monthly budgets. A request is checked before it is sent and
accounted after; a refused request says why.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Verdict:
    allowed: bool
    reason: str


@dataclass
class Gateway:
    policies: dict[str, dict[str, Any]]
    eur_per_1k_tokens: float
    spent: dict[str, float] = field(default_factory=dict)
    minute_tokens: dict[tuple[str, int], int] = field(default_factory=dict)

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> Gateway:
        return cls(dict(cfg["teams"]), float(cfg["llm"]["eur_per_1k_tokens"]))

    def check(self, groups: list[str], deployment: str, tokens: int, minute: int) -> Verdict:
        mine = [g for g in groups if g in self.policies and deployment in self.policies[g]["deployments"]]
        if not mine:
            return Verdict(False, f"none of your groups may call {deployment}")
        g = mine[0]
        p = self.policies[g]
        tpm = int(p["tokens_per_minute"])
        if tpm and self.minute_tokens.get((g, minute), 0) + tokens > tpm:
            return Verdict(False, f"{g} is over its {tpm} tokens per minute")
        budget = float(p["monthly_budget_eur"])
        if budget and self.spent.get(g, 0.0) + tokens / 1000 * self.eur_per_1k_tokens > budget:
            return Verdict(False, f"{g} has used its monthly budget of EUR {budget:.0f}")
        return Verdict(True, g)

    def account(self, group: str, tokens: int, minute: int) -> None:
        self.minute_tokens[(group, minute)] = self.minute_tokens.get((group, minute), 0) + tokens
        self.spent[group] = self.spent.get(group, 0.0) + tokens / 1000 * self.eur_per_1k_tokens
