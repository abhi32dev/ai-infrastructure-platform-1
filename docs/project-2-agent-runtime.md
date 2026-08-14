# Project 2 - Durable Agent Runtime and Orchestrator

## Learning objective

An agent is not production-ready merely because a model can choose a function. The runtime must make every decision and side effect recoverable, authorized, bounded, and inspectable.

This project implements a deterministic incident-remediation plan so runtime behavior can be tested separately from model-planning quality. A later increment can plug an LLM planner into the same typed `AgentPlan` boundary.

## Implemented runtime contract

- Typed tool registry and required-argument validation
- Per-runtime tool allowlist
- Explicit dependency graph validation
- Durable run, step, approval, side-effect, event, and dead-letter records
- State references between steps (`$state.incident.service`)
- High-risk tool approval gate
- Human approval and denial
- Per-tool timeout
- Bounded retry
- Dead-letter isolation after retry exhaustion
- Idempotency-keyed tool effects
- Checkpointed resume without repeating completed tools
- Complete event journal for inspection

## Happy-path state transitions

```text
RUNNING
  -> lookup_incident: COMPLETED
  -> draft_remediation: COMPLETED
  -> apply_remediation: WAITING_APPROVAL
  -> human APPROVED
  -> apply_remediation: COMPLETED
  -> RUN COMPLETED
```

Denial produces a terminal `DENIED` run. Exhausted retries produce a `FAILED` run and a dead-letter record containing the tool, arguments, final error, and attempt count.

## Why the side-effect table matters

A step checkpoint alone cannot guarantee safe replay. A process may complete an external action and crash immediately before saving the step status. The runtime therefore derives an idempotency key from the run, step, tool, and arguments and stores the completed effect separately. On resume, it can reuse the recorded effect.

For a real remote service, the same key must also cross the network and be honored by that service. A local SQLite record cannot prevent duplication if the remote system ignores idempotency.

## Hands-on exercises

1. Start a run and inspect the event journal before approving it.
2. Deny the action and confirm the tool side-effect does not occur.
3. Remove `apply_remediation` from the allowlist and observe `PolicyDenied`.
4. Set a 1 ms tool timeout and observe bounded retry plus dead-letter creation.
5. Resume an already completed run and verify no completed tool executes again.
6. Add a second high-risk tool and require an independent approval.
7. Replace the deterministic plan creator with structured LLM output while retaining plan validation.

## Staff-level interview questions

### 1. Where is the atomicity gap between an external side effect and a local checkpoint?

**Answer.** The gap is after the remote tool has committed its effect but before this runtime commits `tool_effects` and the completed step. In `_execute`, `future.result(...)` can return successfully and the process can crash before `self.connection.commit()`. On restart, local storage cannot know whether the remote mutation happened. A Staff-level design therefore sends the same idempotency key to the remote service, requires that service to deduplicate it, and records the result locally. If the remote system cannot honor idempotency, use an outbox/inbox protocol or a compensating action; do not claim exactly-once execution.

```python
# ailab/agent_runtime.py · DurableAgentRuntime._execute
key = hashlib.sha256(json.dumps({"run": run_id, "step": step.id,
    "tool": tool.name, "arguments": arguments}, sort_keys=True).encode()).hexdigest()
output = future.result(timeout=tool.timeout_seconds)       # remote effect may now exist
self.connection.execute("INSERT INTO tool_effects VALUES (?, ?, ?, ?)",
    (key, tool.name, json.dumps(output, sort_keys=True), time.time()))
self._set_step(run_id, step, "completed", attempt, output, None)
self.connection.commit()                                  # local effect becomes durable here
```

### 2. When is exactly-once execution impossible, and what practical guarantee replaces it?

**Answer.** Exactly-once is impossible when two independent systems—the runtime database and a remote tool—cannot participate in one atomic transaction. Network timeout makes “request not received” indistinguishable from “effect committed but response lost.” The practical guarantee is at-least-once delivery plus idempotent execution, stable operation identity, durable deduplication, bounded retry, and reconciliation. For non-idempotent operations, use a saga with explicit compensation and surface ambiguous outcomes for human review.

