#!/usr/bin/env python3
import json,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));from ailab.observability import *
def main():
 with tempfile.TemporaryDirectory() as d:
  t=Telemetry(Path(d)/"o.db");now=time.time()
  with t.span("a2a.send_message") as span:t.log("INFO","guardrail allowed",span["trace_id"],policy="tool_allowlist")
  [t.request("agent",i<80,20+i,cost=.001,tokens_in=50,tokens_out=10,timestamp=now) for i in range(100)];budget=t.error_budget(SLO("agent",.99,3600),now);alert=t.multi_window_burn_alert(SLO("agent",.99,3600),300,3600,now=now);timeline=t.timeline(span["trace_id"]);sc=[{"name":"correlated_trace","status":"passed" if len(timeline)==2 else "failed","evidence":timeline},{"name":"slo_burn_alert","status":"passed" if alert["sent"] and budget["budget_consumed_ratio"]>1 else "failed","evidence":{"budget":budget,"alert":alert}},{"name":"cost_attribution","status":"passed" if t.cost_breakdown()["total"]>0 else "failed","evidence":t.cost_breakdown()}]
 tests=subprocess.run([sys.executable,"-m","pytest","-q","tests/test_observability.py"],cwd=ROOT,text=True,capture_output=True);sc.append({"name":"project_10_tests","status":"passed" if tests.returncode==0 else "failed","stdout":tests.stdout.strip(),"stderr":tests.stderr.strip()});passed=sum(x["status"]=="passed" for x in sc);dest=ROOT/"artifacts/project-10-observability";dest.mkdir(parents=True,exist_ok=True);(dest/"latest.json").write_text(json.dumps({"summary":{"total":len(sc),"passed":passed,"failed":len(sc)-passed},"scenarios":sc},indent=2)+"\n");(dest/"latest.txt").write_text(f"Project 10 verification: {passed}/{len(sc)} passed\n");print(f"Project 10 verification: {passed}/{len(sc)} passed");return 0 if passed==len(sc) else 1
if __name__=="__main__":raise SystemExit(main())
