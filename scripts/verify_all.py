#!/usr/bin/env python3
"""Run the entire portfolio and persist a machine-readable completion report."""
from __future__ import annotations
import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERIFIERS=["verify.py","verify_rag_complete.py","verify_agent_runtime.py","verify_model_gateway.py","verify_eval_platform.py","verify_inference_server.py","verify_streaming_features.py","verify_recommendations.py","verify_batch_platform.py","verify_golden_path.py","verify_observability.py","verify_security_guardrails.py","verify_ml_lifecycle.py","verify_protocols.py","verify_expansion_projects.py","verify_staff_controls.py","verify_project_envs.py","verify_pages.py"]
def main():
    scenarios=[]
    for script in VERIFIERS:
        result=subprocess.run([sys.executable,str(ROOT/"scripts"/script)],cwd=ROOT,text=True,capture_output=True)
        scenarios.append({"name":script.removesuffix(".py"),"status":"passed" if result.returncode==0 else "failed","stdout":result.stdout.strip(),"stderr":result.stderr.strip()})
    tests=subprocess.run([sys.executable,"-m","pytest","-q"],cwd=ROOT,text=True,capture_output=True)
    scenarios.append({"name":"full_test_suite","status":"passed" if tests.returncode==0 else "failed","stdout":tests.stdout.strip(),"stderr":tests.stderr.strip()})
    passed=sum(item["status"]=="passed" for item in scenarios)
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"summary":{"total":len(scenarios),"passed":passed,"failed":len(scenarios)-passed},"scenarios":scenarios}
    target=ROOT/"artifacts/completion-audit"; target.mkdir(parents=True,exist_ok=True); (target/"latest.json").write_text(json.dumps(report,indent=2)+"\n"); (target/"latest.txt").write_text(f"Portfolio completion audit: {passed}/{len(scenarios)} passed\n"); print(f"Portfolio completion audit: {passed}/{len(scenarios)} passed"); return int(passed!=len(scenarios))
if __name__=="__main__": raise SystemExit(main())
