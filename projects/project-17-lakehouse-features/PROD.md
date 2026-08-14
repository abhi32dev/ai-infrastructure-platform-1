# Production reasoning — Lakehouse and feature platform

## Why this project exists

Schema contracts, event-time commits and point-in-time joins prevent leakage and skew. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- missing IDs
- NaN/Inf values
- unsupported schema DLQ
- duplicate ingest
- future watermark exclusion
- idempotent compaction
- point-in-time leakage
- online materialization and quality

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

In-memory semantics keep tests fast; DuckDB/PyArrow provide a path to actual columnar persistence.

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

**Staff/Principal answer.** Future-data leakage in a point-in-time join is the most expensive correctness violation because it invalidates offline evaluation without obvious runtime failure. Event-time order, commit integrity, and observation-time boundaries are non-negotiable.

**Implementation evidence.** [`ailab/lakehouse_features.py · LakehouseFeaturePlatform.point_in_time`](../../ailab/lakehouse_features.py) is the concrete control point used by this project:

```python
def point_in_time(self,entity_id:str,as_of:float)->float|None:
  values=[e for e in self.silver if e.entity_id==entity_id and e.event_time<=as_of];return max(values,key=lambda e:e.event_time).value if values else None
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `LakehouseFeaturePlatform.point_in_time` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** Ingest linearizes at deduplicated bronze append by event ID; a compacted version linearizes when its checksummed commit becomes visible. Materialization consumes only committed versions.

**Implementation evidence.** [`ailab/lakehouse_features.py · LakehouseFeaturePlatform.compact`](../../ailab/lakehouse_features.py) is the concrete control point used by this project:

```python
def compact(self,watermark:float|None=None)->dict:
  watermark=time.time() if watermark is None else watermark
  eligible=sorted((e for e in self.bronze.values() if e.event_time<=watermark),key=lambda e:(e.event_time,e.event_id));known={e.event_id for e in self.silver};new=[e for e in eligible if e.event_id not in known];self.silver.extend(new)
  digest=hashlib.sha256("|".join(e.event_id for e in self.silver).encode()).hexdigest();self.commits.append({"version":len(self.commits)+1,"rows":len(self.silver),"checksum":digest});return self.commits[-1]
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `LakehouseFeaturePlatform.compact` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** Immutable bronze events and verified version commits are authoritative; online features are derived. Reconciliation rebuilds one bounded version/watermark range and compares checksums rather than patching unexplained online values.

**Implementation evidence.** [`ailab/lakehouse_features.py · LakehouseFeaturePlatform.compact`](../../ailab/lakehouse_features.py) is the concrete control point used by this project:

```python
def compact(self,watermark:float|None=None)->dict:
  watermark=time.time() if watermark is None else watermark
  eligible=sorted((e for e in self.bronze.values() if e.event_time<=watermark),key=lambda e:(e.event_time,e.event_id));known={e.event_id for e in self.silver};new=[e for e in eligible if e.event_id not in known];self.silver.extend(new)
  digest=hashlib.sha256("|".join(e.event_id for e in self.silver).encode()).hexdigest();self.commits.append({"version":len(self.commits)+1,"rows":len(self.silver),"checksum":digest});return self.commits[-1]
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `LakehouseFeaturePlatform.compact` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade by serving the prior verified version or explicit missing feature with freshness metadata. Schema contract, checksum, dedup identity, watermark policy, and point-in-time no-future rule fail closed.

**Implementation evidence.** [`ailab/lakehouse_features.py · LakehouseFeaturePlatform.materialize_online`](../../ailab/lakehouse_features.py) is the concrete control point used by this project:

```python
def materialize_online(self,as_of:float):
  latest={}
  for event in self.silver:
   if event.event_time<=as_of and (event.entity_id not in latest or event.event_time>=latest[event.entity_id].event_time):latest[event.entity_id]=event
  self.online={key:value.value for key,value in latest.items()};return dict(self.online)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `LakehouseFeaturePlatform.materialize_online` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track contract/DLQ failures, duplicate rate, event/processing-time lag, late rows, compaction input/output/checksum, version age, materialization lag, PIT misses, feature nulls, and online/offline skew.

**Implementation evidence.** [`ailab/lakehouse_features.py · LakehouseFeaturePlatform.quality`](../../ailab/lakehouse_features.py) is the concrete control point used by this project:

```python
def quality(self)->dict:
  ids=[e.event_id for e in self.silver];return {"rows":len(ids),"unique":len(ids)==len(set(ids)),"dlq":len(self.dlq),"commits":len(self.commits)}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `LakehouseFeaturePlatform.quality` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Partition by event date/entity hash, use columnar object storage, metadata catalogs, incremental compaction, and distributed materialization. Multi-region requires commit ownership; adversarial producers need schema, rate, and hot-key controls.

**Implementation evidence.** [`ailab/lakehouse_features.py · LakehouseFeaturePlatform.ingest`](../../ailab/lakehouse_features.py) is the concrete control point used by this project:

```python
def ingest(self,event:FeatureEvent)->str:
  try:event.validate()
  except DataContractError as exc:self.dlq.append({"event":event,"error":str(exc)});return "dead_lettered"
  if event.event_id in self.bronze:return "duplicate"
  self.bronze[event.event_id]=event;return "ingested"
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `LakehouseFeaturePlatform.ingest` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns contracts, lake formats, commits, lineage, PIT join primitives, materialization, freshness, and quality telemetry. Application teams own feature meaning, event producers, default/null semantics, acceptable lateness, and validation thresholds.

**Implementation evidence.** [`ailab/lakehouse_features.py · FeatureEvent.validate`](../../ailab/lakehouse_features.py) is the concrete control point used by this project:

```python
def validate(self):
  if not self.event_id or not self.entity_id:raise DataContractError("event and entity identifiers are required")
  if not math.isfinite(self.event_time) or not math.isfinite(self.value):raise DataContractError("time and value must be finite")
  if self.schema_version!=1:raise DataContractError("unsupported schema version")
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `FeatureEvent.validate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
