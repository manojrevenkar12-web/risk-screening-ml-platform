"""Release records in MLflow. An Azure ML workspace is an MLflow tracking server, so the same calls write to Azure ML
in production (MLFLOW_TRACKING_URI from the workspace) and to a local folder in development. Nothing is logged unless
MLFLOW_TRACKING_URI is set, which keeps the evaluations fast."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def log_release(version: str, day: int, trigger: str, promoted: bool, reasons: list[str], params: dict[str, Any],
                per_language: dict[str, Any], artefact: Path | None = None) -> str | None:
    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not uri:
        return None
    import mlflow

    mlflow.set_tracking_uri(uri)
    name = "relevance-releases"
    if mlflow.get_experiment_by_name(name) is None:
        mlflow.create_experiment(name, artifact_location=os.environ.get("MLFLOW_ARTIFACT_LOCATION"))
    mlflow.set_experiment(name)
    with mlflow.start_run(run_name=version) as run:
        mlflow.set_tags({"trigger": trigger, "decision": "promoted" if promoted else "held", "day": str(day)})
        mlflow.log_params({k: str(v) for k, v in params.items()})
        for lang, r in per_language.items():
            mlflow.log_metric(f"recall_{lang}", float(r.recall[0]))
            mlflow.log_metric(f"harmless_pass_{lang}", float(r.fpr[0]))
            mlflow.log_metric(f"threshold_{lang}", float(r.threshold))
        mlflow.log_text("\n".join(reasons), "gate.txt")
        if artefact is not None and artefact.exists():
            mlflow.log_artifact(str(artefact), "model")
            meta = artefact.with_suffix(".json")
            if meta.exists():
                mlflow.log_artifact(str(meta), "model")
        return str(run.info.run_id)
