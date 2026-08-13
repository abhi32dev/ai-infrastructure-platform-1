#!/usr/bin/env python3
"""Project 2 acceptance verification with stored evidence."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailab.agent_runtime import (  # noqa: E402
    AgentPlan, AgentRuntimeError, AgentStep, ApprovalRequired,
    DurableAgentRuntime, PolicyDenied, ToolRegistry, ToolSpec,
    demo_plan, demo_registry,
)


def check(name: str, category: str, operation: Callable[[], dict]) -> dict:
    started = time.perf_counter()
    try:
        evidence = operation()
        return {"name": name, "category": category, "status": "passed", "duration_ms": round((time.perf_counter() - started) * 1000, 3), "evidence": evidence}
    except Exception as exc:
        return {"name": name, "category": category, "status": "failed", "duration_ms": round((time.perf_counter() - started) * 1000, 3), "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="ailab-agent-verification-") as directory:
        root = Path(directory)

        def approval_resume() -> dict:
            effects: list[str] = []
            runtime = DurableAgentRuntime(root / "happy.db", demo_registry(effects), {"lookup_incident", "draft_remediation", "apply_remediation"})
            try:
                try:
                    runtime.start(demo_plan())
                    raise AssertionError("high-risk action did not pause")
                except ApprovalRequired as waiting:
                    run_id = waiting.run_id
                runtime.approve(run_id, "apply", "verification-user", "reviewed")
                result = runtime.resume(run_id)
                runtime.resume(run_id)
                assert result.status == "completed" and len(effects) == 1
                return {"run_id": run_id, "status": result.status, "side_effect_count_after_second_resume": len(effects), "event_types": [row["event_type"] for row in runtime.inspect(run_id)["events"]]}
            finally:
                runtime.close()

        results.append(check("approval_checkpoint_and_idempotent_resume", "happy_path", approval_resume))

        def denial() -> dict:
            effects: list[str] = []
            runtime = DurableAgentRuntime(root / "deny.db", demo_registry(effects), {"lookup_incident", "draft_remediation", "apply_remediation"})
            try:
                try:
                    runtime.start(demo_plan("INC-DENY"))
                except ApprovalRequired as waiting:
                    run_id = waiting.run_id
                runtime.deny(run_id, "apply", "verification-user", "unsafe")
                result = runtime.resume(run_id)
                assert result.status == "denied" and effects == []
                return {"run_id": run_id, "status": result.status, "side_effect_count": 0}
            finally:
                runtime.close()

        results.append(check("human_denial_blocks_side_effect", "negative", denial))

        def policy() -> dict:
            runtime = DurableAgentRuntime(root / "policy.db", demo_registry(), {"lookup_incident"})
            try:
                try:
                    runtime.start(demo_plan())
                except PolicyDenied as exc:
                    return {"expected_error": str(exc)}
                raise AssertionError("policy did not deny tool")
            finally:
                runtime.close()

        results.append(check("least_privilege_tool_allowlist", "security", policy))

        def dead_letter() -> dict:
            registry = ToolRegistry()
            calls = {"count": 0}

            def broken(args: dict) -> dict:
                calls["count"] += 1
                raise RuntimeError("injected permanent failure")

            registry.register(ToolSpec("broken", broken, max_attempts=2))
            runtime = DurableAgentRuntime(root / "dlq.db", registry, {"broken"})
            plan = AgentPlan("dead letter", (AgentStep("broken-step", "broken", {}, "output"),))
            try:
                try:
                    runtime.start(plan, run_id="dead-letter-run")
                except AgentRuntimeError as exc:
                    record = runtime.inspect("dead-letter-run")["dead_letters"][0]
                    assert calls["count"] == 2 and record["attempts"] == 2
                    return {"expected_error": str(exc), "attempts": calls["count"], "dead_letter": record}
                raise AssertionError("retry exhaustion unexpectedly succeeded")
            finally:
                runtime.close()

        results.append(check("bounded_retry_and_dead_letter", "failure_recovery", dead_letter))

    tests = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_agent_runtime.py"], cwd=ROOT, text=True, capture_output=True)
    results.append({"name": "project_2_test_suite", "category": "tests", "status": "passed" if tests.returncode == 0 else "failed", "exit_code": tests.returncode, "stdout": tests.stdout.strip(), "stderr": tests.stderr.strip()})
    passed = sum(item["status"] == "passed" for item in results)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True).stdout.strip(), "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed}, "scenarios": results}
    destination = ROOT / "artifacts" / "project-2-agent-runtime"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "latest.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [f"Project 2 verification: {passed}/{len(results)} passed", *[f"[{item['status'].upper()}] {item['category']}: {item['name']}" for item in results]]
    (destination / "latest.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

