from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

class OrchestrationError(RuntimeError):pass
@dataclass(frozen=True)
class Task:
 name:str;handler:Callable[[dict],object];dependencies:tuple[str,...]=();cpu:int=1;memory:int=1;retries:int=0

class Orchestrator:
 def __init__(self,cpu:int=4,memory:int=8,object_store:int=1024):
  if min(cpu,memory,object_store)<1:raise ValueError("capacities must be positive")
  self.cpu=cpu;self.memory=memory;self.object_store=object_store;self.objects={};self.events=[]
 def validate(self,tasks:list[Task]):
  names=[x.name for x in tasks]
  if not tasks or any(not x for x in names):raise ValueError("tasks and names are required")
  if len(names)!=len(set(names)):raise ValueError("duplicate task")
  seen=set()
  for task in tasks:
   if task.cpu<1 or task.memory<1 or task.retries<0:raise ValueError("invalid task resources")
   if any(dep not in seen for dep in task.dependencies):raise ValueError("dependency must precede task")
   seen.add(task.name)
 def run(self,tasks:list[Task])->dict:
  self.validate(tasks);context={}
  for task in tasks:
   if task.cpu>self.cpu or task.memory>self.memory:raise OrchestrationError(f"unschedulable task: {task.name}")
   attempts=0
   while True:
    attempts+=1
    try:result=task.handler(context);break
    except Exception as exc:
     self.events.append({"task":task.name,"attempt":attempts,"status":"failed","error":str(exc)})
     if attempts>task.retries:raise OrchestrationError(f"task failed: {task.name}") from exc
   size=len(repr(result).encode())
   if sum(len(repr(x).encode()) for x in self.objects.values())+size>self.object_store:raise OrchestrationError("object store exhausted")
   self.objects[task.name]=result;context[task.name]=result;self.events.append({"task":task.name,"attempt":attempts,"status":"completed"})
  return context
 def actor(self,name:str,initial:int=0):
  if not name:raise ValueError("actor name required")
  state={"value":initial,"restarts":0}
  def call(delta:int=0,crash:bool=False):
   if crash:state["restarts"]+=1;raise OrchestrationError("actor crashed")
   state["value"]+=delta;return dict(state)
  return call
