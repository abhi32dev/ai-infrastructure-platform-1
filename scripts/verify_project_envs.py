#!/usr/bin/env python3
"""Verify project environments import installed snapshots, not repository source."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = {
    "project-01-rag": ("ailab.rag", "ailab.cli"),
    "project-02-agent-runtime": ("ailab.agent_runtime", "ailab.agent_cli"),
    "project-03-model-gateway": ("ailab.model_gateway", "ailab.gateway_cli"),
    "project-04-evaluation": ("ailab.eval_platform", "ailab.eval_cli"),
    "project-05-inference-serving": ("ailab.inference_server", "ailab.inference_cli"),
    "project-06-streaming-features": ("ailab.streaming_features", "ailab.streaming_cli"),
    "project-07-recommendations": ("ailab.recommendations", "ailab.recommendation_cli"),
    "project-08-batch-platform": ("ailab.batch_platform", "ailab.batch_cli"),
    "project-09-golden-path": ("ailab.golden_path", "ailab.golden_path_cli"),
    "project-10-observability": ("ailab.observability", "ailab.observability_cli"),
}


def main() -> int:
    results = []
    for name, (module, cli) in PROJECTS.items():
        project = ROOT / "projects" / name
        python = project / ".venv" / "bin" / "python"
        manifest = project / "environment-manifest.json"
        freeze = project / "installed-freeze.txt"
        command = [str(python), "-c", f"import json,{module}; print(json.dumps({{'module_path':{module}.__file__}}))"]
        process = subprocess.run(command, cwd="/tmp", text=True, capture_output=True)
        cli_process = subprocess.run([str(python), "-m", cli, "--help"], cwd="/tmp", text=True, capture_output=True)
        module_path = json.loads(process.stdout)["module_path"] if process.returncode == 0 else ""
        passed = process.returncode == 0 and cli_process.returncode == 0 and "/.venv/" in module_path and manifest.exists() and freeze.exists()
        results.append({"project": name, "status": "passed" if passed else "failed", "module_path": module_path, "cli_exit_code": cli_process.returncode, "manifest_exists": manifest.exists(), "freeze_exists": freeze.exists(), "stderr": process.stderr or cli_process.stderr})
    passed = sum(row["status"] == "passed" for row in results)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "summary": {"total": len(results), "passed": passed, "failed": len(results)-passed}, "projects": results}
    target = ROOT / "artifacts" / "environment-isolation"
    target.mkdir(parents=True, exist_ok=True)
    (target / "latest.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [f"Environment isolation: {passed}/{len(results)} passed", *[f"[{row['status'].upper()}] {row['project']}: {row['module_path']}" for row in results]]
    (target / "latest.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
