from __future__ import annotations
import argparse,json
from .gpu_platform import *
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--workloads",type=int,default=3);a=p.parse_args(argv);x=GPUPlatform({"demo":4});x.add_node(GPUNode("stable-a","a10",4));scheduled={f"job-{i}":x.schedule(Workload(f"job-{i}",1,"a10",tenant="demo")) for i in range(min(a.workloads,4))};print(json.dumps({"scheduled":scheduled,"autoscale":x.autoscale_plan([])},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
