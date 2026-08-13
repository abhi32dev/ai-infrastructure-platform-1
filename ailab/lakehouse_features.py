from __future__ import annotations
import hashlib,math,time
from dataclasses import dataclass

class DataContractError(ValueError):pass
@dataclass(frozen=True)
class FeatureEvent:
 event_id:str;entity_id:str;event_time:float;value:float;schema_version:int=1
 def validate(self):
  if not self.event_id or not self.entity_id:raise DataContractError("event and entity identifiers are required")
  if not math.isfinite(self.event_time) or not math.isfinite(self.value):raise DataContractError("time and value must be finite")
  if self.schema_version!=1:raise DataContractError("unsupported schema version")

class LakehouseFeaturePlatform:
 def __init__(self):self.bronze={};self.silver=[];self.commits=[];self.online={};self.dlq=[]
 def ingest(self,event:FeatureEvent)->str:
  try:event.validate()
  except DataContractError as exc:self.dlq.append({"event":event,"error":str(exc)});return "dead_lettered"
  if event.event_id in self.bronze:return "duplicate"
  self.bronze[event.event_id]=event;return "ingested"
 def compact(self,watermark:float|None=None)->dict:
  watermark=time.time() if watermark is None else watermark
  eligible=sorted((e for e in self.bronze.values() if e.event_time<=watermark),key=lambda e:(e.event_time,e.event_id));known={e.event_id for e in self.silver};new=[e for e in eligible if e.event_id not in known];self.silver.extend(new)
  digest=hashlib.sha256("|".join(e.event_id for e in self.silver).encode()).hexdigest();self.commits.append({"version":len(self.commits)+1,"rows":len(self.silver),"checksum":digest});return self.commits[-1]
 def materialize_online(self,as_of:float):
  latest={}
  for event in self.silver:
   if event.event_time<=as_of and (event.entity_id not in latest or event.event_time>=latest[event.entity_id].event_time):latest[event.entity_id]=event
  self.online={key:value.value for key,value in latest.items()};return dict(self.online)
 def point_in_time(self,entity_id:str,as_of:float)->float|None:
  values=[e for e in self.silver if e.entity_id==entity_id and e.event_time<=as_of];return max(values,key=lambda e:e.event_time).value if values else None
 def quality(self)->dict:
  ids=[e.event_id for e in self.silver];return {"rows":len(ids),"unique":len(ids)==len(set(ids)),"dlq":len(self.dlq),"commits":len(self.commits)}
