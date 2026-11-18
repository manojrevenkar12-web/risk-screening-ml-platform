"""How many scorer replicas run each hour, and how much provisioned LLM throughput to buy.

fixed_average and fixed_peak are what a team sets by hand; lag scales on the Event Hubs consumer lag the way the
KEDA ScaledObject in deploy/k8s does, and pays a few minutes of reaction time on every rise.
"""

from __future__ import annotations

import math
from typing import Any


def fixed_replicas(hourly_forecast: list[float], cfg: dict[str, Any]) -> int:
    s = cfg["scorer"]
    per_hour = float(s["docs_per_second_per_replica"]) * 3600
    if s["policy"] == "fixed_peak":
        need = max(hourly_forecast)
    else:
        need = sum(hourly_forecast) / len(hourly_forecast)
    return max(int(s["min_replicas"]), math.ceil(need / per_hour))


def lag_replicas(arrivals_per_hour: float, backlog: float, cfg: dict[str, Any]) -> int:
    """Replicas KEDA settles on: enough to drain the backlog within the target lag while keeping up with arrivals."""
    s = cfg["scorer"]
    per_sec = float(s["docs_per_second_per_replica"])
    need = arrivals_per_hour / 3600 / per_sec + backlog / max(1.0, float(s["target_lag_seconds"])) / per_sec
    return int(min(int(s["max_replicas"]), max(int(s["min_replicas"]), math.ceil(need))))


def ptu_units(hourly_tokens: list[float], cfg: dict[str, Any]) -> int:
    """Provisioned throughput units. ptu_peak: enough for the busiest forecast hour. ptu_spillover: the number that
    minimises provisioned cost plus pay-as-you-go cost for what spills over, on the forecast."""
    llm = cfg["llm"]
    if llm["capacity"] == "payg":
        return 0
    if int(llm["ptu_units"]) > 0:
        return int(llm["ptu_units"])
    per_unit_hour = float(llm["ptu_tokens_per_minute"]) * 60
    if llm["capacity"] == "ptu_peak":
        return max(1, math.ceil(max(hourly_tokens) / per_unit_hour))
    payg = float(llm["eur_per_1k_tokens"]) / 1000
    unit_cost = float(llm["ptu_eur_per_hour"])

    def cost(units: int) -> float:
        cap = units * per_unit_hour
        return sum(unit_cost * units + max(0.0, t - cap) * payg for t in hourly_tokens)

    top = math.ceil(max(hourly_tokens) / per_unit_hour)
    return min(range(top + 1), key=cost)
