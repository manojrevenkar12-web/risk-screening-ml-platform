"""The relevance scorer as it runs on AKS: an ONNX model, per-language thresholds, Prometheus metrics.

    MODEL_DIR=artefacts MODEL_VERSION=relevance-d00-... uvicorn screening.serving.app:app

The image holds no training code. A request carries a language and texts; the answer is a score and a decision per
text. The threshold file ships next to the model, so a release changes both together or neither.
"""

from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

app = FastAPI(title="relevance scorer", version="1.0.0")
SCORED = Counter("screening_documents_scored_total", "Documents scored", ["language", "decision"])
LATENCY = Histogram("screening_score_seconds", "Scoring latency per request")
MAX_BATCH = int(os.environ.get("MAX_BATCH", "256"))


class Batch(BaseModel):
    language: str = Field(min_length=2, max_length=8)
    texts: list[str] = Field(min_length=1)


class Loaded:
    def __init__(self, model_dir: Path, version: str):
        import onnxruntime as ort

        meta = json.loads((model_dir / f"{version}.json").read_text())
        self.version = version
        self.thresholds: dict[str, float] = meta["thresholds"]
        self.default = float(meta["default_threshold"])
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = int(os.environ.get("ORT_THREADS", "2"))
        self.session = ort.InferenceSession(str(model_dir / f"{version}.onnx"), opts,
                                            providers=["CPUExecutionProvider"])
        self.output = self.session.get_outputs()[1].name

    def scores(self, texts: list[str]) -> np.ndarray:
        x = np.array(texts, dtype=object).reshape(-1, 1)
        return np.asarray(self.session.run([self.output], {"text": x})[0])[:, 1]


@lru_cache
def model() -> Loaded:
    d = Path(os.environ.get("MODEL_DIR", "artefacts"))
    v = os.environ.get("MODEL_VERSION") or sorted(p.stem for p in d.glob("*.onnx"))[-1]
    return Loaded(d, v)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    m = model()
    return {"ok": True, "version": m.version, "languages": len(m.thresholds)}


@app.post("/score")
def score(batch: Batch) -> dict[str, Any]:
    if len(batch.texts) > MAX_BATCH:
        raise HTTPException(413, f"at most {MAX_BATCH} texts per request")
    m = model()
    t = time.perf_counter()
    s = m.scores(batch.texts)
    th = m.thresholds.get(batch.language, m.default)
    LATENCY.observe(time.perf_counter() - t)
    out = []
    for v in s:
        decision = "pass" if v >= th else "drop"
        SCORED.labels(batch.language, decision).inc()
        out.append({"score": round(float(v), 5), "decision": decision})
    return {"version": m.version, "threshold": th, "results": out}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)
