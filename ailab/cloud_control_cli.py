from __future__ import annotations
import argparse,json
from .cloud_control_plane import *
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--provider",choices=["aws","gcp","azure"],default="aws");a=p.parse_args(argv);x=CloudMLControlPlane();plan=x.plan(DeploymentSpec("demo-model",a.provider,"us-west","cpu-small",1,100));print(json.dumps({"apply":x.apply(plan),"plan":plan,"drift":x.drift("demo-model")},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
