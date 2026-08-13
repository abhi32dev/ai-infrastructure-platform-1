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

- Where is the atomicity gap between an external side effect and a local checkpoint?
- When is exactly-once execution impossible, and what practical guarantee replaces it?
- How should tool permissions differ by tenant, agent, environment, and data classification?
- Why must timeouts use an end-to-end deadline rather than reset at every retry?
- What information belongs in a dead-letter record, and who owns replay?
- How do you prevent a compromised prompt from escalating tool privileges?
- How would multiple workers safely lease runnable steps?
- What changes when a human approval remains pending for several days?
- Which events must be immutable for audit and compliance?

## Production-scale substitutions

| Local implementation | Production replacement | Additional concern |
|---|---|---|
| SQLite journal | PostgreSQL or Temporal | leases, isolation, replication |
| Local thread timeout | isolated worker/process | cancellation and resource cleanup |
| In-process registry | signed tool service catalog | versioning and service identity |
| Local approval row | workflow/UI notification | authentication, expiry, delegation |
| Sequential executor | distributed task queue | scheduling, fairness, backpressure |

