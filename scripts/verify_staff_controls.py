#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from ailab.golden_path import GoldenPath, ServiceConfig
def run(name, command):
    result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    return {"name":name,"status":"passed" if result.returncode==0 else "failed","command":" ".join(map(str,command)),"stdout":result.stdout.strip(),"stderr":result.stderr.strip()}
def main():
    scenarios=[]; controls=json.loads((ROOT/"config/project-controls.json").read_text()); categories={"guardrails","evals","observability","cost","protocols"}
    complete=len(controls)==13 and all(categories == set(value) and all(value[key] for key in categories) for value in controls.values())
    scenarios.append({"name":"all_projects_have_cross_cutting_controls","status":"passed" if complete else "failed","evidence":{"projects":len(controls)}})
    scenarios += [run("fastapi_openai_contract",[str(ROOT/"projects/project-03-model-gateway/.venv/bin/python"),"-m","pytest","-q","tests/test_gateway_api.py"]),run("multi_judge_and_mlflow",[str(ROOT/"projects/project-04-evaluation/.venv/bin/python"),"-m","pytest","-q","tests/test_production_adapters.py","tests/test_mlflow_tracking.py"]),run("otel_prometheus",[str(ROOT/"projects/project-10-observability/.venv/bin/python"),"-m","pytest","-q","tests/test_native_telemetry.py"]),run("chaos_security_rollback",[sys.executable,"-m","pytest","-q","tests/test_model_gateway.py","tests/test_security_guardrails.py","tests/test_inference_server.py"])]
    with tempfile.TemporaryDirectory() as temporary:
        target=GoldenPath().generate(Path(temporary),ServiceConfig("staff-ai-service",18080)); validation=GoldenPath().validate(target)
        scenarios.append({"name":"kubernetes_policy_validation","status":"passed" if validation["valid"] else "failed","evidence":validation}); scenarios.append(run("docker_compose_config",["docker","compose","-f",str(target/"compose.yaml"),"config"]))
    passed=sum(x["status"]=="passed" for x in scenarios); report={"generated_at":datetime.now(timezone.utc).isoformat(),"summary":{"total":len(scenarios),"passed":passed,"failed":len(scenarios)-passed},"scenarios":scenarios}; target=ROOT/"artifacts/staff-controls"; target.mkdir(parents=True,exist_ok=True); (target/"latest.json").write_text(json.dumps(report,indent=2)+"\n"); (target/"latest.txt").write_text(f"Staff controls verification: {passed}/{len(scenarios)} passed\n"); print(f"Staff controls verification: {passed}/{len(scenarios)} passed"); return int(passed!=len(scenarios))
if __name__=="__main__": raise SystemExit(main())
