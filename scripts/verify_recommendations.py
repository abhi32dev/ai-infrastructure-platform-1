#!/usr/bin/env python3
import json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));from ailab.recommendations import *
def main():
 with tempfile.TemporaryDirectory() as d:
  p=RecommendationPlatform(Path(d)/"r.db",demo_catalog());p.interact("u","ml-book","purchase");recs=p.recommend("u",3);metrics=ranking_metrics([r.item_id for r in recs],{"gpu-course","python-lab"},demo_catalog(),3);cold=p.recommend("new",3);sc=[{"name":"personalized_ranking","status":"passed" if recs[0].item_id in {"gpu-course","python-lab"} else "failed","evidence":[r.__dict__ for r in recs]},{"name":"cold_start","status":"passed" if len(cold)==3 else "failed","evidence":[r.__dict__ for r in cold]},{"name":"offline_metrics","status":"passed" if metrics["recall_at_k"]>0 else "failed","evidence":metrics}]
 tests=subprocess.run([sys.executable,"-m","pytest","-q","tests/test_recommendations.py"],cwd=ROOT,text=True,capture_output=True);sc.append({"name":"project_7_tests","status":"passed" if tests.returncode==0 else "failed","stdout":tests.stdout.strip()});passed=sum(x["status"]=="passed" for x in sc);target=ROOT/"artifacts/project-7-recommendations";target.mkdir(parents=True,exist_ok=True);(target/"latest.json").write_text(json.dumps({"summary":{"total":len(sc),"passed":passed,"failed":len(sc)-passed},"scenarios":sc},indent=2)+"\n");(target/"latest.txt").write_text(f"Project 7 verification: {passed}/{len(sc)} passed\n");print(f"Project 7 verification: {passed}/{len(sc)} passed");return 0 if passed==len(sc) else 1
if __name__=="__main__":raise SystemExit(main())
