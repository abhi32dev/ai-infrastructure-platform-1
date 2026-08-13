from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


class AgentRuntimeError(RuntimeError):
    pass


class PolicyDenied(AgentRuntimeError):
    pass


class ApprovalRequired(AgentRuntimeError):
    def __init__(self, run_id: str, step_id: str) -> None:
        super().__init__(f"approval required for run={run_id} step={step_id}")
        self.run_id = run_id
        self.step_id = step_id


class ToolTimeout(AgentRuntimeError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    required_arguments: frozenset[str] = frozenset()
    risk: str = "low"
    timeout_seconds: float = 2.0
    max_attempts: int = 3

    def validate(self, arguments: dict[str, Any]) -> None:
        missing = self.required_arguments - arguments.keys()
        if missing:
            raise ValueError(f"tool {self.name} missing arguments: {sorted(missing)}")


@dataclass(frozen=True)
class AgentStep:
    id: str
    tool: str
    arguments: dict[str, Any]
    save_as: str
    depends_on: tuple[str, ...] = ()
    requires_approval: bool = False


@dataclass(frozen=True)
class AgentPlan:
    objective: str
    steps: tuple[AgentStep, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    state: dict[str, Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ValueError(f"unknown tool: {name}") from exc


class DurableAgentRuntime:
    """SQLite-backed agent executor with policy, approvals, retries, and replay.

    A completed tool invocation is stored using an idempotency key before later
    steps run. Resuming the same plan reuses that durable result instead of
    invoking the tool twice.
    """

    def __init__(self, database: Path, registry: ToolRegistry, allowed_tools: set[str]) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.registry = registry
        self.allowed_tools = set(allowed_tools)
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY, objective TEXT NOT NULL, plan TEXT NOT NULL,
              status TEXT NOT NULL, state TEXT NOT NULL, created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_steps (
              run_id TEXT NOT NULL, step_id TEXT NOT NULL, tool TEXT NOT NULL,
              status TEXT NOT NULL, attempts INTEGER NOT NULL, output TEXT,
              error TEXT, updated_at REAL NOT NULL, PRIMARY KEY(run_id, step_id)
            );
            CREATE TABLE IF NOT EXISTS approvals (
              run_id TEXT NOT NULL, step_id TEXT NOT NULL, decision TEXT NOT NULL,
              actor TEXT NOT NULL, reason TEXT, updated_at REAL NOT NULL,
              PRIMARY KEY(run_id, step_id)
            );
            CREATE TABLE IF NOT EXISTS tool_effects (
              idempotency_key TEXT PRIMARY KEY, tool TEXT NOT NULL,
              output TEXT NOT NULL, created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS dead_letters (
              run_id TEXT NOT NULL, step_id TEXT NOT NULL, tool TEXT NOT NULL,
              arguments TEXT NOT NULL, error TEXT NOT NULL, attempts INTEGER NOT NULL,
              created_at REAL NOT NULL, PRIMARY KEY(run_id, step_id)
            );
            CREATE TABLE IF NOT EXISTS events (
              sequence INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
              event_type TEXT NOT NULL, payload TEXT NOT NULL, created_at REAL NOT NULL
            );
            """
        )
        self.connection.commit()

    def start(self, plan: AgentPlan, initial_state: dict[str, Any] | None = None, run_id: str | None = None) -> RunResult:
        self._validate_plan(plan)
        run_id = run_id or uuid.uuid4().hex
        now = time.time()
        existing = self.connection.execute("SELECT id FROM runs WHERE id=?", (run_id,)).fetchone()
        if not existing:
            self.connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, plan.objective, json.dumps(asdict(plan), sort_keys=True), "running", json.dumps(initial_state or {}, sort_keys=True), now, now),
            )
            self._event(run_id, "run_started", {"objective": plan.objective})
            self.connection.commit()
        return self.resume(run_id)

    def resume(self, run_id: str) -> RunResult:
        run = self._run_row(run_id)
        plan = self._deserialize_plan(json.loads(run["plan"]))
        state = json.loads(run["state"])
        for step in plan.steps:
            completed = self.connection.execute(
                "SELECT output FROM agent_steps WHERE run_id=? AND step_id=? AND status='completed'", (run_id, step.id)
            ).fetchone()
            if completed:
                state[step.save_as] = json.loads(completed["output"])
                continue
            self._assert_dependencies(run_id, step)
            tool = self.registry.get(step.tool)
            self._assert_policy(tool)
            if step.requires_approval or tool.risk == "high":
                decision = self.connection.execute("SELECT decision FROM approvals WHERE run_id=? AND step_id=?", (run_id, step.id)).fetchone()
                if not decision:
                    self._set_step(run_id, step, "waiting_approval", 0, None, None)
                    self._set_run(run_id, "waiting_approval", state)
                    self._event(run_id, "approval_requested", {"step_id": step.id, "tool": step.tool})
                    raise ApprovalRequired(run_id, step.id)
                if decision["decision"] != "approved":
                    self._set_step(run_id, step, "denied", 0, None, "human denied operation")
                    self._set_run(run_id, "denied", state)
                    return RunResult(run_id, "denied", state)
            arguments = self._resolve(step.arguments, state)
            tool.validate(arguments)
            output = self._execute(run_id, step, tool, arguments)
            state[step.save_as] = output
            self._set_run(run_id, "running", state)
        self._set_run(run_id, "completed", state)
        self._event(run_id, "run_completed", {"state_keys": sorted(state)})
        self.connection.commit()
        return RunResult(run_id, "completed", state)

    def approve(self, run_id: str, step_id: str, actor: str, reason: str = "") -> None:
        self._decision(run_id, step_id, "approved", actor, reason)

    def deny(self, run_id: str, step_id: str, actor: str, reason: str = "") -> None:
        self._decision(run_id, step_id, "denied", actor, reason)

    def inspect(self, run_id: str) -> dict[str, Any]:
        run = self._run_row(run_id)
        steps = [dict(row) for row in self.connection.execute("SELECT * FROM agent_steps WHERE run_id=? ORDER BY updated_at", (run_id,))]
        events = [dict(row) for row in self.connection.execute("SELECT * FROM events WHERE run_id=? ORDER BY sequence", (run_id,))]
        dead_letters = [dict(row) for row in self.connection.execute("SELECT * FROM dead_letters WHERE run_id=?", (run_id,))]
        return {"run": dict(run), "steps": steps, "events": events, "dead_letters": dead_letters}

    def _execute(self, run_id: str, step: AgentStep, tool: ToolSpec, arguments: dict[str, Any]) -> dict[str, Any]:
        key = hashlib.sha256(json.dumps({"run": run_id, "step": step.id, "tool": tool.name, "arguments": arguments}, sort_keys=True).encode()).hexdigest()
        cached = self.connection.execute("SELECT output FROM tool_effects WHERE idempotency_key=?", (key,)).fetchone()
        if cached:
            output = json.loads(cached["output"])
            self._set_step(run_id, step, "completed", 0, output, None)
            self._event(run_id, "tool_effect_reused", {"step_id": step.id, "idempotency_key": key})
            return output
        last_error = ""
        for attempt in range(1, tool.max_attempts + 1):
            self._set_step(run_id, step, "running", attempt, None, None)
            try:
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(tool.handler, dict(arguments))
                try:
                    output = future.result(timeout=tool.timeout_seconds)
                except FutureTimeout as exc:
                    future.cancel()
                    raise ToolTimeout(f"tool {tool.name} exceeded {tool.timeout_seconds}s") from exc
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)
                if not isinstance(output, dict):
                    raise TypeError(f"tool {tool.name} must return a dictionary")
                self.connection.execute("INSERT INTO tool_effects VALUES (?, ?, ?, ?)", (key, tool.name, json.dumps(output, sort_keys=True), time.time()))
                self._set_step(run_id, step, "completed", attempt, output, None)
                self._event(run_id, "tool_completed", {"step_id": step.id, "tool": tool.name, "attempt": attempt})
                self.connection.commit()
                return output
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                self._set_step(run_id, step, "failed", attempt, None, last_error)
                self._event(run_id, "tool_failed", {"step_id": step.id, "attempt": attempt, "error": last_error})
        self.connection.execute("INSERT OR REPLACE INTO dead_letters VALUES (?, ?, ?, ?, ?, ?, ?)", (run_id, step.id, tool.name, json.dumps(arguments, sort_keys=True), last_error, tool.max_attempts, time.time()))
        self._set_run(run_id, "failed", self._state(run_id))
        self.connection.commit()
        raise AgentRuntimeError(f"step {step.id} exhausted retries: {last_error}")

    def _validate_plan(self, plan: AgentPlan) -> None:
        ids = [step.id for step in plan.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step ids must be unique")
        known: set[str] = set()
        for step in plan.steps:
            unknown = set(step.depends_on) - known
            if unknown:
                raise ValueError(f"step {step.id} has unresolved dependencies: {sorted(unknown)}")
            self.registry.get(step.tool)
            known.add(step.id)

    def _assert_policy(self, tool: ToolSpec) -> None:
        if tool.name not in self.allowed_tools:
            raise PolicyDenied(f"tool is outside this runtime's allowlist: {tool.name}")

    def _assert_dependencies(self, run_id: str, step: AgentStep) -> None:
        for dependency in step.depends_on:
            row = self.connection.execute("SELECT status FROM agent_steps WHERE run_id=? AND step_id=?", (run_id, dependency)).fetchone()
            if not row or row["status"] != "completed":
                raise AgentRuntimeError(f"dependency {dependency} is not completed")

    def _resolve(self, value: Any, state: dict[str, Any]) -> Any:
        if isinstance(value, str) and value.startswith("$state."):
            current: Any = state
            for part in value[7:].split("."):
                current = current[part]
            return current
        if isinstance(value, dict):
            return {key: self._resolve(item, state) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve(item, state) for item in value]
        return value

    def _decision(self, run_id: str, step_id: str, decision: str, actor: str, reason: str) -> None:
        self._run_row(run_id)
        self.connection.execute("INSERT OR REPLACE INTO approvals VALUES (?, ?, ?, ?, ?, ?)", (run_id, step_id, decision, actor, reason, time.time()))
        self._event(run_id, f"approval_{decision}", {"step_id": step_id, "actor": actor, "reason": reason})
        self.connection.commit()

    def _set_step(self, run_id: str, step: AgentStep, status: str, attempts: int, output: dict[str, Any] | None, error: str | None) -> None:
        self.connection.execute(
            """INSERT INTO agent_steps VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, step_id) DO UPDATE SET status=excluded.status,
            attempts=excluded.attempts, output=excluded.output, error=excluded.error, updated_at=excluded.updated_at""",
            (run_id, step.id, step.tool, status, attempts, json.dumps(output, sort_keys=True) if output is not None else None, error, time.time()),
        )
        self.connection.commit()

    def _set_run(self, run_id: str, status: str, state: dict[str, Any]) -> None:
        self.connection.execute("UPDATE runs SET status=?, state=?, updated_at=? WHERE id=?", (status, json.dumps(state, sort_keys=True), time.time(), run_id))
        self.connection.commit()

    def _state(self, run_id: str) -> dict[str, Any]:
        return json.loads(self._run_row(run_id)["state"])

    def _run_row(self, run_id: str) -> sqlite3.Row:
        row = self.connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise ValueError(f"unknown run: {run_id}")
        return row

    def _event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.connection.execute("INSERT INTO events(run_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)", (run_id, event_type, json.dumps(payload, sort_keys=True), time.time()))

    @staticmethod
    def _deserialize_plan(value: dict[str, Any]) -> AgentPlan:
        steps = tuple(AgentStep(**{**step, "depends_on": tuple(step.get("depends_on", []))}) for step in value["steps"])
        return AgentPlan(value["objective"], steps, value.get("metadata", {}))


def demo_registry(effect_log: list[str] | None = None) -> ToolRegistry:
    effect_log = effect_log if effect_log is not None else []
    registry = ToolRegistry()
    registry.register(ToolSpec("lookup_incident", lambda args: {"incident_id": args["incident_id"], "severity": "high", "service": "model-gateway"}, frozenset({"incident_id"})))
    registry.register(ToolSpec("draft_remediation", lambda args: {"action": f"restart {args['service']}", "justification": "health checks are failing"}, frozenset({"service"})))

    def apply(args: dict[str, Any]) -> dict[str, Any]:
        effect_log.append(args["action"])
        return {"applied": True, "action": args["action"]}

    registry.register(ToolSpec("apply_remediation", apply, frozenset({"action"}), risk="high", max_attempts=2))
    return registry


def demo_plan(incident_id: str = "INC-1001") -> AgentPlan:
    return AgentPlan(
        "Investigate and safely remediate a model gateway incident",
        (
            AgentStep("lookup", "lookup_incident", {"incident_id": incident_id}, "incident"),
            AgentStep("draft", "draft_remediation", {"service": "$state.incident.service"}, "remediation", ("lookup",)),
            AgentStep("apply", "apply_remediation", {"action": "$state.remediation.action"}, "execution", ("draft",), True),
        ),
        {"planner": "deterministic-demo", "version": 1},
    )

