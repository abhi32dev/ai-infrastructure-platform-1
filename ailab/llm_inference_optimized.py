from __future__ import annotations
import hashlib,math,time
from dataclasses import dataclass

class AdmissionRejected(RuntimeError):pass
class CacheExhausted(RuntimeError):pass
@dataclass(frozen=True)
class GenerationRequest:
 request_id:str;prompt:str;max_tokens:int=32;priority:int=0;deadline:float|None=None
 def validate(self):
  if not self.request_id.strip():raise ValueError("request_id is required")
  if not self.prompt.strip():raise ValueError("prompt is required")
  if self.max_tokens<1:raise ValueError("max_tokens must be positive")
  if self.max_tokens>4096:raise ValueError("max_tokens exceeds policy")
  if self.deadline is not None and not math.isfinite(self.deadline):raise ValueError("deadline must be finite")

class KVCache:
 def __init__(self,capacity_tokens:int):
  if capacity_tokens<1:raise ValueError("capacity must be positive")
  self.capacity=capacity_tokens;self.entries={};self.used=0
 def reserve(self,key:str,tokens:int):
  if tokens<0:raise ValueError("tokens cannot be negative")
  if key in self.entries:return False
  if self.used+tokens>self.capacity:raise CacheExhausted("KV cache capacity exceeded")
  self.entries[key]=tokens;self.used+=tokens;return True
 def release(self,key:str):self.used-=self.entries.pop(key,0)

class ContinuousBatchEngine:
 def __init__(self,max_batch:int=8,cache_tokens:int=8192):
  if max_batch<1:raise ValueError("max_batch must be positive")
  self.max_batch=max_batch;self.cache=KVCache(cache_tokens);self.queue=[];self.completed={};self.prefix_cache={}
 def submit(self,request:GenerationRequest):
  request.validate()
  if request.request_id in self.completed or any(x.request_id==request.request_id for x in self.queue):return "duplicate"
  if request.deadline is not None and request.deadline<=time.time():raise AdmissionRejected("deadline already expired")
  self.queue.append(request);self.queue.sort(key=lambda x:(-x.priority,x.request_id));return "queued"
 def step(self)->list[dict]:
  batch=self.queue[:self.max_batch];self.queue=self.queue[self.max_batch:];results=[]
  for request in batch:
   if request.deadline is not None and request.deadline<=time.time():self.completed[request.request_id]={"status":"expired"};continue
   prefix=hashlib.sha256(request.prompt[:64].encode()).hexdigest();hit=prefix in self.prefix_cache;tokens=min(request.max_tokens,max(1,len(request.prompt.split())//2));self.cache.reserve(request.request_id,tokens)
   result={"request_id":request.request_id,"status":"completed","tokens":tokens,"prefix_cache_hit":hit,"quantized_bytes":tokens,"text":f"generated:{request.prompt[:24]}"};self.prefix_cache[prefix]=True;self.completed[request.request_id]=result;results.append(result);self.cache.release(request.request_id)
  return results
 def speculative_acceptance(self,draft:list[int],target:list[int])->dict:
  accepted=0
  for a,b in zip(draft,target):
   if a!=b:break
   accepted+=1
  return {"accepted":accepted,"proposed":len(draft),"rate":accepted/len(draft) if draft else 0.0}
