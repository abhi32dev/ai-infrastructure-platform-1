# Production reasoning — Streaming feature platform

## Why this project exists

Offsets, schemas and event time must yield reproducible online and offline features. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- invalid partition/lateness configuration
- null and non-finite events
- schema-version DLQ
- duplicate publication
- independent consumer groups
- late events and watermarks
- point-in-time correctness
- online/offline skew

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

SQLite models Kafka/Kinesis semantics; production swaps in a durable broker and distributed feature store.

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

**Staff/Principal answer.** Point-in-time leakage is the costliest correctness failure because it silently inflates offline performance and can promote a bad model. Event time, offsets, deduplication, and historical snapshots must remain reproducible.

**Implementation evidence.** [`ailab/streaming_features.py · StreamingFeaturePlatform.point_in_time`](../../ailab/streaming_features.py) is the concrete control point used by this project:

```python
def point_in_time(self,user:str,as_of:float)->dict|None:
  row=self.db.execute("SELECT * FROM offline_features WHERE user_id=? AND as_of<=? ORDER BY as_of DESC LIMIT 1",(user,as_of)).fetchone();return dict(row) if row else None
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `StreamingFeaturePlatform.point_in_time` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** Consumption linearizes when the online feature update and consumer-group offset commit in the same transaction. Publishing linearizes at durable append with a unique event identity; retries must observe that identity rather than create another logical event.

**Implementation evidence.** [`ailab/streaming_features.py · StreamingFeaturePlatform.consume`](../../ailab/streaming_features.py) is the concrete control point used by this project:

```python
def consume(self,group:str,limit:int=100,now:float|None=None)->dict:
  if not group:raise ValueError("consumer group is required")
  if limit<1:raise ValueError("limit must be positive")
  now=now or time.time();processed=duplicates=late=0
  for partition in range(self.partitions):
   row=self.db.execute("SELECT offset_id FROM offsets WHERE group_id=? AND partition_id=?",(group,partition)).fetchone();last=row[0] if row else -1
   rows=self.db.execute("SELECT * FROM events WHERE partition_id=? AND offset_id>? ORDER BY offset_id LIMIT ?",(partition,last,limit)).fetchall()
   for row in rows:
    event=Event(**json.loads(row["payload"]));is_late=event.event_time<now-self.allowed_lateness;late+=int(is_late)
    if not is_late:self._update_online(event);processed+=1
    self.db.execute("INSERT OR REPLACE INTO offsets VALUES(?,?,?)",(group,partition,row["offset_id"]))
  self.db.commit();return {"processed":processed,"duplicates":duplicates,"late":late,"lag":self.lag(group)}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `StreamingFeaturePlatform.consume` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The immutable event log plus committed group offsets is authoritative; online features and offline snapshots are materialized views. Reconciliation replays a bounded partition/offset range and compares versioned feature logic.

**Implementation evidence.** [`ailab/streaming_features.py · StreamingFeaturePlatform.consume`](../../ailab/streaming_features.py) is the concrete control point used by this project:

```python
def consume(self,group:str,limit:int=100,now:float|None=None)->dict:
  if not group:raise ValueError("consumer group is required")
  if limit<1:raise ValueError("limit must be positive")
  now=now or time.time();processed=duplicates=late=0
  for partition in range(self.partitions):
   row=self.db.execute("SELECT offset_id FROM offsets WHERE group_id=? AND partition_id=?",(group,partition)).fetchone();last=row[0] if row else -1
   rows=self.db.execute("SELECT * FROM events WHERE partition_id=? AND offset_id>? ORDER BY offset_id LIMIT ?",(partition,last,limit)).fetchall()
   for row in rows:
    event=Event(**json.loads(row["payload"]));is_late=event.event_time<now-self.allowed_lateness;late+=int(is_late)
    if not is_late:self._update_online(event);processed+=1
    self.db.execute("INSERT OR REPLACE INTO offsets VALUES(?,?,?)",(group,partition,row["offset_id"]))
  self.db.commit();return {"processed":processed,"duplicates":duplicates,"late":late,"lag":self.lag(group)}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `StreamingFeaturePlatform.consume` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade by serving the last known feature with explicit freshness or falling back to model defaults. Schema validation, tenant partitioning, offset monotonicity, and point-in-time boundaries fail closed; future data is never substituted.

**Implementation evidence.** [`ailab/streaming_features.py · StreamingFeaturePlatform.feature`](../../ailab/streaming_features.py) is the concrete control point used by this project:

```python
def feature(self,user:str)->dict|None:
  row=self.db.execute("SELECT * FROM online_features WHERE user_id=?",(user,)).fetchone();return dict(row) if row else None
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `StreamingFeaturePlatform.feature` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track consumer lag, event-time lateness, DLQ rate by schema reason, duplicate rate, feature freshness, replay volume, online/offline skew, and point-in-time miss rate. Skew and freshness are direct correctness signals.

