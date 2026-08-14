# Production reasoning — Self-healing batch platform

## Why this project exists

Item-level durable state and reconciliation prevent silent loss and duplicate work. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- empty manifests
- adaptive batch boundaries
- transient/permanent worker failure
- partial checkpoints
- resume
- TTL dedup expiry
- missing/corrupt output
- three-pass reconciliation

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

Local workers demonstrate recovery; production maps the same manifest to distributed compute and object storage.

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

**Staff/Principal answer.** Silent item loss is more expensive than a visibly failed job because downstream consumers may treat incomplete output as complete. Every expected item needs durable status, integrity evidence, and bounded reconciliation.

**Implementation evidence.** [`ailab/batch_platform.py · SelfHealingBatchPlatform.reconcile`](../../ailab/batch_platform.py) is the concrete control point used by this project:

```python
def reconcile(self,run_id:str,items:list[WorkItem],worker:Callable[[WorkItem],str],max_attempts:int=3)->dict:
  expected={x.id:x for x in items};history=[]
  for pass_number in range(1,4):
   actual={row[0] for row in self.db.execute("SELECT item_id FROM outputs")};missing=sorted(set(expected)-actual);history.append({"pass":pass_number,"missing":missing});self.db.execute("INSERT OR REPLACE INTO reconciliation VALUES(?,?,?,?)",(run_id,pass_number,json.dumps(missing),time.time()));self.db.commit()
   if not missing:break
   for item_id in missing:
    self.db.execute("DELETE FROM checkpoints WHERE run_id=? AND item_id=?",(run_id,item_id));self.db.commit()
    try:self._process(run_id,expected[item_id],worker,max_attempts)
    except Exception:pass
  actual={row[0] for row in self.db.execute("SELECT item_id FROM outputs")};return {"missing":sorted(set(expected)-actual),"reconciliation":history}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `SelfHealingBatchPlatform.reconcile` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** An item linearizes at the atomic completion checkpoint containing output identity and checksum. Worker return alone is not completion; a crash before checkpoint leaves the item retryable and the output subject to reconciliation.

**Implementation evidence.** [`ailab/batch_platform.py · SelfHealingBatchPlatform._complete`](../../ailab/batch_platform.py) is the concrete control point used by this project:

```python
def _complete(self,run,item):return bool(self.db.execute("SELECT 1 FROM checkpoints WHERE run_id=? AND item_id=? AND status='completed'",(run,item)).fetchone())
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `SelfHealingBatchPlatform._complete` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The manifest and item checkpoints are authoritative for intent and logical completion; object/filesystem output is observed actual state. Reconciliation is bounded to expected manifest items and a fixed number of repair passes.

**Implementation evidence.** [`ailab/batch_platform.py · SelfHealingBatchPlatform.reconcile`](../../ailab/batch_platform.py) is the concrete control point used by this project:

```python
def reconcile(self,run_id:str,items:list[WorkItem],worker:Callable[[WorkItem],str],max_attempts:int=3)->dict:
  expected={x.id:x for x in items};history=[]
  for pass_number in range(1,4):
   actual={row[0] for row in self.db.execute("SELECT item_id FROM outputs")};missing=sorted(set(expected)-actual);history.append({"pass":pass_number,"missing":missing});self.db.execute("INSERT OR REPLACE INTO reconciliation VALUES(?,?,?,?)",(run_id,pass_number,json.dumps(missing),time.time()));self.db.commit()
   if not missing:break
   for item_id in missing:
    self.db.execute("DELETE FROM checkpoints WHERE run_id=? AND item_id=?",(run_id,item_id));self.db.commit()
    try:self._process(run_id,expected[item_id],worker,max_attempts)
    except Exception:pass
  actual={row[0] for row in self.db.execute("SELECT item_id FROM outputs")};return {"missing":sorted(set(expected)-actual),"reconciliation":history}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `SelfHealingBatchPlatform.reconcile` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade by reducing batch size, retrying transient items, and allowing partial resumable progress. Checksums, permanent-error classification, retry limits, and completeness fail closed; corrupt output is never marked successful.

**Implementation evidence.** [`ailab/batch_platform.py · SelfHealingBatchPlatform._process`](../../ailab/batch_platform.py) is the concrete control point used by this project:

```python
def _process(self,run_id:str,item:WorkItem,worker:Callable[[WorkItem],str],max_attempts:int):
  with self.lock:
   if self._complete(run_id,item.id):return
   now=time.time();dedup=self.db.execute("SELECT expires_at FROM dedup WHERE item_id=?",(item.id,)).fetchone()
   if dedup and dedup[0]>now and self.db.execute("SELECT 1 FROM outputs WHERE item_id=?",(item.id,)).fetchone():self._checkpoint(run_id,item.id,"completed","dedup-reused",0,None);return
   prior=self.db.execute("SELECT attempts FROM checkpoints WHERE run_id=? AND item_id=?",(run_id,item.id)).fetchone();attempts=prior[0] if prior else 0
  last=""
  while attempts<max_attempts:
   attempts+=1
   try:
    output=worker(item);checksum=hashlib.sha256(output.encode()).hexdigest()
    with self.lock:self.db.execute("INSERT OR REPLACE INTO outputs VALUES(?,?,?,?)",(item.id,output,checksum,time.time()));self.db.execute("INSERT OR REPLACE INTO dedup VALUES(?,?)",(item.id,time.time()+self.ttl));self._checkpoint(run_id,item.id,"completed",output,attempts,None)
    return
   except Exception as exc:
    last=f"{type(exc).__name__}: {exc}"
    with self.lock:self._checkpoint(run_id,item.id,"failed",None,attempts,last)
  raise BatchFailure(f"item {item.id} exhausted retries: {last}")
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `SelfHealingBatchPlatform._process` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track expected/completed/failed/reconciled items, retries by cause, checkpoint age, throughput, worker utilization, duplicate skips, checksum failures, missing outputs, and time-to-recovery after interruption.

