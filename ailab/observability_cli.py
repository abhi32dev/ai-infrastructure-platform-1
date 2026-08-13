import argparse,json,time
from pathlib import Path
from .observability import *
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--db",type=Path,default=Path("data/telemetry.db"));a=p.parse_args(argv);t=Telemetry(a.db);now=time.time();[t.request("gateway",i%20!=0,10+i,tokens_in=100,tokens_out=25,cost=.002,model="small",tenant="demo",cache_hit=i%3==0,timestamp=now-i) for i in range(100)];print(json.dumps({"metrics":t.service_metrics("gateway"),"budget":t.error_budget(SLO("gateway",.99,3600),now),"cost":t.cost_breakdown()},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
