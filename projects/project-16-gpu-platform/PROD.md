# Production reasoning — Kubernetes GPU platform

## Why this project exists

Scheduling must respect GPU type, capacity, health, tenant quota and interruption recovery. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- invalid/duplicate nodes
- invalid workloads
- GPU-type mismatch
- insufficient capacity
- tenant quota
- idempotent schedule
- completion reclamation
- spot drain and autoscale plan

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

The scheduler is executable without a GPU; Kubernetes client/YAML dependencies map decisions to real resources.

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

**Staff/Principal answer.** Oversubscribing or cross-charging GPUs is the costliest invariant because it creates workload failure and direct financial leakage. Capacity, device type, health, allocation identity, and tenant quota must change atomically.

**Implementation evidence.** [`ailab/gpu_platform.py · GPUPlatform.schedule`](../../ailab/gpu_platform.py) is the concrete control point used by this project:

```python
def schedule(self,workload:Workload)->str:
  workload.validate()
  if workload.name in self.workloads:return self.workloads[workload.name]
  used=sum(w.gpus for w,n in getattr(self,"_requests",[]) if w.tenant==workload.tenant)
  if workload.tenant in self.quotas and used+workload.gpus>self.quotas[workload.tenant]:raise SchedulingError("tenant quota exceeded")
  candidates=[n for n in self.nodes.values() if n.healthy and n.available>=workload.gpus and (workload.gpu_type is None or n.gpu_type==workload.gpu_type)]
  if not candidates:raise SchedulingError("no feasible GPU node")
  node=sorted(candidates,key=lambda n:(n.spot,-n.available,n.name))[0];node.allocations[workload.name]=workload.gpus;self.workloads[workload.name]=node.name
  if not hasattr(self,"_requests"):self._requests=[]
  self._requests.append((workload,node.name));return node.name
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GPUPlatform.schedule` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** Scheduling linearizes when the placement and node allocation are recorded together for the workload ID. A repeated request returns that placement; completion linearizes when exactly that allocation is reclaimed.

**Implementation evidence.** [`ailab/gpu_platform.py · GPUPlatform.schedule`](../../ailab/gpu_platform.py) is the concrete control point used by this project:

```python
def schedule(self,workload:Workload)->str:
  workload.validate()
  if workload.name in self.workloads:return self.workloads[workload.name]
  used=sum(w.gpus for w,n in getattr(self,"_requests",[]) if w.tenant==workload.tenant)
  if workload.tenant in self.quotas and used+workload.gpus>self.quotas[workload.tenant]:raise SchedulingError("tenant quota exceeded")
  candidates=[n for n in self.nodes.values() if n.healthy and n.available>=workload.gpus and (workload.gpu_type is None or n.gpu_type==workload.gpu_type)]
  if not candidates:raise SchedulingError("no feasible GPU node")
  node=sorted(candidates,key=lambda n:(n.spot,-n.available,n.name))[0];node.allocations[workload.name]=workload.gpus;self.workloads[workload.name]=node.name
  if not hasattr(self,"_requests"):self._requests=[]
  self._requests.append((workload,node.name));return node.name
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GPUPlatform.schedule` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The control-plane allocation ledger is authoritative for logical ownership; node-reported availability is observed actual state. Reconciliation is bounded by registered nodes/workloads and never frees capacity without matching allocation identity.

**Implementation evidence.** [`ailab/gpu_platform.py · GPUPlatform.complete`](../../ailab/gpu_platform.py) is the concrete control point used by this project:

```python
def complete(self,name:str):
  node_name=self.workloads.pop(name,None)
  if node_name:self.nodes[node_name].allocations.pop(name,None)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GPUPlatform.complete` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade by queueing, choosing a policy-approved alternate node, draining spot capacity, or scaling out. GPU compatibility, quota, idempotency, health, and non-overcommit fail closed.

**Implementation evidence.** [`ailab/gpu_platform.py · GPUPlatform.schedule`](../../ailab/gpu_platform.py) is the concrete control point used by this project:

```python
def schedule(self,workload:Workload)->str:
  workload.validate()
  if workload.name in self.workloads:return self.workloads[workload.name]
  used=sum(w.gpus for w,n in getattr(self,"_requests",[]) if w.tenant==workload.tenant)
  if workload.tenant in self.quotas and used+workload.gpus>self.quotas[workload.tenant]:raise SchedulingError("tenant quota exceeded")
  candidates=[n for n in self.nodes.values() if n.healthy and n.available>=workload.gpus and (workload.gpu_type is None or n.gpu_type==workload.gpu_type)]
  if not candidates:raise SchedulingError("no feasible GPU node")
  node=sorted(candidates,key=lambda n:(n.spot,-n.available,n.name))[0];node.allocations[workload.name]=workload.gpus;self.workloads[workload.name]=node.name
  if not hasattr(self,"_requests"):self._requests=[]
  self._requests.append((workload,node.name));return node.name
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GPUPlatform.schedule` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track allocatable/allocated GPUs by type/node/tenant, pending demand, fragmentation, placement failure reason, quota rejection, idle cost, job startup, drain/eviction, completion reclaim, spot interruption, and autoscale accuracy.

**Implementation evidence.** [`ailab/gpu_platform.py · GPUPlatform.autoscale_plan`](../../ailab/gpu_platform.py) is the concrete control point used by this project:

```python
def autoscale_plan(self,pending:list[Workload])->dict:
  demand=sum(w.gpus for w in pending);available=sum(n.available for n in self.nodes.values() if n.healthy);return {"pending_gpus":demand,"available_gpus":available,"nodes_to_add":max(0,demand-available)}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GPUPlatform.autoscale_plan` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Use Kubernetes scheduler plugins, device plugins, topology labels, gang scheduling, quota hierarchies, and separate on-demand/spot pools. Multi-region needs independent capacity domains; adversarial tenants require workload isolation and hard GPU-hour budgets.

**Implementation evidence.** [`ailab/gpu_platform.py · GPUPlatform.add_node`](../../ailab/gpu_platform.py) is the concrete control point used by this project:

```python
def add_node(self,node:GPUNode):
  if not node.name.strip() or node.capacity<1:raise ValueError("invalid node")
  if node.name in self.nodes:raise ValueError("duplicate node")
  self.nodes[node.name]=node
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GPUPlatform.add_node` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns node/device inventory, placement, quota, preemption, autoscaling, health, and cost attribution. Application teams own accelerator requirement, distributed topology, checkpointability, priority justification, and interruption tolerance.

**Implementation evidence.** [`ailab/gpu_platform.py · Workload.validate`](../../ailab/gpu_platform.py) is the concrete control point used by this project:

```python
def validate(self):
  if not self.name.strip():raise ValueError("workload name required")
  if self.gpus<1:raise ValueError("GPU request must be positive")
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `Workload.validate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
