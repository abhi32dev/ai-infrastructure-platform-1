import time
from pathlib import Path

import pytest

from ailab.agent_runtime import (
    AgentPlan,
    AgentRuntimeError,
    AgentStep,
    ApprovalRequired,
    DurableAgentRuntime,
    PolicyDenied,
    ToolRegistry,
    ToolSpec,
    demo_plan,
    demo_registry,
)


TOOLS = {"lookup_incident", "draft_remediation", "apply_remediation"}


def test_happy_path_pauses_for_approval_then_resumes_once(tmp_path: Path) -> None:
    effects: list[str] = []
    runtime = DurableAgentRuntime(tmp_path / "agent.db", demo_registry(effects), TOOLS)
    with pytest.raises(ApprovalRequired) as waiting:
        runtime.start(demo_plan())
    run_id = waiting.value.run_id
    before = runtime.inspect(run_id)
    assert before["run"]["status"] == "waiting_approval"
    assert effects == []

    runtime.approve(run_id, "apply", "reviewer", "plan inspected")
    result = runtime.resume(run_id)
    assert result.status == "completed"
    assert effects == ["restart model-gateway"]

    repeated = runtime.resume(run_id)
    assert repeated.status == "completed"
    assert effects == ["restart model-gateway"]


def test_denied_action_never_executes(tmp_path: Path) -> None:
    effects: list[str] = []
    runtime = DurableAgentRuntime(tmp_path / "agent.db", demo_registry(effects), TOOLS)
    with pytest.raises(ApprovalRequired) as waiting:
        runtime.start(demo_plan("INC-DENY"))
    runtime.deny(waiting.value.run_id, "apply", "reviewer", "unsafe")
    result = runtime.resume(waiting.value.run_id)
    assert result.status == "denied"
    assert effects == []


def test_tool_outside_allowlist_is_denied(tmp_path: Path) -> None:
    runtime = DurableAgentRuntime(tmp_path / "agent.db", demo_registry(), {"lookup_incident"})
    with pytest.raises(PolicyDenied, match="allowlist"):
        runtime.start(demo_plan())


def test_missing_tool_argument_is_rejected(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(ToolSpec("requires_value", lambda args: args, frozenset({"value"})))
    runtime = DurableAgentRuntime(tmp_path / "agent.db", registry, {"requires_value"})
    plan = AgentPlan("invalid arguments", (AgentStep("bad", "requires_value", {}, "output"),))
    with pytest.raises(ValueError, match="missing arguments"):
        runtime.start(plan)


def test_retry_exhaustion_writes_dead_letter(tmp_path: Path) -> None:
    registry = ToolRegistry()
    calls = {"count": 0}

    def fail(args: dict) -> dict:
        calls["count"] += 1
        raise RuntimeError("dependency unavailable")

    registry.register(ToolSpec("unstable", fail, max_attempts=2))
    runtime = DurableAgentRuntime(tmp_path / "agent.db", registry, {"unstable"})
    plan = AgentPlan("failure", (AgentStep("fail", "unstable", {}, "result"),))
    with pytest.raises(AgentRuntimeError, match="exhausted retries"):
        runtime.start(plan, run_id="failed-run")
    inspected = runtime.inspect("failed-run")
    assert calls["count"] == 2
    assert inspected["run"]["status"] == "failed"
    assert inspected["dead_letters"][0]["attempts"] == 2


def test_timeout_is_bounded_and_dead_lettered(tmp_path: Path) -> None:
    registry = ToolRegistry()

    def slow(args: dict) -> dict:
        time.sleep(0.03)
        return {"too_late": True}

    registry.register(ToolSpec("slow", slow, timeout_seconds=0.001, max_attempts=1))
    runtime = DurableAgentRuntime(tmp_path / "agent.db", registry, {"slow"})
    plan = AgentPlan("timeout", (AgentStep("slow-step", "slow", {}, "result"),))
    with pytest.raises(AgentRuntimeError, match="ToolTimeout"):
        runtime.start(plan, run_id="timeout-run")
    assert "ToolTimeout" in runtime.inspect("timeout-run")["dead_letters"][0]["error"]


def test_plan_rejects_forward_or_missing_dependency(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(ToolSpec("noop", lambda args: {}))
    runtime = DurableAgentRuntime(tmp_path / "agent.db", registry, {"noop"})
    plan = AgentPlan("bad graph", (AgentStep("first", "noop", {}, "x", ("later",)), AgentStep("later", "noop", {}, "y")))
    with pytest.raises(ValueError, match="unresolved dependencies"):
        runtime.start(plan)

