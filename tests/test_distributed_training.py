import math,pytest
from ailab.distributed_training import *
def data(n=8):return [Sample(float(i),2.0*i) for i in range(1,n+1)]
@pytest.mark.parametrize("field,value",[("world_size",0),("epochs",0),("gradient_accumulation",0),("checkpoint_every",0),("learning_rate",0),("learning_rate",-1),("learning_rate",math.nan),("learning_rate",math.inf)])
def test_invalid_config_matrix(field,value):
 values=TrainingConfig().__dict__|{field:value}
 with pytest.raises(ValueError):TrainingConfig(**values).validate()
def test_empty_data_rejected(tmp_path):
 with pytest.raises(ValueError):DistributedTrainer(tmp_path,TrainingConfig()).train([])
def test_world_larger_than_data_rejected(tmp_path):
 with pytest.raises(ValueError):DistributedTrainer(tmp_path,TrainingConfig(world_size=3)).train(data(2))
@pytest.mark.parametrize("run_id",["","../escape","a/b"])
def test_unsafe_run_ids_rejected(tmp_path,run_id):
 with pytest.raises(ValueError):DistributedTrainer(tmp_path,TrainingConfig()).train(data(),run_id)
def test_partition_has_no_overlap(tmp_path):
 t=DistributedTrainer(tmp_path,TrainingConfig(world_size=3));parts=t.partition(data(9));assert sorted(x.x for p in parts for x in p)==list(map(float,range(1,10)))
def test_training_converges_and_checkpoints(tmp_path):
 r=DistributedTrainer(tmp_path,TrainingConfig(epochs=20,learning_rate=.005)).train(data());assert abs(r["weight"]-2)<.1 and (tmp_path/"run.json").exists()
def test_failure_checkpoint_and_resume(tmp_path):
 t=DistributedTrainer(tmp_path,TrainingConfig(epochs=4,learning_rate=.001))
 with pytest.raises(TrainingError):t.train(data(),"recover",fail_at=(1,1))
 r=t.train(data(),"recover",resume=True);assert r["epoch"]==4
def test_resume_missing_checkpoint_rejected(tmp_path):
 with pytest.raises(TrainingError):DistributedTrainer(tmp_path,TrainingConfig()).train(data(),resume=True)
def test_checksum_deterministic(tmp_path):
 t=DistributedTrainer(tmp_path,TrainingConfig());assert t.train(data(),"a")["checksum"]==t.train(data(),"b")["checksum"]
def test_framework_inventory_contract():assert set(framework_inventory())=={"torch","tensorflow","jax"}
