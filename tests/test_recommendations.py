import pytest
from ailab.recommendations import *
def test_cold_start_returns_catalog(tmp_path):
 p=RecommendationPlatform(tmp_path/"r.db",demo_catalog());assert len(p.recommend("new",3))==3 and all("cold-start" in r.reasons[0] for r in p.recommend("new",3))
def test_content_affinity_and_consumed_exclusion(tmp_path):
 p=RecommendationPlatform(tmp_path/"r.db",demo_catalog());p.interact("u","ml-book","purchase");recs=p.recommend("u",5);assert recs[0].item_id in {"gpu-course","python-lab"} and "ml-book" not in [r.item_id for r in recs]
def test_collaborative_signal(tmp_path):
 p=RecommendationPlatform(tmp_path/"r.db",demo_catalog());p.interact("u","ml-book");p.interact("other","ml-book");p.interact("other","security-lab","purchase");assert "similar users" in next(r for r in p.recommend("u") if r.item_id=="security-lab").reasons
def test_invalid_interaction_rejected(tmp_path):
 p=RecommendationPlatform(tmp_path/"r.db",demo_catalog());
 with pytest.raises(ValueError):p.interact("u","missing")
def test_metrics_exact_values():
 m=ranking_metrics(["ml-book","cloud-book"],{"ml-book"},demo_catalog(),2);assert m["precision_at_k"]==.5 and m["recall_at_k"]==1 and m["ndcg_at_k"]==1
def test_assignment_is_sticky(tmp_path):
 p=RecommendationPlatform(tmp_path/"r.db",demo_catalog());assert p.assign("u")==p.assign("u")
def test_experiment_requires_both_variants(tmp_path):
 p=RecommendationPlatform(tmp_path/"r.db",demo_catalog());p.outcome("u",True);assert not p.analyze()["ready"]
def test_experiment_analysis(tmp_path):
 p=RecommendationPlatform(tmp_path/"r.db",demo_catalog());
 for i in range(300):
  user=f"u{i}";variant=p.assign(user);p.outcome(user,(i%5==0) if variant=="control" else (i%3==0))
 assert p.analyze()["ready"]
