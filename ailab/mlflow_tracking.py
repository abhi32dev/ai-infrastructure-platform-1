from __future__ import annotations
from pathlib import Path
from typing import Any

class MLflowTracker:
    """MLflow adapter using a local file store or a production tracking URI."""
    def __init__(self, tracking_uri: str, experiment: str) -> None:
        import mlflow
        self.mlflow = mlflow
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment)
    def log_evaluation(self, candidate: str, version: str, metrics: dict[str, float], config: dict[str, Any], artifact: Path | None = None) -> str:
        with self.mlflow.start_run(run_name=f"{candidate}-{version}") as run:
            self.mlflow.log_params({"candidate": candidate, "version": version, **config})
            self.mlflow.log_metrics(metrics)
            if artifact: self.mlflow.log_artifact(str(artifact))
            self.mlflow.set_tag("release.gate", "evaluation")
            return run.info.run_id
    def read_run(self, run_id: str) -> dict[str, Any]:
        run = self.mlflow.get_run(run_id)
        return {"run_id": run.info.run_id, "params": dict(run.data.params), "metrics": dict(run.data.metrics), "tags": dict(run.data.tags)}
