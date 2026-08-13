# Staff-level cross-cutting controls

This lab treats guardrails, evaluation, observability, and cost as platform controls, not features added after deployment. The machine-readable source of truth is `config/project-controls.json`; every project names concrete controls in all five categories.

## Decision flow

1. Authenticate and authorize the tenant, agent, tool, or model request.
2. Validate schemas and inspect inputs before expensive work starts.
3. Enforce quotas, deadlines, budgets, idempotency, and cancellation.
4. Execute through bounded queues with fallback and circuit breaking.
5. Inspect outputs, record traces/metrics/audit events, and attribute cost.
6. Evaluate offline and online results; promote only through explicit gates.
7. Roll back on SLO burn, quality regression, security failure, or drift.

## How to study it

Start with one project's README and verifier. Trace a happy path, then change one input to trigger each control. Inspect its SQLite state or JSON artifact after every run. For staff interviews, explain the invariant, ownership boundary, failure mode, measurable signal, and rollback—not merely the library call.

Native integrations are isolated where they belong: FastAPI in Project 3, MLflow in Project 4, and OpenTelemetry/Prometheus in Project 10. Project 9 emits Docker Compose and Kubernetes deployment, service, probe, resource, security, and network-policy resources. Grafana consumes the Prometheus endpoint; its dashboard/query layer is external to the instrumentation library.

PyTorch and TensorFlow are intentionally not installed: Project 12 demonstrates lifecycle invariants with NumPy so the lab stays inexpensive. A framework adapter is a mechanical extension and is not claimed as verified. Ollama is installed locally and the HTTP contract is implemented; a live-model run requires pulling model weights explicitly.
