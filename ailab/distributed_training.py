from __future__ import annotations
import hashlib,json,math
from dataclasses import dataclass
from pathlib import Path

class TrainingError(RuntimeError):pass
@dataclass(frozen=True)
class TrainingConfig:
 world_size:int=2;epochs:int=2;learning_rate:float=.1;gradient_accumulation:int=1;checkpoint_every:int=1
 def validate(self):
  if self.world_size<1:raise ValueError("world_size must be positive")
  if self.epochs<1:raise ValueError("epochs must be positive")
  if not math.isfinite(self.learning_rate) or self.learning_rate<=0:raise ValueError("learning_rate must be finite and positive")
  if self.gradient_accumulation<1 or self.checkpoint_every<1:raise ValueError("accumulation and checkpoint cadence must be positive")
@dataclass(frozen=True)
class Sample:x:float;y:float

class DistributedTrainer:
 """Deterministic data-parallel trainer exposing DDP invariants without requiring GPUs."""
 def __init__(self,root:Path,config:TrainingConfig):
  config.validate();self.root=root;root.mkdir(parents=True,exist_ok=True);self.config=config
 def partition(self,data:list[Sample])->list[list[Sample]]:
  if not data:raise ValueError("training data cannot be empty")
  return [data[rank::self.config.world_size] for rank in range(self.config.world_size)]
 def train(self,data:list[Sample],run_id:str="run",fail_at:tuple[int,int]|None=None,resume:bool=False)->dict:
  if not run_id or "/" in run_id or ".." in run_id:raise ValueError("unsafe run_id")
  shards=self.partition(data)
  if any(not shard for shard in shards):raise ValueError("world_size cannot exceed sample count")
  checkpoint=self.root/f"{run_id}.json";state={"epoch":0,"weight":0.0,"steps":0}
  if resume:
   if not checkpoint.exists():raise TrainingError("checkpoint not found")
   state=json.loads(checkpoint.read_text())
  for epoch in range(state["epoch"],self.config.epochs):
   gradients=[]
   for rank,shard in enumerate(shards):
    if fail_at==(epoch,rank):self._save(checkpoint,{**state,"epoch":epoch});raise TrainingError(f"worker {rank} failed")
    gradients.append(sum(2*s.x*(state["weight"]*s.x-s.y) for s in shard)/len(shard))
   gradient=sum(gradients)/len(gradients)
   state["weight"]-=self.config.learning_rate*gradient/self.config.gradient_accumulation;state["steps"]+=1;state["epoch"]=epoch+1
   if state["epoch"]%self.config.checkpoint_every==0:self._save(checkpoint,state)
  checksum=hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest();return {**state,"checksum":checksum,"partitions":[len(x) for x in shards]}
 def _save(self,path:Path,state:dict):
  temporary=path.with_suffix(".tmp");temporary.write_text(json.dumps(state,sort_keys=True));temporary.replace(path)

def framework_inventory()->dict[str,bool]:
 import importlib.util
 return {name:importlib.util.find_spec(name) is not None for name in ("torch","tensorflow","jax")}
