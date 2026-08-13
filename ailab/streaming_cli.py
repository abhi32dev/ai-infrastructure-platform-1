from __future__ import annotations
import argparse,json,time
from pathlib import Path
from .streaming_features import Event,StreamingFeaturePlatform
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--db",type=Path,default=Path("data/streaming.db"));p.add_argument("--events",type=int,default=20);a=p.parse_args(argv);s=StreamingFeaturePlatform(a.db);now=time.time();[s.publish(Event(str(i),f"user-{i%3}","click",1,now+i/100)) for i in range(a.events)];result=s.consume("online",now=now+1);s.snapshot_offline(now+1);print(json.dumps({"consume":result,"features":[s.feature(f"user-{i}") for i in range(3)]},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
