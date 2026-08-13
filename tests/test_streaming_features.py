import time
from pathlib import Path
from ailab.streaming_features import *
def e(i,user="u",value=1,t=None,version=1):return Event(str(i),user,"click",value,t or time.time(),version)
def test_partition_order_offsets_and_features(tmp_path):
 p=StreamingFeaturePlatform(tmp_path/"s.db");[p.publish(e(i,value=i)) for i in range(1,4)];assert p.lag("g")==3;r=p.consume("g");assert r["lag"]==0 and p.feature("u")["total_value"]==6
def test_duplicate_event_not_reprocessed(tmp_path):
 p=StreamingFeaturePlatform(tmp_path/"s.db");assert p.publish(e(1))["status"]=="published";assert p.publish(e(1))["status"]=="duplicate";p.consume("g");assert p.feature("u")["event_count"]==1
def test_consumer_groups_independent(tmp_path):
 p=StreamingFeaturePlatform(tmp_path/"s.db");p.publish(e(1));p.consume("a");assert p.lag("a")==0 and p.lag("b")==1
def test_late_event_excluded_online(tmp_path):
 now=time.time();p=StreamingFeaturePlatform(tmp_path/"s.db",allowed_lateness=10);p.publish(e(1,t=now-20));r=p.consume("g",now=now);assert r["late"]==1 and p.feature("u") is None
def test_bad_schema_goes_dlq(tmp_path):
 p=StreamingFeaturePlatform(tmp_path/"s.db");assert p.publish(e(1,version=99))["status"]=="dlq";assert p.db.execute("select count(*) from dlq").fetchone()[0]==1
def test_point_in_time_and_consistency(tmp_path):
 now=time.time();p=StreamingFeaturePlatform(tmp_path/"s.db");p.publish(e(1,value=2,t=now-2));p.publish(e(2,value=3,t=now-1));p.consume("g",now=now);p.snapshot_offline(now);assert not p.skew("u",now)["skew"] and p.point_in_time("u",now)["total_value"]==5
def test_skew_detected_after_new_online_event(tmp_path):
 now=time.time();p=StreamingFeaturePlatform(tmp_path/"s.db");p.publish(e(1,t=now-2));p.consume("g",now=now);p.snapshot_offline(now);p.publish(e(2,t=now+1));p.consume("g",now=now+1);assert p.skew("u",now)["skew"]
