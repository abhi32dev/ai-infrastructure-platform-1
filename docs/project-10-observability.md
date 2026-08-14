# Project 10 - AI Observability, SLO, Incident, and Cost Lab

Implements structured correlated spans/logs, request metrics, RED and AI signals (tokens, model, cache, tenant, cost), p95 latency, availability, SLO/error-budget consumption, multi-window burn-rate alerts, cooldown suppression, trace incident timelines, cost attribution, and utilization-based right-sizing recommendations.

Exercises: create success/failure traffic; calculate error budget by hand; simulate fast and slow burns; verify alert cooldown; trace a request across named spans; compare tenant/model cost; vary provisioned throughput. Discuss cardinality control, sampling, exemplars, tail-based sampling, semantic conventions, telemetry PII, SLO ownership, burn-rate thresholds, unit economics, cost-per-successful-task, chargeback/showback, and why averages hide tails.

This is the shared telemetry contract for later MCP/A2A calls and guardrail decisions: protocol method, agent/tool identity, policy decision, token/cost counts, task state, and trace identifiers will be captured without recording secrets or chain-of-thought.

## Complete answered Staff/Principal Q&A

The detailed answers, trade-offs, and exact implementation evidence are in [`projects/project-10-observability/PROD.md`](../projects/project-10-observability/PROD.md).