```python
# ailab/agent_runtime.py · DurableAgentRuntime._execute
cached = self.connection.execute(
    "SELECT output FROM tool_effects WHERE idempotency_key=?", (key,)
).fetchone()
if cached:
    output = json.loads(cached["output"])
    self._set_step(run_id, step, "completed", 0, output, None)
    self._event(run_id, "tool_effect_reused", {"step_id": step.id, "idempotency_key": key})
    return output
```

### 3. How should tool permissions differ by tenant, agent, environment, and data classification?

**Answer.** Effective permission is the intersection—not union—of tenant entitlement, agent identity, environment policy, data classification, tool risk, and human approval. Production should deny by default, bind the principal and tenant outside the prompt, issue short-lived scoped credentials, and evaluate ABAC attributes at invocation time. Development may allow mock/read tools; production mutation tools need narrower resource scopes and independent approval. The current lab demonstrates the first boundary with an immutable runtime allowlist and a separate high-risk approval gate.

```python
# ailab/agent_runtime.py · DurableAgentRuntime._assert_policy
def _assert_policy(self, tool: ToolSpec) -> None:
    if tool.name not in self.allowed_tools:
        raise PolicyDenied(f"tool is outside this runtime's allowlist: {tool.name}")

# DurableAgentRuntime.resume
if step.requires_approval or tool.risk == "high":
    decision = self.connection.execute(
        "SELECT decision FROM approvals WHERE run_id=? AND step_id=?", (run_id, step.id)
    ).fetchone()
```

### 4. Why must timeouts use an end-to-end deadline rather than reset at every retry?

**Answer.** Resetting a full timeout for every attempt multiplies tail latency and can continue work after the caller has abandoned it. One deadline must cover queueing, approval, retries, remote execution, and response delivery. Each attempt receives only the remaining budget; if no budget remains, the step terminates without another call. This lab currently demonstrates a per-attempt tool timeout, so a production extension must add `deadline_at` to run/step state and calculate `remaining = deadline_at - now` before every wait.

```python
# Current bounded per-attempt control in DurableAgentRuntime._execute
future = executor.submit(tool.handler, dict(arguments))
try:
    output = future.result(timeout=tool.timeout_seconds)
except FutureTimeout as exc:
    future.cancel()
    raise ToolTimeout(f"tool {tool.name} exceeded {tool.timeout_seconds}s") from exc

# Production call-site rule:
# remaining = min(tool.timeout_seconds, run.deadline_at - time.time())
# if remaining <= 0: raise EndToEndDeadlineExceeded(...)
```

### 5. What information belongs in a dead-letter record, and who owns replay?

**Answer.** Store operation identity, run/step/tool and tool version, tenant/principal references, sanitized arguments or their hash, final typed error, attempt count, first/last timestamps, policy/model/schema versions, trace ID, and checkpoint/effect status. Never store raw secrets. Replay ownership belongs to the service/team that understands the side effect, with platform-provided tooling and authorization. Replay must create an audited decision and reuse the original idempotency key; a generic platform operator should not blindly resubmit business mutations.

```python
# ailab/agent_runtime.py · retry-exhaustion path
self.connection.execute(
    "INSERT OR REPLACE INTO dead_letters VALUES (?, ?, ?, ?, ?, ?, ?)",
    (run_id, step.id, tool.name, json.dumps(arguments, sort_keys=True),
     last_error, tool.max_attempts, time.time()),
)
self._set_run(run_id, "failed", self._state(run_id))
self.connection.commit()
```

### 6. How do you prevent a compromised prompt from escalating tool privileges?

