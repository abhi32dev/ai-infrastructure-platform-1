from ailab.eval_platform import EvalCase, consensus_judge

def test_multi_judge_median_resists_outlier():
    judge = consensus_judge([("a", lambda c,o:.9), ("b", lambda c,o:.8), ("bad", lambda c,o:.0)])
    assert judge(EvalCase("x","x",()), "x") == .8

def test_multi_judge_rejects_invalid_panel():
    try: consensus_judge([("a", lambda c,o:1), ("b", lambda c,o:1)])
    except ValueError as exc: assert "three" in str(exc)
    else: raise AssertionError("expected invalid panel")
