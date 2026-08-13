from pathlib import Path
import pytest
pytest.importorskip("mlflow")
from ailab.mlflow_tracking import MLflowTracker

def test_mlflow_local_tracking(tmp_path: Path):
    tracker=MLflowTracker((tmp_path/"mlruns").as_uri(), "release-eval")
    run_id=tracker.log_evaluation("candidate","v1",{"quality":.92},{"suite":"core-v1"})
    run=tracker.read_run(run_id)
    assert run["metrics"]["quality"] == .92 and run["params"]["suite"] == "core-v1"
