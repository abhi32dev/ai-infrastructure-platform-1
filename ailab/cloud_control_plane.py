from __future__ import annotations
import hashlib,json
from dataclasses import dataclass,asdict

class PolicyViolation(RuntimeError):pass
@dataclass(frozen=True)
class DeploymentSpec:
 name:str;provider:str;region:str;instance_type:str;replicas:int;monthly_budget:float;private_network:bool=True;encrypted:bool=True
 def validate(self):
  if not self.name or not self.name.replace("-","").isalnum():raise ValueError("invalid deployment name")
  if self.provider not in {"aws","gcp","azure"}:raise ValueError("unsupported provider")
  if not self.region or not self.instance_type:raise ValueError("region and instance type required")
  if self.replicas<1 or self.monthly_budget<=0:raise ValueError("replicas and budget must be positive")

class CloudMLControlPlane:
 PRICES={"cpu-small":50.0,"cpu-large":180.0,"gpu-small":700.0}
 def __init__(self):self.desired={};self.actual={};self.audit=[]
 def plan(self,spec:DeploymentSpec)->dict:
  spec.validate()
  if not spec.private_network or not spec.encrypted:raise PolicyViolation("private networking and encryption are mandatory")
  if spec.instance_type not in self.PRICES:raise ValueError("unknown instance type")
  cost=self.PRICES[spec.instance_type]*spec.replicas
  if cost>spec.monthly_budget:raise PolicyViolation("estimated cost exceeds budget")
  digest=hashlib.sha256(json.dumps(asdict(spec),sort_keys=True).encode()).hexdigest();return {"spec":asdict(spec),"estimated_monthly_cost":cost,"plan_id":digest}
 def apply(self,plan:dict)->str:
  spec=DeploymentSpec(**plan["spec"]);expected=self.plan(spec)
  if expected["plan_id"]!=plan.get("plan_id"):raise PolicyViolation("plan integrity failure")
  if spec.name in self.desired and self.desired[spec.name]==plan:return "unchanged"
  self.desired[spec.name]=plan;self.actual[spec.name]=dict(plan["spec"]);self.audit.append({"action":"apply","name":spec.name,"plan_id":plan["plan_id"]});return "applied"
 def drift(self,name:str)->dict:
  if name not in self.desired:raise KeyError(name)
  desired=self.desired[name]["spec"];actual=self.actual.get(name,{});changes={key:{"desired":value,"actual":actual.get(key)} for key,value in desired.items() if actual.get(key)!=value};return {"drifted":bool(changes),"changes":changes}
 def reconcile(self,name:str):
  report=self.drift(name)
  if report["drifted"]:self.actual[name]=dict(self.desired[name]["spec"]);self.audit.append({"action":"reconcile","name":name})
  return report
 def failover(self,name:str,target_region:str)->dict:
  if not target_region:raise ValueError("target region required")
  if name not in self.desired:raise KeyError(name)
  current=DeploymentSpec(**self.desired[name]["spec"]);replacement=DeploymentSpec(**{**asdict(current),"region":target_region});plan=self.plan(replacement);self.apply(plan);return plan
