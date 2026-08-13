#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess,sys,threading
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ailab.inference_server import *
def main():
 s=BatchedInferenceServer(demo_model(),"v1",8,20,32);results=[];ts=[threading.Thread(target=lambda i=i:results.append(s.infer(InferenceRequest(str(i))))) for i in range(8)];[t.start() for t in ts];[t.join() for t in ts];dynamic={"responses":len(results),"metrics":s.health()["metrics"]};s.shutdown()
 stable=BatchedInferenceServer(demo_model("stable"),"v1",max_batch_wait_ms=0);canary=BatchedInferenceServer(demo_model("canary"),"v2",max_batch_wait_ms=0);d=CanaryDeployment(stable,canary,100);before=d.infer(InferenceRequest("x")).model_version;d.rollback();after=d.infer(InferenceRequest("x2")).model_version;stable.shutdown();canary.shutdown()
 scenarios=[{"name":"dynamic_batching","status":"passed" if dynamic["metrics"]["max_batch_size"]>1 else "failed","evidence":dynamic},{"name":"canary_rollback","status":"passed" if (before,after)==("v2","v1") else "failed","evidence":{"before":before,"after":after}}]
 tests=subprocess.run([sys.executable,"-m","pytest","-q","tests/test_inference_server.py"],cwd=ROOT,text=True,capture_output=True);scenarios.append({"name":"project_5_tests","status":"passed" if tests.returncode==0 else "failed","stdout":tests.stdout.strip()});passed=sum(x["status"]=="passed" for x in scenarios);report={"generated_at":datetime.now(timezone.utc).isoformat(),"summary":{"total":len(scenarios),"passed":passed,"failed":len(scenarios)-passed},"scenarios":scenarios};target=ROOT/"artifacts/project-5-inference-serving";target.mkdir(parents=True,exist_ok=True);(target/"latest.json").write_text(json.dumps(report,indent=2)+"\n");(target/"latest.txt").write_text(f"Project 5 verification: {passed}/{len(scenarios)} passed\n");print(f"Project 5 verification: {passed}/{len(scenarios)} passed");return 0 if passed==len(scenarios) else 1
if __name__=="__main__":raise SystemExit(main())
