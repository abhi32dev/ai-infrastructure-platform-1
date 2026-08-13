from __future__ import annotations
import argparse,json
from .llm_inference_optimized import *
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--requests",type=int,default=8);p.add_argument("--batch",type=int,default=4);a=p.parse_args(argv);e=ContinuousBatchEngine(a.batch);[e.submit(GenerationRequest(str(i),f"shared prompt {i}",priority=i%2)) for i in range(a.requests)];out=[]
 while e.queue:out.extend(e.step())
 print(json.dumps(out,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
