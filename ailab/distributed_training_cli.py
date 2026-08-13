from __future__ import annotations
import argparse,json,tempfile
from pathlib import Path
from .distributed_training import *
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--epochs",type=int,default=10);p.add_argument("--world-size",type=int,default=2);a=p.parse_args(argv);data=[Sample(float(i),2*i) for i in range(1,9)];r=DistributedTrainer(Path(tempfile.gettempdir())/"ailab-training",TrainingConfig(a.world_size,a.epochs,.005)).train(data,"demo");print(json.dumps(r,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
