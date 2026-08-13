#!/usr/bin/env python3
import json,subprocess,sys,tempfile
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));from ailab.batch_platform import *
def main():
 with tempfile.TemporaryDirectory() as d:
  p=SelfHealingBatchPlatform(Path(d)/"b.db",500,3,4);items=[WorkItem(str(i),str(i),100) for i in range(8)];calls=Counter()
  def worker(x):calls[x.id]+=1;
  def work(x):
   calls[x.id]+=1
   if x.id=="3" and calls[x.id]==1:raise RuntimeError("injected")
   return x.payload
  result=p.execute(items,work);p.db.execute("DELETE FROM outputs WHERE item_id='5'");p.db.commit();repair=p.reconcile(result["run_id"],items,work);sc=[{"name":"adaptive_execution","status":"passed" if result["status"]=="completed" else "failed","evidence":result},{"name":"transient_retry","status":"passed" if calls["3"]==2 else "failed","evidence":{"calls":dict(calls)}},{"name":"storage_reconciliation","status":"passed" if not repair["missing"] else "failed","evidence":repair}]
 tests=subprocess.run([sys.executable,"-m","pytest","-q","tests/test_batch_platform.py"],cwd=ROOT,text=True,capture_output=True);sc.append({"name":"project_8_tests","status":"passed" if tests.returncode==0 else "failed","stdout":tests.stdout.strip(),"stderr":tests.stderr.strip()});passed=sum(x["status"]=="passed" for x in sc);target=ROOT/"artifacts/project-8-batch-platform";target.mkdir(parents=True,exist_ok=True);(target/"latest.json").write_text(json.dumps({"summary":{"total":len(sc),"passed":passed,"failed":len(sc)-passed},"scenarios":sc},indent=2)+"\n");(target/"latest.txt").write_text(f"Project 8 verification: {passed}/{len(sc)} passed\n");print(f"Project 8 verification: {passed}/{len(sc)} passed");return 0 if passed==len(sc) else 1
if __name__=="__main__":raise SystemExit(main())
