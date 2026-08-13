from __future__ import annotations
import hashlib,json,sqlite3,time
from dataclasses import dataclass
from pathlib import Path

class StreamError(RuntimeError):pass
class SchemaError(StreamError):pass

@dataclass(frozen=True)
class Event:
 id:str;user_id:str;event_type:str;value:float;event_time:float;schema_version:int=1

class StreamingFeaturePlatform:
 def __init__(self,path:Path,partitions:int=4,allowed_lateness:float=300):
  if partitions<=0:raise ValueError("partitions must be positive")
  path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row;self.partitions=partitions;self.allowed_lateness=allowed_lateness
  self.db.executescript("""CREATE TABLE IF NOT EXISTS events(partition_id INTEGER,offset_id INTEGER,event_id TEXT UNIQUE,payload TEXT,event_time REAL,ingested_at REAL,PRIMARY KEY(partition_id,offset_id));CREATE TABLE IF NOT EXISTS offsets(group_id TEXT,partition_id INTEGER,offset_id INTEGER,PRIMARY KEY(group_id,partition_id));CREATE TABLE IF NOT EXISTS online_features(user_id TEXT PRIMARY KEY,event_count INTEGER,total_value REAL,last_event_time REAL,updated_at REAL);CREATE TABLE IF NOT EXISTS offline_features(user_id TEXT,as_of REAL,event_count INTEGER,total_value REAL,PRIMARY KEY(user_id,as_of));CREATE TABLE IF NOT EXISTS dlq(event_id TEXT PRIMARY KEY,payload TEXT,error TEXT,created_at REAL);""");self.db.commit()
 def close(self):self.db.close()
 def publish(self,event:Event)->dict:
  if event.schema_version not in (1,2):return self._dlq(event,"unsupported schema version")
  if not event.id or not event.user_id:return self._dlq(event,"missing event or user id")
  partition=int(hashlib.sha256(event.user_id.encode()).hexdigest()[:8],16)%self.partitions
  offset=self.db.execute("SELECT COALESCE(MAX(offset_id),-1)+1 FROM events WHERE partition_id=?",(partition,)).fetchone()[0]
  try:self.db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)",(partition,offset,event.id,json.dumps(event.__dict__),event.event_time,time.time()));self.db.commit();return {"status":"published","partition":partition,"offset":offset}
  except sqlite3.IntegrityError:return {"status":"duplicate","event_id":event.id}
 def consume(self,group:str,limit:int=100,now:float|None=None)->dict:
  now=now or time.time();processed=duplicates=late=0
  for partition in range(self.partitions):
   row=self.db.execute("SELECT offset_id FROM offsets WHERE group_id=? AND partition_id=?",(group,partition)).fetchone();last=row[0] if row else -1
   rows=self.db.execute("SELECT * FROM events WHERE partition_id=? AND offset_id>? ORDER BY offset_id LIMIT ?",(partition,last,limit)).fetchall()
   for row in rows:
    event=Event(**json.loads(row["payload"]));is_late=event.event_time<now-self.allowed_lateness;late+=int(is_late)
    if not is_late:self._update_online(event);processed+=1
    self.db.execute("INSERT OR REPLACE INTO offsets VALUES(?,?,?)",(group,partition,row["offset_id"]))
  self.db.commit();return {"processed":processed,"duplicates":duplicates,"late":late,"lag":self.lag(group)}
 def snapshot_offline(self,as_of:float)->int:
  rows=self.db.execute("SELECT payload FROM events WHERE event_time<=?",(as_of,)).fetchall();aggregates={}
  for row in rows:
   event=Event(**json.loads(row[0]));count,total=aggregates.get(event.user_id,(0,0.0));aggregates[event.user_id]=(count+1,total+event.value)
  for user,(count,total) in aggregates.items():self.db.execute("INSERT OR REPLACE INTO offline_features VALUES(?,?,?,?)",(user,as_of,count,total))
  self.db.commit();return len(aggregates)
 def feature(self,user:str)->dict|None:
  row=self.db.execute("SELECT * FROM online_features WHERE user_id=?",(user,)).fetchone();return dict(row) if row else None
 def point_in_time(self,user:str,as_of:float)->dict|None:
  row=self.db.execute("SELECT * FROM offline_features WHERE user_id=? AND as_of<=? ORDER BY as_of DESC LIMIT 1",(user,as_of)).fetchone();return dict(row) if row else None
 def skew(self,user:str,as_of:float)->dict:
  online=self.feature(user);offline=self.point_in_time(user,as_of)
  if not online or not offline:return {"skew":True,"reason":"missing feature"}
  fields=("event_count","total_value");diff={f:online[f]-offline[f] for f in fields};return {"skew":any(abs(v)>1e-9 for v in diff.values()),"difference":diff}
 def lag(self,group:str)->int:
  total=0
  for p in range(self.partitions):
   maximum=self.db.execute("SELECT COALESCE(MAX(offset_id),-1) FROM events WHERE partition_id=?",(p,)).fetchone()[0];row=self.db.execute("SELECT offset_id FROM offsets WHERE group_id=? AND partition_id=?",(group,p)).fetchone();current=row[0] if row else -1;total+=max(0,maximum-current)
  return total
 def freshness(self,user:str,now:float|None=None)->float|None:
  row=self.feature(user);return None if not row else (now or time.time())-row["last_event_time"]
 def _update_online(self,event:Event):
  row=self.db.execute("SELECT * FROM online_features WHERE user_id=?",(event.user_id,)).fetchone()
  if row:self.db.execute("UPDATE online_features SET event_count=?,total_value=?,last_event_time=?,updated_at=? WHERE user_id=?",(row["event_count"]+1,row["total_value"]+event.value,max(row["last_event_time"],event.event_time),time.time(),event.user_id))
  else:self.db.execute("INSERT INTO online_features VALUES(?,?,?,?,?)",(event.user_id,1,event.value,event.event_time,time.time()))
 def _dlq(self,event:Event,error:str)->dict:self.db.execute("INSERT OR REPLACE INTO dlq VALUES(?,?,?,?)",(event.id,json.dumps(event.__dict__),error,time.time()));self.db.commit();return {"status":"dlq","error":error}
