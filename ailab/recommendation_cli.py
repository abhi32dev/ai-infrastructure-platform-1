import argparse,json
from pathlib import Path
from .recommendations import *
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--db",type=Path,default=Path("data/recommendations.db"));p.add_argument("--user",default="demo");a=p.parse_args(argv);r=RecommendationPlatform(a.db,demo_catalog());r.interact(a.user,"ml-book","purchase");print(json.dumps([x.__dict__ for x in r.recommend(a.user)],indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
