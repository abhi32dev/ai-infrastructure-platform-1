#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PROJECTS=[("14-distributed-training","tests/test_distributed_training.py","ailab.distributed_training_cli"),("15-optimized-inference","tests/test_llm_inference_optimized.py","ailab.llm_inference_cli"),("16-gpu-platform","tests/test_gpu_platform.py","ailab.gpu_platform_cli"),("17-lakehouse-features","tests/test_lakehouse_features.py","ailab.lakehouse_cli"),("18-distributed-orchestration","tests/test_distributed_orchestration.py","ailab.orchestration_cli"),("19-multi-framework","tests/test_multi_framework.py","ailab.multi_framework_cli"),("20-cloud-control-plane","tests/test_cloud_control_plane.py","ailab.cloud_control_cli")]
def main():
 all_passed=True
 for name,test,cli in PROJECTS:
  tests=subprocess.run([sys.executable,"-m","pytest","-q",test],cwd=ROOT,text=True,capture_output=True);demo=subprocess.run([sys.executable,"-m",cli],cwd=ROOT,text=True,capture_output=True);scenarios=[{"name":"edge_case_suite","status":"passed" if tests.returncode==0 else "failed","stdout":tests.stdout.strip(),"stderr":tests.stderr.strip()},{"name":"runnable_demo","status":"passed" if demo.returncode==0 else "failed","stdout":demo.stdout.strip(),"stderr":demo.stderr.strip()}];passed=sum(x["status"]=="passed" for x in scenarios);report={"generated_at":datetime.now(timezone.utc).isoformat(),"summary":{"total":2,"passed":passed,"failed":2-passed},"scenarios":scenarios};target=ROOT/"artifacts"/f"project-{name}";target.mkdir(parents=True,exist_ok=True);(target/"latest.json").write_text(json.dumps(report,indent=2)+"\n");(target/"latest.txt").write_text(f"Project {name} verification: {passed}/2 passed\n");print(f"Project {name}: {passed}/2 passed");all_passed &= passed==2
 return int(not all_passed)
if __name__=="__main__":raise SystemExit(main())
