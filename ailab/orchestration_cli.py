from __future__ import annotations
import json,argparse
from .distributed_orchestration import *
def main(argv=None):
 argparse.ArgumentParser().parse_args(argv);x=Orchestrator();r=x.run([Task("extract",lambda c:[1,2,3]),Task("train",lambda c:sum(c["extract"]),("extract",))]);print(json.dumps({"results":r,"events":x.events},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
