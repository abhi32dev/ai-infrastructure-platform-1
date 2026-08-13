#!/usr/bin/env python3
import json,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));from ailab.streaming_features import *
def main():
 with tempfile.TemporaryDirectory() as d:
  p=StreamingFeaturePlatform(Path(d)/"s.db",allowed_lateness=10);now=time.time();published=[p.publish(Event(str(i),"u","click",i,now-1)) for i in range(1,4)];consume=p.consume("g",now=now);p.snapshot_offline(now);consistent=p.skew("u",now);duplicate=p.publish(Event("1","u","click",1,now));bad=p.publish(Event("bad","u","click",1,now,99));sc=[{"name":"stream_to_online_features","status":"passed" if p.feature("u")["total_value"]==6 else "failed","evidence":consume},{"name":"online_offline_consistency","status":"passed" if not consistent["skew"] else "failed","evidence":consistent},{"name":"duplicate_and_dlq","status":"passed" if duplicate["status"]=="duplicate" and bad["status"]=="dlq" else "failed","evidence":{"duplicate":duplicate,"bad":bad}}]
 tests=subprocess.run([sys.executable,"-m","pytest","-q","tests/test_streaming_features.py"],cwd=ROOT,text=True,capture_output=True);sc.append({"name":"project_6_tests","status":"passed" if tests.returncode==0 else "failed","stdout":tests.stdout.strip()});passed=sum(x["status"]=="passed" for x in sc);target=ROOT/"artifacts/project-6-streaming-features";target.mkdir(parents=True,exist_ok=True);report={"summary":{"total":len(sc),"passed":passed,"failed":len(sc)-passed},"scenarios":sc};(target/"latest.json").write_text(json.dumps(report,indent=2)+"\n");(target/"latest.txt").write_text(f"Project 6 verification: {passed}/{len(sc)} passed\n");print(f"Project 6 verification: {passed}/{len(sc)} passed");return 0 if passed==len(sc) else 1
if __name__=="__main__":raise SystemExit(main())
