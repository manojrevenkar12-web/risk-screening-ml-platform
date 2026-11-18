import os

import numpy as np

from screening.config import settings
from screening.models import gate
from screening.models.relevance import allocate, export_onnx, fit_thresholds, train


def small_training(world, cfg, purpose="train", scale=4):
    docs = []
    for lang, (n, enrich) in allocate(world.shares, cfg).items():
        docs += world.labelled(lang, max(60, n // scale), purpose, relevant_share=enrich)
    return docs


def golden(world, n=120):
    return {lang: world.labelled(lang, n, "golden", relevant_share=1.0) + world.labelled(lang, 2 * n, "golden_random")
            for lang in world.shares}


def test_the_floor_moves_labels_to_small_languages_within_the_same_budget(world):
    cfg = settings()
    prop = allocate(world.shares, settings({"labels": {"allocation": "proportional"}}))
    floor = allocate(world.shares, cfg)
    budget = cfg["labels"]["budget_per_round"]
    assert abs(sum(n for n, _ in floor.values()) - budget) < 0.02 * budget
    assert floor["sw"][0] == cfg["labels"]["min_per_language"] > prop["sw"][0]
    assert floor["sw"][1] == cfg["labels"]["enrich_relevant_share"] and floor["en"][1] is None


def test_each_language_gets_the_threshold_that_keeps_its_recall(world):
    cfg = settings()
    m = train(small_training(world, cfg), cfg, "t")
    gold = golden(world)
    fit_thresholds(m, gold, cfg)
    assert len({round(t, 3) for t in m.thresholds.values()}) > 10
    for lang, docs in gold.items():
        pos = [d.text for d in docs if d.label]
        assert np.mean(m.scores(pos) >= m.threshold(lang)) >= cfg["thresholds"]["target_recall"]


def test_the_onnx_artefact_scores_like_the_trained_model(world, tmp_path):
    cfg = settings()
    m = train(small_training(world, cfg, scale=8), cfg, "relevance-onnx")
    export_onnx(m, tmp_path)
    os.environ["MODEL_DIR"] = str(tmp_path)
    os.environ["MODEL_VERSION"] = "relevance-onnx"
    from screening.serving import app as serving

    serving.model.cache_clear()
    texts = [d.text for d in world.truth_sample("fr", 200)]
    assert np.abs(m.scores(texts) - serving.model().scores(texts)).max() < 1e-5


def test_the_scorer_api_answers_per_language(world, tmp_path):
    from fastapi.testclient import TestClient

    from screening.serving import app as serving

    cfg = settings()
    m = train(small_training(world, cfg, scale=8), cfg, "relevance-api")
    m.thresholds = {"de": 0.2}
    export_onnx(m, tmp_path)
    os.environ["MODEL_DIR"] = str(tmp_path)
    os.environ["MODEL_VERSION"] = "relevance-api"
    serving.model.cache_clear()
    c = TestClient(serving.app)
    assert c.get("/healthz").json()["version"] == "relevance-api"
    r = c.post("/score", json={"language": "de", "texts": ["a b c", "d e f"]}).json()
    assert r["threshold"] == 0.2 and len(r["results"]) == 2
    assert c.post("/score", json={"language": "de", "texts": ["x"] * 300}).status_code == 413
    assert "screening_documents_scored_total" in c.get("/metrics").text


def test_a_model_trained_without_five_languages_fails_the_per_language_gate_but_not_the_aggregate(world):
    cfg = settings()
    champ = train(small_training(world, cfg), cfg, "champ")
    gold = golden(world)
    cal = {k: v[0::2] for k, v in gold.items()}
    test = {k: v[1::2] for k, v in gold.items()}
    fit_thresholds(champ, cal, cfg)
    gapped = [d for d in small_training(world, cfg, "retrain")]       # the world's export drops five languages
    cand = train(gapped, cfg, "cand")
    fit_thresholds(cand, cal, settings({"thresholds": {"mode": "global"}}))
    per_language = gate.decide(cand, champ, test, cfg, world.shares)
    assert not per_language.promote
    missing = world.cfg["data_feed"]["missing_languages_in_retrain"]
    assert any(lang in " ".join(per_language.reasons) for lang in missing)
    aggregate = gate.decide(cand, champ, test, settings({"gate": {"mode": "aggregate"}}), world.shares)
    assert aggregate.mode == "aggregate"


def test_a_release_is_recorded_in_mlflow_when_a_tracking_server_is_set(world, tmp_path, monkeypatch):
    from screening.models.gate import report
    from screening.models.registry import log_release

    cfg = settings()
    m = train(small_training(world, cfg, scale=8), cfg, "relevance-mlflow")
    path = export_onnx(m, tmp_path / "art")
    assert log_release("v", 0, "initial", True, ["first model"], {}, {}) is None      # nothing without a server
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path / 'mlflow.db'}")
    monkeypatch.setenv("MLFLOW_ARTIFACT_LOCATION", str(tmp_path / "mlruns"))
    run_id = log_release(m.version, 0, "initial", True, ["first model"], {"labels": "floor"},
                         report(m, golden(world, 50)), path)
    assert run_id and any((tmp_path / "mlruns").rglob("*.onnx"))
