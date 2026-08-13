from __future__ import annotations
import argparse,json
from pathlib import Path
from .eval_platform import Candidate,EvaluationPlatform,GateThresholds,demo_suite,two_proportion_z_test

def answer(prompt:str)->str:
    if "recovery" in prompt:return "checkpoint and idempotency"
    if "retrieval" in prompt:return "lexical and dense"
    return "cost and fallback"

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--db",type=Path,default=Path("data/evaluations.db")); sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("demo"); ab=sub.add_parser("ab-test");
    for name in ("success-a","total-a","success-b","total-b"):ab.add_argument(f"--{name}",type=int,required=True)
    args=parser.parse_args(argv)
    if args.command=="ab-test": print(json.dumps(two_proportion_z_test(args.success_a,args.total_a,args.success_b,args.total_b),indent=2)); return 0
    platform=EvaluationPlatform(args.db); suite=platform.register_suite("core","1",demo_suite()); run=platform.run(suite,Candidate("demo","1",answer,0.001)); print(json.dumps(platform.gate(run,GateThresholds()),indent=2)); return 0
if __name__=="__main__":raise SystemExit(main())