**Implementation evidence.** [`ailab/batch_platform.py · SelfHealingBatchPlatform.inspect`](../../ailab/batch_platform.py) is the concrete control point used by this project:

```python
def inspect(self,run):return {"run":dict(self.db.execute("SELECT * FROM runs WHERE id=?",(run,)).fetchone()),"checkpoints":[dict(x) for x in self.db.execute("SELECT * FROM checkpoints WHERE run_id=?",(run,))],"reconciliation":[dict(x) for x in self.db.execute("SELECT * FROM reconciliation WHERE run_id=?",(run,))]}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `SelfHealingBatchPlatform.inspect` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Move manifests to a transactional store, outputs to versioned object storage, and workers to elastic queues with leases. Partition manifests, bound reconciliation I/O, and isolate adversarial tenants with compute/storage quotas.

**Implementation evidence.** [`ailab/batch_platform.py · SelfHealingBatchPlatform.execute`](../../ailab/batch_platform.py) is the concrete control point used by this project:

```python
def execute(self,items:list[WorkItem],worker:Callable[[WorkItem],str],run_id:str|None=None,max_attempts:int=3)->dict:
  run_id=run_id or uuid.uuid4().hex;existing=self.db.execute("SELECT manifest FROM runs WHERE id=?",(run_id,)).fetchone()
  if not existing:self.db.execute("INSERT INTO runs VALUES(?,?,?,?,?)",(run_id,"running",json.dumps([x.__dict__ for x in items]),time.time(),time.time()));self.db.commit()
  else:items=[WorkItem(**x) for x in json.loads(existing[0])]
  pending=[x for x in items if not self._complete(run_id,x.id)]
  batches=self.plan(pending);failures=[]
  with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
   futures={pool.submit(self._process,run_id,item,worker,max_attempts):item for batch in batches for item in batch.items}
   for future in as_completed(futures):
    try:future.result()
    except Exception as exc:failures.append({"item":futures[future].id,"error":str(exc)})
  reconciliation=self.reconcile(run_id,items,worker,max_attempts);status="completed" if not reconciliation["missing"] else "failed";self.db.execute("UPDATE runs SET status=?,updated_at=? WHERE id=?",(status,time.time(),run_id));self.db.commit();return {"run_id":run_id,"status":status,"batches":len(batches),"failures":failures,**reconciliation}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `SelfHealingBatchPlatform.execute` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns job state, leases, retries, checkpoint schema, idempotency, reconciliation, quotas, and telemetry. Application teams own item transformation, error classification hints, data-specific validation, output semantics, and acceptable partial-results policy.

**Implementation evidence.** [`ailab/batch_platform.py · SelfHealingBatchPlatform.plan`](../../ailab/batch_platform.py) is the concrete control point used by this project:

```python
def plan(self,items:list[WorkItem])->list[Batch]:
  ordered=sorted(items,key=lambda x:(-x.size_bytes,x.id));bins=[]
  for item in ordered:
   target=next((b for b in bins if len(b)<self.max_items and sum(x.size_bytes for x in b)+item.size_bytes<=self.target),None)
   if target is None:target=[];bins.append(target)
   target.append(item)
  return [Batch(hashlib.sha256("|".join(x.id for x in b).encode()).hexdigest()[:12],tuple(b),sum(x.size_bytes for x in b)) for b in bins]
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `SelfHealingBatchPlatform.plan` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
