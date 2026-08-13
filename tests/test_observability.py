import time
from ailab.observability import *
def test_correlated_trace_log_timeline(tmp_path):
 t=Telemetry(tmp_path/"o.db");
 with t.span("request") as s:t.log("INFO","route selected",s["trace_id"])
 timeline=t.timeline(s["trace_id"]);assert [x["type"] for x in timeline]==["span_start","log"]
def test_span_records_error(tmp_path):
 t=Telemetry(tmp_path/"o.db");
 try:
  with t.span("bad"):raise RuntimeError("x")
 except RuntimeError:pass
 assert t.db.execute("select status from spans").fetchone()[0]=="error"
def test_red_ai_and_cost_metrics(tmp_path):
 t=Telemetry(tmp_path/"o.db");[t.request("gateway",i<9,10+i,tokens_in=10,tokens_out=5,cost=.01,model="m",tenant="a",cache_hit=i%2==0) for i in range(10)];m=t.service_metrics("gateway");assert m["requests"]==10 and m["availability"]==.9 and m["tokens"]==150 and round(m["cost"],5)==.1
def test_error_budget_calculation(tmp_path):
 t=Telemetry(tmp_path/"o.db");now=time.time();[t.request("s",i<99,1,timestamp=now) for i in range(100)];b=t.error_budget(SLO("s",.99,3600),now);assert round(b["budget_consumed_ratio"],5)==1
def test_multi_window_burn_alert_and_cooldown(tmp_path):
 t=Telemetry(tmp_path/"o.db");now=time.time();[t.request("s",False,1,timestamp=now) for _ in range(10)];s=SLO("s",.99,3600);first=t.multi_window_burn_alert(s,300,3600,now=now);second=t.multi_window_burn_alert(s,300,3600,now=now+1);assert first["sent"] and second["reason"]=="cooldown"
def test_cost_breakdown(tmp_path):
 t=Telemetry(tmp_path/"o.db");t.request("s",True,1,cost=.2,tenant="a",model="large");t.request("s",True,1,cost=.1,tenant="b",model="small");assert round(t.cost_breakdown()["total"],5)==.3
def test_right_sizing(tmp_path):
 t=Telemetry(tmp_path/"o.db");assert t.right_size("empty",100,60)["recommendation"]=="scale_down"
