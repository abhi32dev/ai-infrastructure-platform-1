# Production reasoning — Observability and cost

## Why this project exists

Signals must connect user impact, trace context, model usage, cost and actionable SLO policy. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- no-data behavior
- success/error spans
- p95 boundaries
- error-budget exhaustion
- multi-window burn alerts
- alert cooldown
- tenant/model cost attribution
- rightsizing at zero/low/high utilization

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

SQLite provides queryable evidence; native OTel/Prometheus adapters preserve the production export contract.

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

**Staff/Principal answer.** Incorrect or missing telemetry during an incident is the most expensive invariant because operators may take damaging action with false confidence. Signal semantics, dimensions, and no-data behavior must be versioned and tested.

**Implementation evidence.** [`ailab/observability.py · Telemetry.request`](../../ailab/observability.py) is the concrete control point used by this project:

```python
def request(self,service,success,latency_ms,tokens_in=0,tokens_out=0,cost=0.0,model="",tenant="",cache_hit=False,timestamp=None):self.db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?,?)",(timestamp or time.time(),service,int(success),latency_ms,tokens_in,tokens_out,cost,model,tenant,int(cache_hit)));self.db.commit()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Telemetry.request` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** A request observation linearizes when its correlated span/log/metric event is durably accepted by the telemetry pipeline. Aggregated dashboards are eventually consistent views and cannot be the acknowledgment point.

**Implementation evidence.** [`ailab/observability.py · Telemetry.request`](../../ailab/observability.py) is the concrete control point used by this project:

```python
def request(self,service,success,latency_ms,tokens_in=0,tokens_out=0,cost=0.0,model="",tenant="",cache_hit=False,timestamp=None):self.db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?,?)",(timestamp or time.time(),service,int(success),latency_ms,tokens_in,tokens_out,cost,model,tenant,int(cache_hit)));self.db.commit()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Telemetry.request` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** Raw immutable request/span events are authoritative; metrics, alerts, cost views, and timelines are derived. Reconciliation recomputes bounded time windows and must preserve event identity to avoid double counting.

**Implementation evidence.** [`ailab/observability.py · Telemetry.service_metrics`](../../ailab/observability.py) is the concrete control point used by this project:

```python
def service_metrics(self,service,since:float=0)->dict:
  rows=self.db.execute("SELECT * FROM requests WHERE service=? AND timestamp>=?",(service,since)).fetchall()
  if not rows:return {"requests":0,"availability":None,"p95_latency_ms":None,"cost":0,"tokens":0,"cache_hit_rate":None}
  lat=sorted(r["latency_ms"] for r in rows);return {"requests":len(rows),"availability":sum(r["success"] for r in rows)/len(rows),"p95_latency_ms":lat[max(0,math.ceil(.95*len(lat))-1)],"cost":sum(r["cost"] for r in rows),"tokens":sum(r["tokens_in"]+r["tokens_out"] for r in rows),"cache_hit_rate":sum(r["cache_hit"] for r in rows)/len(rows)}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Telemetry.service_metrics` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade by sampling successful traces, reducing cardinality, or buffering exports while retaining error and audit signals. Security events, billing attribution, SLO outcome counts, and explicit no-data state must fail closed.

**Implementation evidence.** [`ailab/observability.py · Telemetry.alert`](../../ailab/observability.py) is the concrete control point used by this project:

```python
def alert(self,key:str,condition:bool,cooldown_seconds:float=300,now:float|None=None)->dict:
  now=now or time.time();row=self.db.execute("SELECT * FROM alerts WHERE key=?",(key,)).fetchone()
  if not condition:return {"sent":False,"reason":"condition_false"}
  if row and now-row["last_sent"]<cooldown_seconds:return {"sent":False,"reason":"cooldown"}
  count=(row["count"] if row else 0)+1;self.db.execute("INSERT OR REPLACE INTO alerts VALUES(?,?,?)",(key,now,count));self.db.commit();return {"sent":True,"count":count}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Telemetry.alert` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Use RED plus saturation, SLO budget/burn, trace completeness, dropped samples, model/token/quality signals, tenant/model cost, alert precision, and telemetry pipeline lag. No-data and dimension-cardinality growth are first-class alerts.

**Implementation evidence.** [`ailab/observability.py · Telemetry.multi_window_burn_alert`](../../ailab/observability.py) is the concrete control point used by this project:

```python
def multi_window_burn_alert(self,slo:SLO,short_window:float,long_window:float,short_threshold:float=14.4,long_threshold:float=6,now:float|None=None)->dict:
  short=self.burn_rate(slo,short_window,now);long=self.burn_rate(slo,long_window,now);decision=self.alert(f"{slo.service}:burn",short>=short_threshold and long>=long_threshold,now=now);return {"short_burn":short,"long_burn":long,**decision}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Telemetry.multi_window_burn_alert` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Adopt tiered sampling, streaming aggregation, cardinality budgets, regional collectors, durable buffering, and retention classes. Adversarial tenants require dimension allowlists and quotas so labels cannot exhaust the observability backend.

**Implementation evidence.** [`ailab/observability.py · Telemetry.span`](../../ailab/observability.py) is the concrete control point used by this project:

```python
def span(self,name:str,trace_id:str|None=None,parent_id:str|None=None,**attributes):
  trace_id=trace_id or uuid.uuid4().hex;span_id=uuid.uuid4().hex[:16];start=time.time();status="ok"
  try:yield {"trace_id":trace_id,"span_id":span_id}
  except Exception:status="error";raise
  finally:self.db.execute("INSERT INTO spans VALUES(?,?,?,?,?,?,?,?)",(trace_id,span_id,parent_id,name,start,time.time(),status,json.dumps(attributes)));self.db.commit()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Telemetry.span` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns telemetry schemas, collectors, SLO primitives, retention, cost attribution, and paging mechanics. Application teams own meaningful business SLIs, diagnostic attributes, runbooks, ownership, and response to alerts.

**Implementation evidence.** [`ailab/observability.py · Telemetry.error_budget`](../../ailab/observability.py) is the concrete control point used by this project:

```python
def error_budget(self,slo:SLO,now:float|None=None)->dict:
  now=now or time.time();m=self.service_metrics(slo.service,now-slo.window_seconds)
  if not m["requests"]:return {"status":"no_data"}
  allowed=1-slo.target;observed=1-m["availability"];consumed=observed/allowed if allowed else (float("inf") if observed else 0);return {"status":"ok","target":slo.target,"availability":m["availability"],"allowed_error_rate":allowed,"observed_error_rate":observed,"budget_consumed_ratio":consumed,"budget_remaining_ratio":1-consumed}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Telemetry.error_budget` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
