from __future__ import annotations
import argparse,json
from .lakehouse_features import *
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--events",type=int,default=8);a=p.parse_args(argv);x=LakehouseFeaturePlatform();[x.ingest(FeatureEvent(str(i),f"u{i%2}",float(i),float(i))) for i in range(a.events)];x.compact(a.events);print(json.dumps({"online":x.materialize_online(a.events),"quality":x.quality()},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
