import threading,time
import pytest
from ailab.inference_server import *

def test_happy_path_and_health():
 s=BatchedInferenceServer(demo_model(),"v1"); r=s.infer(InferenceRequest("hello")); assert r.output=="prediction:HELLO" and s.health()["ready"]; s.shutdown(); assert not s.health()["ready"]
def test_concurrent_requests_form_dynamic_batch():
 s=BatchedInferenceServer(demo_model(delay_seconds=.003),"v1",max_batch_size=8,max_batch_wait_ms=20); out=[]
 threads=[threading.Thread(target=lambda i=i:out.append(s.infer(InferenceRequest(str(i))))) for i in range(6)]
 [t.start() for t in threads];[t.join() for t in threads]; assert len(out)==6 and s.health()["metrics"]["max_batch_size"]>1;s.shutdown()
def test_backpressure_load_shedding():
 gate=threading.Event()
 def blocked(xs):gate.wait(.2);return xs
 s=BatchedInferenceServer(blocked,"v1",max_batch_size=1,max_queue_size=1,max_batch_wait_ms=0); errors=[]
 t=threading.Thread(target=lambda:s.infer(InferenceRequest("one",deadline_seconds=.5)));t.start();time.sleep(.01)
 queued=threading.Thread(target=lambda:s.infer(InferenceRequest("two",deadline_seconds=.5)));queued.start();time.sleep(.01)
 with pytest.raises(Overloaded):s.infer(InferenceRequest("three"))
 gate.set();t.join();queued.join();s.shutdown();assert s.metrics["shed"]==1
def test_deadline_exceeded():
 s=BatchedInferenceServer(demo_model(delay_seconds=.05),"v1",max_batch_wait_ms=0)
 with pytest.raises(DeadlineExceeded):s.infer(InferenceRequest("slow",deadline_seconds=.001))
 s.shutdown()
def test_model_error_visible():
 def bad(xs):raise RuntimeError("corrupt model")
 s=BatchedInferenceServer(bad,"v1",max_batch_wait_ms=0)
 with pytest.raises(ServingError,match="corrupt model"):s.infer(InferenceRequest("x"))
 s.shutdown()
def test_canary_routing_and_rollback():
 stable=BatchedInferenceServer(demo_model("stable"),"v1",max_batch_wait_ms=0);canary=BatchedInferenceServer(demo_model("canary"),"v2",max_batch_wait_ms=0);deployment=CanaryDeployment(stable,canary,100)
 assert deployment.infer(InferenceRequest("x","id")).model_version=="v2";deployment.rollback();assert deployment.infer(InferenceRequest("x","id2")).model_version=="v1";stable.shutdown();canary.shutdown()
def test_canary_failure_falls_back_to_stable():
 stable=BatchedInferenceServer(demo_model("stable"),"v1",max_batch_wait_ms=0);canary=BatchedInferenceServer(lambda xs:(_ for _ in ()).throw(RuntimeError("bad")),"v2",max_batch_wait_ms=0);d=CanaryDeployment(stable,canary,100);assert d.infer(InferenceRequest("x")).model_version=="v1";stable.shutdown();canary.shutdown()
def test_rejects_after_shutdown():
 s=BatchedInferenceServer(demo_model(),"v1");s.shutdown();
 with pytest.raises(NotReady):s.infer(InferenceRequest("x"))