**Answer.** Treat model output as untrusted data. A prompt may propose a plan but cannot mint identity, widen scopes, register tools, change risk classification, approve itself, or supply credentials. Validate the typed DAG, resolve only registered tools, apply the runtime allowlist, validate arguments, and require an authenticated approval for high-risk actions. Tool credentials should be injected by the trusted execution boundary after authorization, not included in model context.

```python
# ailab/agent_runtime.py · DurableAgentRuntime.resume
self._assert_dependencies(run_id, step)
tool = self.registry.get(step.tool)       # only trusted registered capabilities
self._assert_policy(tool)                # prompt cannot modify allowed_tools
arguments = self._resolve(step.arguments, state)
tool.validate(arguments)                 # typed arguments before execution
output = self._execute(run_id, step, tool, arguments)
```

### 7. How would multiple workers safely lease runnable steps?

**Answer.** Add `lease_owner`, `lease_expires_at`, `fencing_token`, and version to each step. A worker atomically changes one dependency-ready step from pending/expired to leased using a conditional update; only the returned fencing token may checkpoint or emit an effect. Workers renew short leases, stop when renewal fails, and expired work becomes eligible for another worker. The idempotency key remains necessary because a paused worker may finish remotely after losing its lease. Database row locks, `SKIP LOCKED`, or a workflow engine provide the claim primitive.

```sql
UPDATE agent_steps
SET status='running', lease_owner=:worker, lease_expires_at=:expiry,
    fencing_token=fencing_token+1
WHERE run_id=:run AND step_id=:step
  AND status IN ('pending','failed')
  AND (lease_expires_at IS NULL OR lease_expires_at < :now)
RETURNING fencing_token;
```

The current single-worker dependency boundary to protect is `DurableAgentRuntime._assert_dependencies`; leasing is the production-scale substitution, not something the local lab falsely claims to implement.

### 8. What changes when a human approval remains pending for several days?

**Answer.** Approval becomes expiring authorization, not a permanent Boolean. Persist who requested and approved it, reason, policy/tool/input hashes, expiry, and notification/escalation state. Do not hold a worker or database lease while waiting. On resume, reauthenticate the approver and revalidate tenant policy, tool version, arguments, resource state, budget, and deadline; material changes invalidate the old approval. The lab persists the pause correctly, but production adds expiry and change detection.

```python
# ailab/agent_runtime.py · DurableAgentRuntime.resume
if not decision:
    self._set_step(run_id, step, "waiting_approval", 0, None, None)
    self._set_run(run_id, "waiting_approval", state)
    self._event(run_id, "approval_requested", {"step_id": step.id, "tool": step.tool})
    raise ApprovalRequired(run_id, step.id)
```

### 9. Which events must be immutable for audit and compliance?

**Answer.** Preserve run creation, plan/policy versions, identity and tenant references, tool/argument hashes, authorization and approval decisions with actor/reason, every attempt and typed error, idempotency/effect identity, checkpoint transitions, output hashes, cancellation, replay, and final state. Corrections are new events; old events are never updated. Production should export the local append-only sequence to tamper-evident/WORM storage with retention and access controls. Secrets, full sensitive payloads, and chain-of-thought do not belong in audit.

```python
# ailab/agent_runtime.py · DurableAgentRuntime._event
def _event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
    self.connection.execute(
        "INSERT INTO events(run_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
        (run_id, event_type, json.dumps(payload, sort_keys=True), time.time()),
    )
```

For the separate seven-question production architecture review, see [`projects/project-02-agent-runtime/PROD.md`](../projects/project-02-agent-runtime/PROD.md).

## Production-scale substitutions

| Local implementation | Production replacement | Additional concern |
|---|---|---|
| SQLite journal | PostgreSQL or Temporal | leases, isolation, replication |
| Local thread timeout | isolated worker/process | cancellation and resource cleanup |
| In-process registry | signed tool service catalog | versioning and service identity |
| Local approval row | workflow/UI notification | authentication, expiry, delegation |
| Sequential executor | distributed task queue | scheduling, fairness, backpressure |
