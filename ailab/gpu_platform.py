from __future__ import annotations
from dataclasses import dataclass,field

class SchedulingError(RuntimeError):pass
@dataclass
class GPUNode:
 name:str;gpu_type:str;capacity:int;spot:bool=False;healthy:bool=True;allocations:dict[str,int]=field(default_factory=dict)
 @property
 def available(self):return self.capacity-sum(self.allocations.values())
@dataclass(frozen=True)
class Workload:
 name:str;gpus:int;gpu_type:str|None=None;priority:int=0;tenant:str="default"
 def validate(self):
  if not self.name.strip():raise ValueError("workload name required")
  if self.gpus<1:raise ValueError("GPU request must be positive")

class GPUPlatform:
 def __init__(self,tenant_quotas:dict[str,int]|None=None):self.nodes={};self.workloads={};self.quotas=tenant_quotas or {}
 def add_node(self,node:GPUNode):
  if not node.name.strip() or node.capacity<1:raise ValueError("invalid node")
  if node.name in self.nodes:raise ValueError("duplicate node")
  self.nodes[node.name]=node
 def schedule(self,workload:Workload)->str:
  workload.validate()
  if workload.name in self.workloads:return self.workloads[workload.name]
  used=sum(w.gpus for w,n in getattr(self,"_requests",[]) if w.tenant==workload.tenant)
  if workload.tenant in self.quotas and used+workload.gpus>self.quotas[workload.tenant]:raise SchedulingError("tenant quota exceeded")
  candidates=[n for n in self.nodes.values() if n.healthy and n.available>=workload.gpus and (workload.gpu_type is None or n.gpu_type==workload.gpu_type)]
  if not candidates:raise SchedulingError("no feasible GPU node")
  node=sorted(candidates,key=lambda n:(n.spot,-n.available,n.name))[0];node.allocations[workload.name]=workload.gpus;self.workloads[workload.name]=node.name
  if not hasattr(self,"_requests"):self._requests=[]
  self._requests.append((workload,node.name));return node.name
 def complete(self,name:str):
  node_name=self.workloads.pop(name,None)
  if node_name:self.nodes[node_name].allocations.pop(name,None)
 def drain(self,node_name:str)->list[str]:
  if node_name not in self.nodes:raise KeyError(node_name)
  node=self.nodes[node_name];node.healthy=False;evicted=list(node.allocations);node.allocations.clear()
  for name in evicted:self.workloads.pop(name,None)
  return evicted
 def autoscale_plan(self,pending:list[Workload])->dict:
  demand=sum(w.gpus for w in pending);available=sum(n.available for n in self.nodes.values() if n.healthy);return {"pending_gpus":demand,"available_gpus":available,"nodes_to_add":max(0,demand-available)}
