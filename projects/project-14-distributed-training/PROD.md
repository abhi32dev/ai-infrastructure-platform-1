# Production reasoning — PyTorch distributed training

## Why this project exists

All ranks must see disjoint data, synchronized updates and restartable atomic checkpoints. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- invalid world size/epochs/rate
- non-finite hyperparameters
- empty data
- world larger than samples
- unsafe run IDs
- partition completeness
- worker failure checkpoint
- deterministic resume/checksum

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

CPU simulation verifies coordination; the isolated PyTorch dependency supports extending the same tests to DDP/FSDP.

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

**Staff/Principal answer.** Divergent rank updates or a corrupt checkpoint are most expensive because they can consume large GPU budgets while producing an invalid model. Partition completeness, synchronized reduction, finite parameters, and checkpoint integrity are hard invariants.

**Implementation evidence.** [`ailab/distributed_training.py · DistributedTrainer.train`](../../ailab/distributed_training.py) is the concrete control point used by this project:

```python
def train(self,data:list[Sample],run_id:str="run",fail_at:tuple[int,int]|None=None,resume:bool=False)->dict:
  if not run_id or "/" in run_id or ".." in run_id:raise ValueError("unsafe run_id")
  shards=self.partition(data)
  if any(not shard for shard in shards):raise ValueError("world_size cannot exceed sample count")
  checkpoint=self.root/f"{run_id}.json";state={"epoch":0,"weight":0.0,"steps":0}
  if resume:
   if not checkpoint.exists():raise TrainingError("checkpoint not found")
   state=json.loads(checkpoint.read_text())
  for epoch in range(state["epoch"],self.config.epochs):
   gradients=[]
   for rank,shard in enumerate(shards):
    if fail_at==(epoch,rank):self._save(checkpoint,{**state,"epoch":epoch});raise TrainingError(f"worker {rank} failed")
    gradients.append(sum(2*s.x*(state["weight"]*s.x-s.y) for s in shard)/len(shard))
   gradient=sum(gradients)/len(gradients)
   state["weight"]-=self.config.learning_rate*gradient/self.config.gradient_accumulation;state["steps"]+=1;state["epoch"]=epoch+1
   if state["epoch"]%self.config.checkpoint_every==0:self._save(checkpoint,state)
  checksum=hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest();return {**state,"checksum":checksum,"partitions":[len(x) for x in shards]}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DistributedTrainer.train` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** An epoch linearizes at the atomic checksummed checkpoint replace after the synchronized update. Individual rank gradients or a temporary checkpoint do not constitute committed progress.

**Implementation evidence.** [`ailab/distributed_training.py · DistributedTrainer._save`](../../ailab/distributed_training.py) is the concrete control point used by this project:

```python
def _save(self,path:Path,state:dict):
  temporary=path.with_suffix(".tmp");temporary.write_text(json.dumps(state,sort_keys=True));temporary.replace(path)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DistributedTrainer._save` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The last valid checksummed checkpoint is authoritative; worker memory and partial files are disposable. Reconciliation loads only that checkpoint, validates configuration/run identity, and replays at most the uncommitted epoch.

**Implementation evidence.** [`ailab/distributed_training.py · DistributedTrainer.train`](../../ailab/distributed_training.py) is the concrete control point used by this project:

```python
def train(self,data:list[Sample],run_id:str="run",fail_at:tuple[int,int]|None=None,resume:bool=False)->dict:
  if not run_id or "/" in run_id or ".." in run_id:raise ValueError("unsafe run_id")
  shards=self.partition(data)
  if any(not shard for shard in shards):raise ValueError("world_size cannot exceed sample count")
  checkpoint=self.root/f"{run_id}.json";state={"epoch":0,"weight":0.0,"steps":0}
  if resume:
   if not checkpoint.exists():raise TrainingError("checkpoint not found")
   state=json.loads(checkpoint.read_text())
  for epoch in range(state["epoch"],self.config.epochs):
   gradients=[]
   for rank,shard in enumerate(shards):
    if fail_at==(epoch,rank):self._save(checkpoint,{**state,"epoch":epoch});raise TrainingError(f"worker {rank} failed")
    gradients.append(sum(2*s.x*(state["weight"]*s.x-s.y) for s in shard)/len(shard))
   gradient=sum(gradients)/len(gradients)
   state["weight"]-=self.config.learning_rate*gradient/self.config.gradient_accumulation;state["steps"]+=1;state["epoch"]=epoch+1
   if state["epoch"]%self.config.checkpoint_every==0:self._save(checkpoint,state)
  checksum=hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest();return {**state,"checksum":checksum,"partitions":[len(x) for x in shards]}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DistributedTrainer.train` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade by reducing world size, resuming from the last checkpoint, or delaying the job. Data partition uniqueness, finite updates, checkpoint checksum, and incompatible-resume checks fail closed.

