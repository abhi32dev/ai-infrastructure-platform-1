# Production reasoning — Durable agent runtime

## Why this project exists

A side effect may execute only after policy and approval, and resume must never repeat it. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

## Production invariants

- Inputs are typed, validated before side effects, and reject null, empty, malformed, non-finite, unsafe or unsupported values.
- Every mutation is attributable and either idempotent or protected by a unique operation identity.
- Work is bounded by capacity, deadline, retry, quota and cost policies; overload is an explicit state rather than silent degradation.
- Durable evidence separates desired state, actual state, decisions, attempts, outputs and failures.
- Recovery is tested from persisted state. A successful retry cannot duplicate an already committed effect.
- Tenant, identity and policy boundaries are enforced before retrieval, execution or publication.
- Observability records user-impact signals without secrets, raw credentials or chain-of-thought.

## Test strategy and why it matters

The project test suite uses a layered production matrix:

1. **Unit tests** isolate deterministic business rules so failures identify one invariant.
2. **Null and type tests** prevent ambiguous downstream exceptions and injection through unexpected shapes.
3. **Boundary tests** exercise zero, one, maximum, over-maximum, negative, NaN and infinity where applicable.
4. **Negative-policy tests** prove the system fails closed for authorization, budgets, schemas and unsafe configuration.
5. **Idempotency tests** repeat requests, events and resume operations to prevent duplicate cost or effects.
6. **Failure-injection tests** simulate providers, workers, storage, timeouts, corruption and partial completion.
7. **Recovery tests** verify checkpoint, replay, reconciliation, fallback, circuit, failover or rollback behavior.
8. **Concurrency/capacity tests** validate bounded queues, resource placement, quotas and load shedding.
9. **Security tests** cover malformed identity, tenant escape, prompt injection, PII/secrets and audit tampering.
10. **Contract tests** validate protocol, API, artifact and environment compatibility at replaceable boundaries.

Project-specific scenarios:

- empty/invalid plans
- missing or forward dependencies
- tool schema mismatch
- allowlist denial
- approval, denial and stale resume
- timeout and retry exhaustion
- checkpoint crash recovery
- dead-letter evidence and idempotent replay

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

SQLite transactions model durable orchestration; production uses a workflow engine and transactional outbox.

The trade-off is intentional: a local implementation cannot prove internet-scale throughput, multi-region durability or accelerator performance. It can prove state transitions, schemas, policy, retry safety, observability contracts and failure handling—the logic that must remain correct when scale changes.

## Operational review checklist

- Define SLI/SLO, error-budget owner, alert thresholds and rollback authority.
- Estimate peak throughput, concurrency, memory/storage growth, token/GPU usage and unit cost.
- Document dependency limits, timeouts, retry budgets, circuit behavior and degradation order.
- Define backup, restore, replay, reconciliation, regional failure and disaster-recovery exercises.
- Threat-model identity, tenant boundaries, secrets, supply chain, data retention and audit access.
- Version schemas, prompts, datasets, models, policies, APIs and infrastructure; test compatibility.
- Establish deployment gates, canary signals, automated rollback and manual override procedures.

## Staff/Principal discussion prompts

### 1. Which invariant is financially or operationally most expensive to violate?

**Staff/Principal answer.** Duplicate high-risk side effects are the largest operational risk because replay can apply remediation twice. The runtime must persist approval, idempotency identity, attempt state, and completion before allowing dependent work to advance.

**Implementation evidence.** [`ailab/agent_runtime.py · DurableAgentRuntime._execute`](../../ailab/agent_runtime.py) is the concrete control point used by this project:

```python
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
# … 4 additional source lines in the linked implementation
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DurableAgentRuntime._execute` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** The linearization point is the transaction that changes a step to completed and records its result/effect identity. A resumed run reads that committed state and skips execution; an in-flight attempt without completion remains retryable under the tool's idempotency contract.

**Implementation evidence.** [`ailab/agent_runtime.py · DurableAgentRuntime._set_step`](../../ailab/agent_runtime.py) is the concrete control point used by this project:

```python
def _set_step(self, run_id: str, step: AgentStep, status: str, attempts: int, output: dict[str, Any] | None, error: str | None) -> None:
        self.connection.execute(
            """INSERT INTO agent_steps VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, step_id) DO UPDATE SET status=excluded.status,
            attempts=excluded.attempts, output=excluded.output, error=excluded.error, updated_at=excluded.updated_at""",
            (run_id, step.id, step.tool, status, attempts, json.dumps(output, sort_keys=True) if output is not None else None, error, time.time()),
        )
        self.connection.commit()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DurableAgentRuntime._set_step` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The durable run/step tables and event history are authoritative, not worker memory. Resume reconstructs the plan from storage and reconciliation is bounded by the finite step DAG and retry budget; completed steps are never inferred from downstream observations alone.

**Implementation evidence.** [`ailab/agent_runtime.py · DurableAgentRuntime.resume`](../../ailab/agent_runtime.py) is the concrete control point used by this project:

```python
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
# … 2 additional source lines in the linked implementation
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DurableAgentRuntime.resume` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Read-only tools can retry or pause while preserving the durable run. Policy denial, explicit human denial, invalid arguments, and unapproved high-risk actions fail closed; no availability objective overrides authorization.

**Implementation evidence.** [`ailab/agent_runtime.py · DurableAgentRuntime._assert_policy`](../../ailab/agent_runtime.py) is the concrete control point used by this project:

```python
def _assert_policy(self, tool: ToolSpec) -> None:
        if tool.name not in self.allowed_tools:
            raise PolicyDenied(f"tool is outside this runtime's allowlist: {tool.name}")
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DurableAgentRuntime._assert_policy` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Measure step success by tool/version, retries, timeouts, approval wait, DLQ depth, resume count, duplicate-effect prevention, and end-to-end run latency. Rising replay or retry rates expose correctness risk before users see a failed final run.

**Implementation evidence.** [`ailab/agent_runtime.py · DurableAgentRuntime._event`](../../ailab/agent_runtime.py) is the concrete control point used by this project:

```python
def _event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.connection.execute("INSERT INTO events(run_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)", (run_id, event_type, json.dumps(payload, sort_keys=True), time.time()))
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DurableAgentRuntime._event` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Separate schedulers from workers, partition runs by stable ID, use leases and a transactional outbox, and place large results in object storage. Multi-region execution needs single-writer ownership per run; adversarial tenants require tool, concurrency, and spend quotas.

**Implementation evidence.** [`ailab/agent_runtime.py · DurableAgentRuntime._execute`](../../ailab/agent_runtime.py) is the concrete control point used by this project:

```python
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
# … 4 additional source lines in the linked implementation
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DurableAgentRuntime._execute` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns durable transitions, leases, retries, idempotency, approval primitives, audit, and tool-schema enforcement. Application teams own plan semantics, tool implementations, risk classification, compensating actions, and domain-specific approval policy.

**Implementation evidence.** [`ailab/agent_runtime.py · DurableAgentRuntime._validate_plan`](../../ailab/agent_runtime.py) is the concrete control point used by this project:

```python
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
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DurableAgentRuntime._validate_plan` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
