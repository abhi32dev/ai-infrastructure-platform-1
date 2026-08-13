import json,math,pytest
from ailab.multi_framework import *
@pytest.mark.parametrize("xs,ys",[([],[]),([1],[2]),([1,2],[2]),([1,1],[2,2]),([1,math.nan],[2,3]),([1,2],[2,math.inf])])
def test_invalid_training_data_matrix(xs,ys):
 with pytest.raises(ValueError):train_linear(xs,ys)
def test_training_exact_linear_relation():
 m=train_linear([1,2,3],[3,5,7]);assert m.weight==2 and m.bias==1 and m.predict(4)==9
@pytest.mark.parametrize("value",[math.nan,math.inf,-math.inf])
def test_nonfinite_prediction_rejected(value):
 with pytest.raises(ValueError):PortableLinearModel(1,0,"x").predict(value)
def test_artifact_round_trip(tmp_path):
 p=tmp_path/"m.json";PortableLinearModel(2,1,"torch").save(p);assert PortableLinearModel.load(p).predict(2)==5
def test_missing_artifact(tmp_path):
 with pytest.raises(FileNotFoundError):PortableLinearModel.load(tmp_path/"missing")
@pytest.mark.parametrize("payload",[{"schema_version":2,"weight":1,"bias":0,"framework":"x"},{"schema_version":1,"weight":"NaN","bias":0,"framework":"x"}])
def test_corrupt_artifact_matrix(tmp_path,payload):
 p=tmp_path/"m";p.write_text(json.dumps(payload))
 with pytest.raises(ValueError):PortableLinearModel.load(p)
def test_parity_happy_and_failure():
 assert parity([PortableLinearModel(1,0,"a"),PortableLinearModel(1,0,"b")],[1])["passed"]
 assert not parity([PortableLinearModel(1,0,"a"),PortableLinearModel(2,0,"b")],[1])["passed"]
@pytest.mark.parametrize("models,inputs,tol",[([], [1],0),([PortableLinearModel(1,0,"x")],[],0),([PortableLinearModel(1,0,"x")],[1],-1)])
def test_invalid_parity_inputs(models,inputs,tol):
 with pytest.raises(ValueError):parity(models,inputs,tol)
def test_inventory_contract():assert set(installed_frameworks())=={"torch","tensorflow","keras","jax","onnxruntime"}
