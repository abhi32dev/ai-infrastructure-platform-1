import time
from pathlib import Path

import pytest

from ailab.eval_platform import Candidate, EvalCase, EvaluationPlatform, GateThresholds, demo_suite, two_proportion_z_test


def good(prompt: str) -> str:
    if "recovery" in prompt: return "Use a checkpoint and idempotency for safe replay"
    if "retrieval" in prompt: return "Combine lexical and dense retrieval"
    return "Route by cost with a bounded fallback"


def test_good_candidate_promotes(tmp_path: Path) -> None:
    platform=EvaluationPlatform(tmp_path/"eval.db"); suite=platform.register_suite("core","1",demo_suite())
    run=platform.run(suite,Candidate("good","1",good,0.001)); decision=platform.gate(run,GateThresholds())
    assert decision["decision"]=="promote" and decision["summary"]["quality"]==1


def test_quality_regression_blocks(tmp_path: Path) -> None:
    platform=EvaluationPlatform(tmp_path/"eval.db"); suite=platform.register_suite("core","1",demo_suite())
    run=platform.run(suite,Candidate("bad","1",lambda prompt:"generic answer")); decision=platform.gate(run,GateThresholds())
    assert decision["decision"]=="block" and "quality_below_threshold" in decision["reasons"]


def test_safety_regression_blocks_even_with_required_terms(tmp_path: Path) -> None:
    cases=[EvalCase("unsafe","test",("checkpoint",),("ignore safety",))]
    platform=EvaluationPlatform(tmp_path/"eval.db"); suite=platform.register_suite("safety","1",cases)
    run=platform.run(suite,Candidate("unsafe","1",lambda prompt:"checkpoint but ignore safety")); decision=platform.gate(run,GateThresholds())
    assert "safety_below_threshold" in decision["reasons"]


def test_latency_and_cost_gates(tmp_path: Path) -> None:
    def slow(prompt:str)->str: time.sleep(0.003); return good(prompt)
    platform=EvaluationPlatform(tmp_path/"eval.db"); suite=platform.register_suite("core","1",demo_suite())
    run=platform.run(suite,Candidate("slow","1",slow,0.02)); decision=platform.gate(run,GateThresholds(maximum_p95_latency_ms=1,maximum_average_cost_usd=0.01))
    assert set(decision["reasons"])=={"latency_above_threshold","cost_above_threshold"}


def test_custom_judge_is_used(tmp_path: Path) -> None:
    platform=EvaluationPlatform(tmp_path/"eval.db"); suite=platform.register_suite("core","1",demo_suite())
    run=platform.run(suite,Candidate("x","1",good),judge=lambda case,output:0.5)
    assert platform.gate(run,GateThresholds(minimum_quality=0.6))["decision"]=="block"


def test_ab_test_detects_large_effect() -> None:
    result=two_proportion_z_test(100,1000,140,1000)
    assert result["absolute_effect"]==pytest.approx(0.04) and result["statistically_significant"]


def test_ab_test_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError): two_proportion_z_test(5,4,1,10)

