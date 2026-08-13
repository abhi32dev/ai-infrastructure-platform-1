import math,pytest
from ailab.lakehouse_features import *
@pytest.mark.parametrize("event",[FeatureEvent("","e",1,1),FeatureEvent("x","",1,1),FeatureEvent("x","e",math.nan,1),FeatureEvent("x","e",1,math.inf),FeatureEvent("x","e",1,1,2)])
def test_contract_violations_go_to_dlq(event):
 p=LakehouseFeaturePlatform();assert p.ingest(event)=="dead_lettered" and len(p.dlq)==1
def test_duplicate_is_idempotent():
 p=LakehouseFeaturePlatform();e=FeatureEvent("1","u",1,2);assert p.ingest(e)=="ingested" and p.ingest(e)=="duplicate"
def test_watermark_excludes_future():
 p=LakehouseFeaturePlatform();p.ingest(FeatureEvent("1","u",20,2));assert p.compact(10)["rows"]==0
def test_compaction_is_idempotent():
 p=LakehouseFeaturePlatform();p.ingest(FeatureEvent("1","u",1,2));a=p.compact(2);b=p.compact(2);assert a["rows"]==b["rows"]==1
def test_point_in_time_avoids_leakage():
 p=LakehouseFeaturePlatform();[p.ingest(FeatureEvent(str(i),"u",i,float(i))) for i in (1,3,5)];p.compact(10);assert p.point_in_time("u",4)==3 and p.point_in_time("missing",4) is None
def test_online_uses_latest_as_of():
 p=LakehouseFeaturePlatform();p.ingest(FeatureEvent("1","u",1,1));p.ingest(FeatureEvent("2","u",2,2));p.compact(3);assert p.materialize_online(1.5)=={"u":1}
def test_equal_timestamp_is_deterministic():
 p=LakehouseFeaturePlatform();p.ingest(FeatureEvent("a","u",1,1));p.ingest(FeatureEvent("b","u",1,2));p.compact(2);assert p.point_in_time("u",1) in {1,2}
def test_quality_reports_rows_dlq_and_commits():
 p=LakehouseFeaturePlatform();p.ingest(FeatureEvent("","u",1,1));p.ingest(FeatureEvent("1","u",1,1));p.compact(2);assert p.quality()=={"rows":1,"unique":True,"dlq":1,"commits":1}
