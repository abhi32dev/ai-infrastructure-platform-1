import pytest
from ailab.distributed_orchestration import *
@pytest.mark.parametrize("args",[(0,1,1),(1,0,1),(1,1,0),(-1,1,1)])
def test_invalid_cluster_capacity(args):
 with pytest.raises(ValueError):Orchestrator(*args)
def test_empty_and_duplicate_tasks_rejected():
 o=Orchestrator()
 with pytest.raises(ValueError):o.validate([])
 t=Task("a",lambda x:1)
 with pytest.raises(ValueError):o.validate([t,t])
def test_forward_and_missing_dependencies_rejected():
 with pytest.raises(ValueError):Orchestrator().validate([Task("a",lambda x:1,("b",)),Task("b",lambda x:1)])
@pytest.mark.parametrize("task",[Task("a",lambda x:1,cpu=0),Task("a",lambda x:1,memory=0),Task("a",lambda x:1,retries=-1)])
def test_invalid_task_resources(task):
 with pytest.raises(ValueError):Orchestrator().validate([task])
def test_dag_happy_path():
 o=Orchestrator();r=o.run([Task("a",lambda c:2),Task("b",lambda c:c["a"]*3,("a",))]);assert r=={"a":2,"b":6}
def test_retry_then_success():
 calls={"n":0}
 def flaky(c):
  calls["n"]+=1
  if calls["n"]==1:raise RuntimeError()
  return None
 assert Orchestrator().run([Task("a",flaky,retries=1)])["a"] is None
def test_retry_exhaustion():
 with pytest.raises(OrchestrationError):Orchestrator().run([Task("a",lambda c:(_ for _ in ()).throw(RuntimeError()),retries=1)])
def test_unschedulable_task():
 with pytest.raises(OrchestrationError):Orchestrator(cpu=1).run([Task("a",lambda c:1,cpu=2)])
def test_object_store_exhaustion():
 with pytest.raises(OrchestrationError):Orchestrator(object_store=2).run([Task("a",lambda c:"large")])
def test_actor_state_and_crash_visible():
 actor=Orchestrator().actor("a",2);assert actor(3)["value"]==5
 with pytest.raises(OrchestrationError):actor(crash=True)
 assert actor()["restarts"]==1
def test_empty_actor_name():
 with pytest.raises(ValueError):Orchestrator().actor("")
