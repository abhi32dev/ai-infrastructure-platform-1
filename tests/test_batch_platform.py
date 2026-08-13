from collections import Counter
import pytest
from ailab.batch_platform import *
def items():return [WorkItem(str(i),f"data-{i}",size) for i,size in enumerate([900,500,400,100,50])]
def test_adaptive_size_aware_batches(tmp_path):
 p=SelfHealingBatchPlatform(tmp_path/"b.db",1000,3);b=p.plan(items());assert all(x.total_bytes<=1000 or len(x.items)==1 for x in b) and sum(len(x.items) for x in b)==5
def test_happy_parallel_execution(tmp_path):
 p=SelfHealingBatchPlatform(tmp_path/"b.db");r=p.execute(items(),lambda x:x.payload.upper());assert r["status"]=="completed" and not r["missing"]
def test_transient_failure_retried(tmp_path):
 p=SelfHealingBatchPlatform(tmp_path/"b.db");calls=Counter()
 def worker(x):calls[x.id]+=1;
 def actual(x):
  calls[x.id]+=1
  if x.id=="1" and calls[x.id]==1:raise RuntimeError("transient")
  return x.payload
 r=p.execute(items(),actual);assert r["status"]=="completed" and calls["1"]==2
def test_resume_does_not_repeat_completed(tmp_path):
 p=SelfHealingBatchPlatform(tmp_path/"b.db");calls=Counter();worker=lambda x:(calls.update([x.id]) or x.payload);first=p.execute(items(),worker);p.execute(items(),worker,first["run_id"]);assert all(v==1 for v in calls.values())
def test_three_pass_reconciliation_recovers_missing_output(tmp_path):
 p=SelfHealingBatchPlatform(tmp_path/"b.db");r=p.execute(items(),lambda x:x.payload);p.db.execute("DELETE FROM outputs WHERE item_id='2'");p.db.commit();calls=Counter();re=p.reconcile(r["run_id"],items(),lambda x:(calls.update([x.id]) or x.payload));assert not re["missing"] and calls["2"]==1
def test_permanent_failure_remains_missing(tmp_path):
 p=SelfHealingBatchPlatform(tmp_path/"b.db");r=p.execute([WorkItem("x","bad",1)],lambda x:(_ for _ in ()).throw(RuntimeError("permanent")),max_attempts=1);assert r["status"]=="failed" and r["missing"]==["x"]
def test_ttl_dedup_across_runs(tmp_path):
 p=SelfHealingBatchPlatform(tmp_path/"b.db",ttl_seconds=100);calls=Counter();worker=lambda x:(calls.update([x.id]) or x.payload);p.execute(items(),worker);p.execute(items(),worker);assert all(v==1 for v in calls.values())
def test_bad_config_rejected(tmp_path):
 with pytest.raises(ValueError):SelfHealingBatchPlatform(tmp_path/"x",max_workers=0)
