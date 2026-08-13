#!/usr/bin/env python3
import json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));from ailab.golden_path import *
def main():
 with tempfile.TemporaryDirectory() as d:
  g=GoldenPath();target=g.generate(Path(d),ServiceConfig("verified-service"));valid=g.validate(target);(target/"Dockerfile").write_text((target/"Dockerfile").read_text().replace("USER app\n",""));unsafe=g.validate(target);sc=[{"name":"complete_scaffold","status":"passed" if valid["valid"] else "failed","evidence":valid},{"name":"unsafe_scaffold_rejected","status":"passed" if not unsafe["valid"] else "failed","evidence":unsafe}]
 tests=subprocess.run([sys.executable,"-m","pytest","-q","tests/test_golden_path.py"],cwd=ROOT,text=True,capture_output=True);sc.append({"name":"project_9_tests","status":"passed" if tests.returncode==0 else "failed","stdout":tests.stdout.strip()});passed=sum(x["status"]=="passed" for x in sc);dest=ROOT/"artifacts/project-9-golden-path";dest.mkdir(parents=True,exist_ok=True);(dest/"latest.json").write_text(json.dumps({"summary":{"total":len(sc),"passed":passed,"failed":len(sc)-passed},"scenarios":sc},indent=2)+"\n");(dest/"latest.txt").write_text(f"Project 9 verification: {passed}/{len(sc)} passed\n");print(f"Project 9 verification: {passed}/{len(sc)} passed");return 0 if passed==len(sc) else 1
if __name__=="__main__":raise SystemExit(main())
