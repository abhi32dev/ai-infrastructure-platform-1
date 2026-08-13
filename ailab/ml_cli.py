import argparse,json,tempfile
from pathlib import Path
from .ml_lifecycle import *
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--registry",type=Path,default=Path("data/models"));a=p.parse_args(argv);x,y=make_dataset();xt,xv,yt,yv=split(x,y);m=LogisticModel(x.shape[1]).train(xt,yt);metrics=evaluate(yv,m.predict(xv));r=ModelRegistry(a.registry);r.register(m,metrics,xt.mean(0),"v1");r.promote("v1");shifted,_=make_dataset(100,shift=2);print(json.dumps({"metrics":asdict(metrics),"production":r.data["production"],"drift":r.drift(shifted)},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
