#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ailab.eval_platform import Candidate,EvaluationPlatform,GateThresholds,demo_suite,two_proportion_z_test
def good(p):return "checkpoint and idempotency" if "recovery" in p else "lexical and dense" if "retrieval" in p else "cost and fallback"
def main():
 with tempfile.TemporaryDirectory() as d:
  platform=EvaluationPlatform(Path(d)/"e.db");suite=platform.register_suite("core","1",demo_suite())
  good_run=platform.run(suite,Candidate("good","1",good,0.001));promote=platform.gate(good_run,GateThresholds())
  bad_run=platform.run(suite,Candidate("bad","1",lambda p:"generic"));block=platform.gate(bad_run,GateThresholds())
  experiment=two_proportion_z_test(100,1000,140,1000)
  scenarios=[{"name":"quality_release_promoted","status":"passed" if promote["decision"]=="promote" else "failed","evidence":promote},{"name":"regression_blocked","status":"passed" if block["decision"]=="block" else "failed","evidence":block},{"name":"ab_significance","status":"passed" if experiment["statistically_significant"] else "failed","evidence":experiment}]
 tests=subprocess.run([sys.executable,"-m","pytest","-q","tests/test_eval_platform.py"],cwd=ROOT,text=True,capture_output=True);scenarios.append({"name":"project_4_tests","status":"passed" if tests.returncode==0 else "failed","stdout":tests.stdout.strip()})
 passed=sum(x["status"]=="passed" for x in scenarios);report={"generated_at":datetime.now(timezone.utc).isoformat(),"summary":{"total":len(scenarios),"passed":passed,"failed":len(scenarios)-passed},"scenarios":scenarios};target=ROOT/"artifacts/project-4-evaluation";target.mkdir(parents=True,exist_ok=True);(target/"latest.json").write_text(json.dumps(report,indent=2)+"\n");(target/"latest.txt").write_text(f"Project 4 verification: {passed}/{len(scenarios)} passed\n");print(f"Project 4 verification: {passed}/{len(scenarios)} passed");return 0 if passed==len(scenarios) else 1
if __name__=="__main__":raise SystemExit(main())

