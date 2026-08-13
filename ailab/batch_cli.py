import argparse,json
from pathlib import Path
from .batch_platform import *
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--db",type=Path,default=Path("data/batches.db"));p.add_argument("--items",type=int,default=20);a=p.parse_args(argv);platform=SelfHealingBatchPlatform(a.db);items=[WorkItem(str(i),f"payload-{i}",(i%7+1)*100) for i in range(a.items)];print(json.dumps(platform.execute(items,lambda x:x.payload.upper()),indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
