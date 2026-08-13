import numpy as np,pytest
from ailab.ml_lifecycle import *
def trained():
 x,y=make_dataset();xt,xv,yt,yv=split(x,y);m=LogisticModel(x.shape[1]).train(xt,yt);return x,xv,yv,m,evaluate(yv,m.predict(xv))
def test_reproducible_dataset():assert np.array_equal(make_dataset(seed=1)[0],make_dataset(seed=1)[0])
def test_validation_rejects_nan():
 x,y=make_dataset(10);x[0,0]=np.nan
 with pytest.raises(DataValidationError):validate(x,y)
def test_training_quality():assert trained()[-1].f1>.85
def test_registry_promotion_serving_and_rollback(tmp_path):
 x,xv,yv,m,metrics=trained();_,y=make_dataset();r=ModelRegistry(tmp_path/"models");r.register(m,metrics,x.mean(0),"v1");r.promote("v1");m2=LogisticModel(x.shape[1]).train(x,y);r.register(m2,evaluate(y,m2.predict(x)),x.mean(0),"v2");r.promote("v2");assert r.data["production"]=="v2";r.rollback();assert r.data["production"]=="v1" and len(r.load().weights)==x.shape[1]
def test_promotion_gate_blocks_bad_model(tmp_path):
 r=ModelRegistry(tmp_path/"m");m=LogisticModel(2);r.register(m,Metrics(.5,.5,.5,.5),[0,0],"bad")
 with pytest.raises(ValueError,match="quality"):r.promote("bad")
def test_drift_retraining_signal(tmp_path):
 x,xv,yv,m,metrics=trained();r=ModelRegistry(tmp_path/"m");r.register(m,metrics,x.mean(0),"v1");r.promote("v1");shifted,_=make_dataset(100,shift=2);assert r.drift(shifted)["retrain_recommended"]
def test_detector_and_iou():
 f=np.zeros((20,20));f[2:5,3:7]=1;boxes=detect(f);assert boxes==[Box(3,2,7,5)] and iou(boxes[0],Box(3,2,7,5))==1
def test_tracker_preserves_identity():
 t=CentroidTracker();one=t.update([Box(1,1,3,3)]);two=t.update([Box(2,1,4,3)]);assert list(one)==list(two)
