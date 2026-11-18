"""The control loop end to end on a short world, and the evaluations' plumbing."""

import pytest

from evals import run as evalrun
from evals.operate import bad_promotions, drift_detection_days, operate
from screening.capacity.autoscale import lag_replicas, ptu_units
from screening.config import gates, settings
from screening.lifecycle.retirement import plan
from screening.monitoring.drift import check, histogram


@pytest.fixture(scope="module")
def platform_run(short_world):
    cfg = settings()
    return evalrun.run_platform(short_world, cfg), cfg


def test_the_platform_repairs_the_broken_export_and_ships_no_worse_model(platform_run, short_world):
    p, _ = platform_run
    assert p.state.breaches and all(b.repaired for b in p.state.breaches)
    assert set(p.state.breaches[0].languages) == set(short_world.cfg["data_feed"]["missing_languages_in_retrain"])
    assert bad_promotions(short_world, p) == []


def test_drift_is_noticed_within_days_and_answered_with_labels(platform_run, short_world):
    p, _ = platform_run
    assert drift_detection_days(short_world, p) <= 3
    assert any(r.trigger.startswith("drift") for r in p.state.releases)


def test_the_llm_moves_to_the_successor_before_the_retirement_with_the_prompt_that_parses(platform_run):
    p, _ = platform_run
    mig = p.state.migrations[0]
    assert mig.chosen_prompt == "v2" and mig.decided_day < mig.retires_day
    assert p.state.llm_by_day[max(p.state.llm_by_day)] == (mig.successor, "v2")


def test_the_operations_meet_the_sla_and_the_cost_gate(platform_run, short_world):
    p, cfg = platform_run
    m = operate(short_world, p, cfg)
    assert m["sla_breach_share"] <= gates()["sla"]["threshold"]
    assert m["eur_per_1k_documents"] <= gates()["cost"]["threshold"]
    assert m["degraded_tagging_days"] == 0


def test_auto_upgrade_breaks_tagging_on_the_retirement_day(short_world):
    cfg = settings({"lifecycle": {"mode": "auto_upgrade"}})
    p = evalrun.run_platform(short_world, cfg)
    m = operate(short_world, p, cfg)
    assert m["degraded_tagging_days"] >= 1 and m["untagged_share"] > 0


def test_drift_check_on_a_shifted_distribution():
    import numpy as np

    edges = settings()["drift"]["bins"]
    ref = histogram(np.random.default_rng(1).beta(1, 8, 2000), edges)
    same = histogram(np.random.default_rng(2).beta(1, 8, 600), edges)
    moved = histogram(np.random.default_rng(3).beta(1, 2, 600), edges)
    assert check("x", 1, ref, same, 0.02, 0.02, 0.2, 0.35) is None
    assert check("x", 1, ref, moved, 0.02, 0.02, 0.2, 0.35) is not None
    assert check("x", 1, ref, same, 0.02, 0.05, 0.2, 0.35) is not None


def test_capacity_planning():
    cfg = settings()
    assert lag_replicas(10_000, 0, cfg) == cfg["scorer"]["min_replicas"]
    assert lag_replicas(10 * 3600 * cfg["scorer"]["docs_per_second_per_replica"], 0, cfg) == 10
    hours = [10e6] * 20 + [60e6] * 4
    assert ptu_units(hours, settings({"llm": {"capacity": "payg"}})) == 0
    peak = ptu_units(hours, settings({"llm": {"capacity": "ptu_peak"}}))
    spill = ptu_units(hours, cfg)
    assert 0 < spill < peak


def test_no_successor_or_no_passing_prompt_goes_to_a_person():
    cat = [{"model": "old", "retires_day": 30}]
    cfg = settings()
    p = plan(cat, "old", "v1", 10, lambda m, pr, d: ('{"topics": []}', 10), [], cfg)
    assert p is not None and p.escalated
    cat.append({"model": "new", "retires_day": 300})
    bad = plan(cat, "old", "v1", 10, lambda m, pr, d: ("garbage" if m == "new" else '{"topics": []}', 10),
               [type("D", (), {"topics": ()})()] * 5, cfg)
    assert bad is not None and bad.escalated and bad.chosen_prompt is None
    assert plan(cat, "old", "v1", 5, lambda *a: ("", 0), [], cfg) is None      # too early


def test_the_held_out_world_runs_once(tmp_path, monkeypatch):
    monkeypatch.setattr(evalrun, "REPORTS", tmp_path)
    (tmp_path / "heldout.lock").write_text("run before\n")
    assert evalrun.main(["--heldout"]) == 2