**Implementation evidence.** [`ailab/streaming_features.py · StreamingFeaturePlatform.skew`](../../ailab/streaming_features.py) is the concrete control point used by this project:

```python
def skew(self,user:str,as_of:float)->dict:
  online=self.feature(user);offline=self.point_in_time(user,as_of)
  if not online or not offline:return {"skew":True,"reason":"missing feature"}
  fields=("event_count","total_value");diff={f:online[f]-offline[f] for f in fields};return {"skew":any(abs(v)>1e-9 for v in diff.values()),"difference":diff}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `StreamingFeaturePlatform.skew` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Partition by stable entity key, autoscale consumers from lag, compact historical storage, and version feature transformations. Multi-region writes need ownership/conflict policy; adversarial keys require hot-partition detection and producer quotas.

**Implementation evidence.** [`ailab/streaming_features.py · StreamingFeaturePlatform.publish`](../../ailab/streaming_features.py) is the concrete control point used by this project:

```python
def publish(self,event:Event)->dict:
  if not isinstance(event,Event):raise ValueError("event must be an Event")
  if event.schema_version not in (1,2):return self._dlq(event,"unsupported schema version")
  if not event.id or not event.user_id:return self._dlq(event,"missing event or user id")
  if not event.event_type or not math.isfinite(event.value) or not math.isfinite(event.event_time):return self._dlq(event,"invalid event fields")
  partition=int(hashlib.sha256(event.user_id.encode()).hexdigest()[:8],16)%self.partitions
  offset=self.db.execute("SELECT COALESCE(MAX(offset_id),-1)+1 FROM events WHERE partition_id=?",(partition,)).fetchone()[0]
  try:self.db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)",(partition,offset,event.id,json.dumps(event.__dict__),event.event_time,time.time()));self.db.commit();return {"status":"published","partition":partition,"offset":offset}
  except sqlite3.IntegrityError:return {"status":"duplicate","event_id":event.id}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `StreamingFeaturePlatform.publish` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns schemas, broker contracts, offsets, replay, DLQ, materialization, lineage, and freshness telemetry. Application teams own feature definitions, acceptable staleness, default values, leakage reviews, and model-specific skew tolerances.

**Implementation evidence.** [`ailab/streaming_features.py · StreamingFeaturePlatform.snapshot_offline`](../../ailab/streaming_features.py) is the concrete control point used by this project:

```python
def snapshot_offline(self,as_of:float)->int:
  rows=self.db.execute("SELECT payload FROM events WHERE event_time<=?",(as_of,)).fetchall();aggregates={}
  for row in rows:
   event=Event(**json.loads(row[0]));count,total=aggregates.get(event.user_id,(0,0.0));aggregates[event.user_id]=(count+1,total+event.value)
  for user,(count,total) in aggregates.items():self.db.execute("INSERT OR REPLACE INTO offline_features VALUES(?,?,?,?)",(user,as_of,count,total))
  self.db.commit();return len(aggregates)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `StreamingFeaturePlatform.snapshot_offline` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
