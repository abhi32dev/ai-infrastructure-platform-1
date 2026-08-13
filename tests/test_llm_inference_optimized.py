import math,time,pytest
from ailab.llm_inference_optimized import *
@pytest.mark.parametrize("case",[GenerationRequest("","x"),GenerationRequest("x"," "),GenerationRequest("x","x",0),GenerationRequest("x","x",4097),GenerationRequest("x","x",deadline=math.nan)])
def test_request_validation_matrix(case):
 with pytest.raises(ValueError):case.validate()
@pytest.mark.parametrize("capacity",[0,-1])
def test_invalid_cache_capacity(capacity):
 with pytest.raises(ValueError):KVCache(capacity)
def test_cache_reserve_duplicate_and_release():
 c=KVCache(3);assert c.reserve("a",2);assert not c.reserve("a",2);c.release("missing");c.release("a");assert c.used==0
def test_cache_rejects_negative_and_exhaustion():
 c=KVCache(1)
 with pytest.raises(ValueError):c.reserve("a",-1)
 with pytest.raises(CacheExhausted):c.reserve("a",2)
def test_invalid_batch_size():
 with pytest.raises(ValueError):ContinuousBatchEngine(0)
def test_expired_admission():
 with pytest.raises(AdmissionRejected):ContinuousBatchEngine().submit(GenerationRequest("a","x",deadline=time.time()-1))
def test_duplicate_request_idempotent():
 e=ContinuousBatchEngine();r=GenerationRequest("a","hello");assert e.submit(r)=="queued" and e.submit(r)=="duplicate";e.step();assert e.submit(r)=="duplicate"
def test_priority_and_bounded_batch():
 e=ContinuousBatchEngine(1);e.submit(GenerationRequest("low","x",priority=0));e.submit(GenerationRequest("high","x",priority=9));assert e.step()[0]["request_id"]=="high" and len(e.queue)==1
def test_prefix_cache_hit():
 e=ContinuousBatchEngine();e.submit(GenerationRequest("a","same prefix"));assert not e.step()[0]["prefix_cache_hit"];e.submit(GenerationRequest("b","same prefix"));assert e.step()[0]["prefix_cache_hit"]
@pytest.mark.parametrize("draft,target,accepted",[([],[],0),([1],[2],0),([1,2],[1,3],1),([1,2],[1,2],2),([1,2,3],[1,2],2)])
def test_speculative_acceptance_matrix(draft,target,accepted):assert ContinuousBatchEngine().speculative_acceptance(draft,target)["accepted"]==accepted
