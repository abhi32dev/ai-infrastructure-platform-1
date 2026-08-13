import argparse,json
from pathlib import Path
from .golden_path import *
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("name");p.add_argument("--output",type=Path,default=Path("generated-services"));p.add_argument("--port",type=int,default=8080);a=p.parse_args(argv);g=GoldenPath();target=g.generate(a.output,ServiceConfig(a.name,a.port));print(json.dumps({"path":str(target),**g.validate(target)},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
