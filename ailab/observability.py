from __future__ import annotations
import json,math,sqlite3,time,uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class SLO:service:str;target:float;window_seconds:float

class Telemetry:
 def __init__(self,path:Path):
  path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row;self.db.executescript("""CREATE TABLE IF NOT EXISTS spans(trace_id TEXT,span_id TEXT,parent_id TEXT,name TEXT,start REAL,end REAL,status TEXT,attributes TEXT);CREATE TABLE IF NOT EXISTS logs(timestamp REAL,level TEXT,message TEXT,trace_id TEXT,attributes TEXT);CREATE TABLE IF NOT EXISTS requests(timestamp REAL,service TEXT,success INTEGER,latency_ms REAL,tokens_in INTEGER,tokens_out INTEGER,cost REAL,model TEXT,tenant TEXT,cache_hit INTEGER);CREATE TABLE IF NOT EXISTS alerts(key TEXT PRIMARY KEY,last_sent REAL,count INTEGER);CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY,service TEXT,started REAL,ended REAL,summary TEXT);""");self.db.commit()
 @contextmanager
 def span(self,name:str,trace_id:str|None=None,parent_id:str|None=None,**attributes):
  trace_id=trace_id or uuid.uuid4().hex;span_id=uuid.uuid4().hex[:16];start=time.time();status="ok"
  try:yield {"trace_id":trace_id,"span_id":span_id}
  except Exception:status="error";raise
  finally:self.db.execute("INSERT INTO spans VALUES(?,?,?,?,?,?,?,?)",(trace_id,span_id,parent_id,name,start,time.time(),status,json.dumps(attributes)));self.db.commit()
 def log(self,level,message,trace_id="",**attributes):self.db.execute("INSERT INTO logs VALUES(?,?,?,?,?)",(time.time(),level,message,trace_id,json.dumps(attributes)));self.db.commit()
 def request(self,service,success,latency_ms,tokens_in=0,tokens_out=0,cost=0.0,model="",tenant="",cache_hit=False,timestamp=None):self.db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?,?)",(timestamp or time.time(),service,int(success),latency_ms,tokens_in,tokens_out,cost,model,tenant,int(cache_hit)));self.db.commit()
 def service_metrics(self,service,since:float=0)->dict:
  rows=self.db.execute("SELECT * FROM requests WHERE service=? AND timestamp>=?",(service,since)).fetchall()
  if not rows:return {"requests":0,"availability":None,"p95_latency_ms":None,"cost":0,"tokens":0,"cache_hit_rate":None}
  lat=sorted(r["latency_ms"] for r in rows);return {"requests":len(rows),"availability":sum(r["success"] for r in rows)/len(rows),"p95_latency_ms":lat[max(0,math.ceil(.95*len(lat))-1)],"cost":sum(r["cost"] for r in rows),"tokens":sum(r["tokens_in"]+r["tokens_out"] for r in rows),"cache_hit_rate":sum(r["cache_hit"] for r in rows)/len(rows)}
 def error_budget(self,slo:SLO,now:float|None=None)->dict:
  now=now or time.time();m=self.service_metrics(slo.service,now-slo.window_seconds)
  if not m["requests"]:return {"status":"no_data"}
  allowed=1-slo.target;observed=1-m["availability"];consumed=observed/allowed if allowed else (float("inf") if observed else 0);return {"status":"ok","target":slo.target,"availability":m["availability"],"allowed_error_rate":allowed,"observed_error_rate":observed,"budget_consumed_ratio":consumed,"budget_remaining_ratio":1-consumed}
 def burn_rate(self,slo:SLO,lookback:float,now:float|None=None)->float:
  now=now or time.time();m=self.service_metrics(slo.service,now-lookback)
  if not m["requests"]:return 0
  return (1-m["availability"])/(1-slo.target)
 def alert(self,key:str,condition:bool,cooldown_seconds:float=300,now:float|None=None)->dict:
  now=now or time.time();row=self.db.execute("SELECT * FROM alerts WHERE key=?",(key,)).fetchone()
  if not condition:return {"sent":False,"reason":"condition_false"}
  if row and now-row["last_sent"]<cooldown_seconds:return {"sent":False,"reason":"cooldown"}
  count=(row["count"] if row else 0)+1;self.db.execute("INSERT OR REPLACE INTO alerts VALUES(?,?,?)",(key,now,count));self.db.commit();return {"sent":True,"count":count}
 def multi_window_burn_alert(self,slo:SLO,short_window:float,long_window:float,short_threshold:float=14.4,long_threshold:float=6,now:float|None=None)->dict:
  short=self.burn_rate(slo,short_window,now);long=self.burn_rate(slo,long_window,now);decision=self.alert(f"{slo.service}:burn",short>=short_threshold and long>=long_threshold,now=now);return {"short_burn":short,"long_burn":long,**decision}
 def cost_breakdown(self)->dict:
  rows=self.db.execute("SELECT tenant,model,SUM(cost) cost,SUM(tokens_in+tokens_out) tokens,COUNT(*) requests FROM requests GROUP BY tenant,model").fetchall();return {"total":sum(r["cost"] for r in rows),"dimensions":[dict(r) for r in rows]}
 def right_size(self,service:str,provisioned_rps:float,window_seconds:float)->dict:
  now=time.time();count=self.db.execute("SELECT COUNT(*) FROM requests WHERE service=? AND timestamp>=?",(service,now-window_seconds)).fetchone()[0];observed=count/window_seconds;util=observed/provisioned_rps if provisioned_rps else 0;action="scale_down" if util<.3 else "scale_up" if util>.8 else "keep";return {"observed_rps":observed,"provisioned_rps":provisioned_rps,"utilization":util,"recommendation":action}
 def timeline(self,trace_id:str)->list[dict]:
  events=[{"timestamp":r["start"],"type":"span_start","name":r["name"],"status":r["status"]} for r in self.db.execute("SELECT * FROM spans WHERE trace_id=?",(trace_id,))];events += [{"timestamp":r["timestamp"],"type":"log","name":r["message"],"status":r["level"]} for r in self.db.execute("SELECT * FROM logs WHERE trace_id=?",(trace_id,))];return sorted(events,key=lambda x:x["timestamp"])
