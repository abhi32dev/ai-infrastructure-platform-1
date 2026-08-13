import pytest
from ailab.gpu_platform import *
@pytest.mark.parametrize("node",[GPUNode("","a",1),GPUNode("n","a",0),GPUNode("n","a",-1)])
def test_invalid_nodes(node):
 with pytest.raises(ValueError):GPUPlatform().add_node(node)
def test_duplicate_node():
 p=GPUPlatform();p.add_node(GPUNode("n","a",1))
 with pytest.raises(ValueError):p.add_node(GPUNode("n","a",1))
@pytest.mark.parametrize("workload",[Workload("",1),Workload("x",0),Workload("x",-1)])
def test_invalid_workloads(workload):
 with pytest.raises(ValueError):workload.validate()
def test_schedule_prefers_on_demand_and_is_idempotent():
 p=GPUPlatform();p.add_node(GPUNode("spot","a",2,True));p.add_node(GPUNode("stable","a",2));w=Workload("w",1);assert p.schedule(w)=="stable" and p.schedule(w)=="stable"
def test_type_constraint_and_insufficient_capacity():
 p=GPUPlatform();p.add_node(GPUNode("n","a",1))
 with pytest.raises(SchedulingError):p.schedule(Workload("wrong",1,"b"))
 with pytest.raises(SchedulingError):p.schedule(Workload("large",2,"a"))
def test_tenant_quota():
 p=GPUPlatform({"a":1});p.add_node(GPUNode("n","x",4));p.schedule(Workload("one",1,tenant="a"))
 with pytest.raises(SchedulingError):p.schedule(Workload("two",1,tenant="a"))
def test_complete_reclaims_capacity():
 p=GPUPlatform();p.add_node(GPUNode("n","x",1));p.schedule(Workload("one",1));p.complete("missing");p.complete("one");assert p.nodes["n"].available==1
def test_drain_evicts_and_marks_unhealthy():
 p=GPUPlatform();p.add_node(GPUNode("n","x",2));p.schedule(Workload("one",1));assert p.drain("n")==["one"] and not p.nodes["n"].healthy
def test_unknown_drain():
 with pytest.raises(KeyError):GPUPlatform().drain("missing")
@pytest.mark.parametrize("pending,expected",[([],0),([Workload("a",1)],0),([Workload("a",3)],1)])
def test_autoscale_plan(pending,expected):
 p=GPUPlatform();p.add_node(GPUNode("n","x",2));assert p.autoscale_plan(pending)["nodes_to_add"]==expected
