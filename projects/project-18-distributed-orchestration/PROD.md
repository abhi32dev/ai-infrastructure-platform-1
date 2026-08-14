# Production reasoning — Distributed ML orchestration

## Why this project exists

DAG validity, placement, retry and object-store bounds make distributed work predictable. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- invalid cluster capacity
- empty/duplicate tasks
- forward dependencies
- invalid resources
- retry success/exhaustion
- unschedulable placement
- object-store exhaustion
- actor state and crash

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

The deterministic orchestrator explains Ray primitives; the isolated Ray dependency enables real local actors.

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

**Staff/Principal answer.** Unbounded retries or object-store growth is the costliest operational violation because one DAG can exhaust the whole cluster. DAG validity, resource feasibility, retry budget, and object capacity must be enforced centrally.

**Implementation evidence.** [`ailab/distributed_orchestration.py · Orchestrator.run`](../../ailab/distributed_orchestration.py) is the concrete control point used by this project:

```python
def run(self,tasks:list[Task])->dict:
  self.validate(tasks);context={}
  for task in tasks:
   if task.cpu>self.cpu or task.memory>self.memory:raise OrchestrationError(f"unschedulable task: {task.name}")
   attempts=0
   while True:
    attempts+=1
    try:result=task.handler(context);break
    except Exception as exc:
     self.events.append({"task":task.name,"attempt":attempts,"status":"failed","error":str(exc)})
     if attempts>task.retries:raise OrchestrationError(f"task failed: {task.name}") from exc
   size=len(repr(result).encode())
   if sum(len(repr(x).encode()) for x in self.objects.values())+size>self.object_store:raise OrchestrationError("object store exhausted")
   self.objects[task.name]=result;context[task.name]=result;self.events.append({"task":task.name,"attempt":attempts,"status":"completed"})
  return context
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Orchestrator.run` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** A task linearizes when its output is accepted into the object store and marked complete after execution. Scheduling or worker start is not completion; actor mutation linearizes at the named actor's state update.

**Implementation evidence.** [`ailab/distributed_orchestration.py · Orchestrator.run`](../../ailab/distributed_orchestration.py) is the concrete control point used by this project:

```python
def run(self,tasks:list[Task])->dict:
  self.validate(tasks);context={}
  for task in tasks:
   if task.cpu>self.cpu or task.memory>self.memory:raise OrchestrationError(f"unschedulable task: {task.name}")
   attempts=0
   while True:
    attempts+=1
    try:result=task.handler(context);break
    except Exception as exc:
     self.events.append({"task":task.name,"attempt":attempts,"status":"failed","error":str(exc)})
     if attempts>task.retries:raise OrchestrationError(f"task failed: {task.name}") from exc
   size=len(repr(result).encode())
   if sum(len(repr(x).encode()) for x in self.objects.values())+size>self.object_store:raise OrchestrationError("object store exhausted")
   self.objects[task.name]=result;context[task.name]=result;self.events.append({"task":task.name,"attempt":attempts,"status":"completed"})
  return context
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Orchestrator.run` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The orchestrator's task-state/output map is authoritative for DAG progress; worker-local state is not. Reconciliation is bounded by the finite DAG, declared dependencies, attempts, and object references.

**Implementation evidence.** [`ailab/distributed_orchestration.py · Orchestrator.validate`](../../ailab/distributed_orchestration.py) is the concrete control point used by this project:

```python
def validate(self,tasks:list[Task]):
  names=[x.name for x in tasks]
  if not tasks or any(not x for x in names):raise ValueError("tasks and names are required")
  if len(names)!=len(set(names)):raise ValueError("duplicate task")
  seen=set()
  for task in tasks:
   if task.cpu<1 or task.memory<1 or task.retries<0:raise ValueError("invalid task resources")
   if any(dep not in seen for dep in task.dependencies):raise ValueError("dependency must precede task")
   seen.add(task.name)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Orchestrator.validate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade by retrying declared transient work, delaying resource-heavy tasks, spilling/recomputing objects, or recreating an actor. DAG cycles, over-allocation, retry exhaustion, and corrupted/missing required inputs fail closed.

**Implementation evidence.** [`ailab/distributed_orchestration.py · Orchestrator.run`](../../ailab/distributed_orchestration.py) is the concrete control point used by this project:

```python
def run(self,tasks:list[Task])->dict:
  self.validate(tasks);context={}
  for task in tasks:
   if task.cpu>self.cpu or task.memory>self.memory:raise OrchestrationError(f"unschedulable task: {task.name}")
   attempts=0
   while True:
    attempts+=1
    try:result=task.handler(context);break
    except Exception as exc:
     self.events.append({"task":task.name,"attempt":attempts,"status":"failed","error":str(exc)})
     if attempts>task.retries:raise OrchestrationError(f"task failed: {task.name}") from exc
   size=len(repr(result).encode())
   if sum(len(repr(x).encode()) for x in self.objects.values())+size>self.object_store:raise OrchestrationError("object store exhausted")
   self.objects[task.name]=result;context[task.name]=result;self.events.append({"task":task.name,"attempt":attempts,"status":"completed"})
  return context
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Orchestrator.run` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track runnable/queued/running tasks, dependency wait, placement failure, CPU/memory utilization, attempts, retry exhaustion, object bytes/pressure/eviction, critical-path latency, actor restarts, and recomputation cost.

**Implementation evidence.** [`ailab/distributed_orchestration.py · Orchestrator.run`](../../ailab/distributed_orchestration.py) is the concrete control point used by this project:

```python
def run(self,tasks:list[Task])->dict:
  self.validate(tasks);context={}
  for task in tasks:
   if task.cpu>self.cpu or task.memory>self.memory:raise OrchestrationError(f"unschedulable task: {task.name}")
   attempts=0
   while True:
    attempts+=1
    try:result=task.handler(context);break
    except Exception as exc:
     self.events.append({"task":task.name,"attempt":attempts,"status":"failed","error":str(exc)})
     if attempts>task.retries:raise OrchestrationError(f"task failed: {task.name}") from exc
   size=len(repr(result).encode())
   if sum(len(repr(x).encode()) for x in self.objects.values())+size>self.object_store:raise OrchestrationError("object store exhausted")
   self.objects[task.name]=result;context[task.name]=result;self.events.append({"task":task.name,"attempt":attempts,"status":"completed"})
  return context
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Orchestrator.run` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Use distributed schedulers, leases, autoscaling, locality-aware placement, object spilling, lineage-based reconstruction, and durable workflow state. Multi-region DAGs need data locality; adversarial jobs require namespace and resource quotas.

**Implementation evidence.** [`ailab/distributed_orchestration.py · Orchestrator.actor`](../../ailab/distributed_orchestration.py) is the concrete control point used by this project:

```python
def actor(self,name:str,initial:int=0):
  if not name:raise ValueError("actor name required")
  state={"value":initial,"restarts":0}
  def call(delta:int=0,crash:bool=False):
   if crash:state["restarts"]+=1;raise OrchestrationError("actor crashed")
   state["value"]+=delta;return dict(state)
  return call
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Orchestrator.actor` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns DAG execution, resources, retries, object transport, actor lifecycle, quotas, and telemetry. Application teams own task functions, dependencies, retryability declarations, data semantics, checkpoints, and compensation logic.

**Implementation evidence.** [`ailab/distributed_orchestration.py · Task`](../../ailab/distributed_orchestration.py) is the concrete control point used by this project:

```python
class Task:
 name:str;handler:Callable[[dict],object];dependencies:tuple[str,...]=();cpu:int=1;memory:int=1;retries:int=0
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Task` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
