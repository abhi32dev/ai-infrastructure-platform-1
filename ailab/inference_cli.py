from __future__ import annotations
import argparse,json,threading
from .inference_server import BatchedInferenceServer,InferenceRequest,demo_model
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--requests",type=int,default=20);p.add_argument("--batch-size",type=int,default=8);a=p.parse_args(argv);s=BatchedInferenceServer(demo_model(),"v1",a.batch_size,10,64);results=[];threads=[threading.Thread(target=lambda i=i:results.append(s.infer(InferenceRequest(f"item-{i}")))) for i in range(a.requests)];[t.start() for t in threads];[t.join() for t in threads];print(json.dumps({"responses":len(results),"health":s.health()},indent=2));s.shutdown();return 0
if __name__=="__main__":raise SystemExit(main())