**Implementation evidence.** [`ailab/distributed_training.py · TrainingConfig.validate`](../../ailab/distributed_training.py) is the concrete control point used by this project:

```python
def validate(self):
  if self.world_size<1:raise ValueError("world_size must be positive")
  if self.epochs<1:raise ValueError("epochs must be positive")
  if not math.isfinite(self.learning_rate) or self.learning_rate<=0:raise ValueError("learning_rate must be finite and positive")
  if self.gradient_accumulation<1 or self.checkpoint_every<1:raise ValueError("accumulation and checkpoint cadence must be positive")
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `TrainingConfig.validate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track samples/rank, step/epoch time, throughput, loss, gradient norm, rank skew/stragglers, collective failures, checkpoint duration/age, restart count, wasted accelerator time, and resumed-vs-clean determinism.

**Implementation evidence.** [`ailab/distributed_training.py · DistributedTrainer.partition`](../../ailab/distributed_training.py) is the concrete control point used by this project:

```python
def partition(self,data:list[Sample])->list[list[Sample]]:
  if not data:raise ValueError("training data cannot be empty")
  return [data[rank::self.config.world_size] for rank in range(self.config.world_size)]
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DistributedTrainer.partition` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Adopt real DDP/FSDP, elastic rendezvous, sharded checkpoints, topology-aware placement, data locality, and hierarchical collectives. Multi-region synchronous training is usually avoided; adversarial jobs need GPU quotas and sandboxed inputs.

**Implementation evidence.** [`ailab/distributed_training.py · framework_inventory`](../../ailab/distributed_training.py) is the concrete control point used by this project:

```python
def framework_inventory()->dict[str,bool]:
 import importlib.util
 return {name:importlib.util.find_spec(name) is not None for name in ("torch","tensorflow","jax")}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `framework_inventory` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns cluster/rendezvous, placement, distributed checkpoint storage, identity, quotas, telemetry, and failure recovery. Model teams own architecture, optimizer, data semantics, convergence policy, and checkpoint compatibility migration.

**Implementation evidence.** [`ailab/distributed_training.py · DistributedTrainer.train`](../../ailab/distributed_training.py) is the concrete control point used by this project:

```python
def train(self,data:list[Sample],run_id:str="run",fail_at:tuple[int,int]|None=None,resume:bool=False)->dict:
  if not run_id or "/" in run_id or ".." in run_id:raise ValueError("unsafe run_id")
  shards=self.partition(data)
  if any(not shard for shard in shards):raise ValueError("world_size cannot exceed sample count")
  checkpoint=self.root/f"{run_id}.json";state={"epoch":0,"weight":0.0,"steps":0}
  if resume:
   if not checkpoint.exists():raise TrainingError("checkpoint not found")
   state=json.loads(checkpoint.read_text())
  for epoch in range(state["epoch"],self.config.epochs):
   gradients=[]
   for rank,shard in enumerate(shards):
    if fail_at==(epoch,rank):self._save(checkpoint,{**state,"epoch":epoch});raise TrainingError(f"worker {rank} failed")
    gradients.append(sum(2*s.x*(state["weight"]*s.x-s.y) for s in shard)/len(shard))
   gradient=sum(gradients)/len(gradients)
   state["weight"]-=self.config.learning_rate*gradient/self.config.gradient_accumulation;state["steps"]+=1;state["epoch"]=epoch+1
   if state["epoch"]%self.config.checkpoint_every==0:self._save(checkpoint,state)
  checksum=hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest();return {**state,"checksum":checksum,"partitions":[len(x) for x in shards]}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DistributedTrainer.train` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
