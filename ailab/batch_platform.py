from __future__ import annotations
import hashlib,json,sqlite3,time,uuid,threading
from concurrent.futures import ThreadPoolExecutor,as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

class BatchFailure(RuntimeError):pass
@dataclass(frozen=True)
class WorkItem:id:str;payload:str;size_bytes:int
@dataclass(frozen=True)
class Batch:id:str;items:tuple[WorkItem,...];total_bytes:int

class SelfHealingBatchPlatform:
 def __init__(self,path:Path,target_batch_bytes:int=1024,max_items:int=10,max_workers:int=4,ttl_seconds:float=3600):
  if min(target_batch_bytes,max_items,max_workers)<=0:raise ValueError("batch configuration must be positive")
  path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path,check_same_thread=False);self.lock=threading.RLock();self.target=target_batch_bytes;self.max_items=max_items;self.max_workers=max_workers;self.ttl=ttl_seconds
  self.db.executescript("""CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,status TEXT,manifest TEXT,created_at REAL,updated_at REAL);CREATE TABLE IF NOT EXISTS checkpoints(run_id TEXT,item_id TEXT,status TEXT,output TEXT,attempts INTEGER,error TEXT,updated_at REAL,PRIMARY KEY(run_id,item_id));CREATE TABLE IF NOT EXISTS outputs(item_id TEXT PRIMARY KEY,output TEXT,checksum TEXT,created_at REAL);CREATE TABLE IF NOT EXISTS dedup(item_id TEXT PRIMARY KEY,expires_at REAL);CREATE TABLE IF NOT EXISTS reconciliation(run_id TEXT,pass INTEGER,missing TEXT,created_at REAL,PRIMARY KEY(run_id,pass));""");self.db.commit()
 def plan(self,items:list[WorkItem])->list[Batch]:
  ordered=sorted(items,key=lambda x:(-x.size_bytes,x.id));bins=[]
  for item in ordered:
   target=next((b for b in bins if len(b)<self.max_items and sum(x.size_bytes for x in b)+item.size_bytes<=self.target),None)
   if target is None:target=[];bins.append(target)
   target.append(item)
  return [Batch(hashlib.sha256("|".join(x.id for x in b).encode()).hexdigest()[:12],tuple(b),sum(x.size_bytes for x in b)) for b in bins]
 def execute(self,items:list[WorkItem],worker:Callable[[WorkItem],str],run_id:str|None=None,max_attempts:int=3)->dict:
  run_id=run_id or uuid.uuid4().hex;existing=self.db.execute("SELECT manifest FROM runs WHERE id=?",(run_id,)).fetchone()
  if not existing:self.db.execute("INSERT INTO runs VALUES(?,?,?,?,?)",(run_id,"running",json.dumps([x.__dict__ for x in items]),time.time(),time.time()));self.db.commit()
  else:items=[WorkItem(**x) for x in json.loads(existing[0])]
  pending=[x for x in items if not self._complete(run_id,x.id)]
  batches=self.plan(pending);failures=[]
  with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
   futures={pool.submit(self._process,run_id,item,worker,max_attempts):item for batch in batches for item in batch.items}
   for future in as_completed(futures):
    try:future.result()
    except Exception as exc:failures.append({"item":futures[future].id,"error":str(exc)})
  reconciliation=self.reconcile(run_id,items,worker,max_attempts);status="completed" if not reconciliation["missing"] else "failed";self.db.execute("UPDATE runs SET status=?,updated_at=? WHERE id=?",(status,time.time(),run_id));self.db.commit();return {"run_id":run_id,"status":status,"batches":len(batches),"failures":failures,**reconciliation}
 def reconcile(self,run_id:str,items:list[WorkItem],worker:Callable[[WorkItem],str],max_attempts:int=3)->dict:
  expected={x.id:x for x in items};history=[]
  for pass_number in range(1,4):
   actual={row[0] for row in self.db.execute("SELECT item_id FROM outputs")};missing=sorted(set(expected)-actual);history.append({"pass":pass_number,"missing":missing});self.db.execute("INSERT OR REPLACE INTO reconciliation VALUES(?,?,?,?)",(run_id,pass_number,json.dumps(missing),time.time()));self.db.commit()
   if not missing:break
   for item_id in missing:
    self.db.execute("DELETE FROM checkpoints WHERE run_id=? AND item_id=?",(run_id,item_id));self.db.commit()
    try:self._process(run_id,expected[item_id],worker,max_attempts)
    except Exception:pass
  actual={row[0] for row in self.db.execute("SELECT item_id FROM outputs")};return {"missing":sorted(set(expected)-actual),"reconciliation":history}
 def _process(self,run_id:str,item:WorkItem,worker:Callable[[WorkItem],str],max_attempts:int):
  with self.lock:
   if self._complete(run_id,item.id):return
   now=time.time();dedup=self.db.execute("SELECT expires_at FROM dedup WHERE item_id=?",(item.id,)).fetchone()
   if dedup and dedup[0]>now and self.db.execute("SELECT 1 FROM outputs WHERE item_id=?",(item.id,)).fetchone():self._checkpoint(run_id,item.id,"completed","dedup-reused",0,None);return
   prior=self.db.execute("SELECT attempts FROM checkpoints WHERE run_id=? AND item_id=?",(run_id,item.id)).fetchone();attempts=prior[0] if prior else 0
  last=""
  while attempts<max_attempts:
   attempts+=1
   try:
    output=worker(item);checksum=hashlib.sha256(output.encode()).hexdigest()
    with self.lock:self.db.execute("INSERT OR REPLACE INTO outputs VALUES(?,?,?,?)",(item.id,output,checksum,time.time()));self.db.execute("INSERT OR REPLACE INTO dedup VALUES(?,?)",(item.id,time.time()+self.ttl));self._checkpoint(run_id,item.id,"completed",output,attempts,None)
    return
   except Exception as exc:
    last=f"{type(exc).__name__}: {exc}"
    with self.lock:self._checkpoint(run_id,item.id,"failed",None,attempts,last)
  raise BatchFailure(f"item {item.id} exhausted retries: {last}")
 def _checkpoint(self,run,item,status,output,attempts,error):self.db.execute("INSERT OR REPLACE INTO checkpoints VALUES(?,?,?,?,?,?,?)",(run,item,status,output,attempts,error,time.time()));self.db.commit()
 def _complete(self,run,item):return bool(self.db.execute("SELECT 1 FROM checkpoints WHERE run_id=? AND item_id=? AND status='completed'",(run,item)).fetchone())
 def inspect(self,run):return {"run":dict(self.db.execute("SELECT * FROM runs WHERE id=?",(run,)).fetchone()),"checkpoints":[dict(x) for x in self.db.execute("SELECT * FROM checkpoints WHERE run_id=?",(run,))],"reconciliation":[dict(x) for x in self.db.execute("SELECT * FROM reconciliation WHERE run_id=?",(run,))]}
