# Production reasoning — Multi-cloud ML control plane

## Why this project exists

Plans must enforce network, encryption, budget, integrity, idempotency, drift and failover policy. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- invalid identity/provider/region
- zero replicas/budget
- public/unencrypted policy denial
- unknown instance
- provider matrix
- idempotent apply
- tampered plan
- drift, reconciliation and failover

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

Local planning avoids cloud cost; real AWS/GCP/Azure SDKs remain isolated adapters behind the control plane.

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

**Staff/Principal answer.** Provisioning public or unencrypted ML resources is the costliest invariant because one bad plan creates data exposure across a provider boundary. Network, encryption, identity, budget, and plan integrity must be policy-gated before apply.

**Implementation evidence.** [`ailab/cloud_control_plane.py · CloudMLControlPlane.plan`](../../ailab/cloud_control_plane.py) is the concrete control point used by this project:

```python
def plan(self,spec:DeploymentSpec)->dict:
  spec.validate()
  if not spec.private_network or not spec.encrypted:raise PolicyViolation("private networking and encryption are mandatory")
  if spec.instance_type not in self.PRICES:raise ValueError("unknown instance type")
  cost=self.PRICES[spec.instance_type]*spec.replicas
  if cost>spec.monthly_budget:raise PolicyViolation("estimated cost exceeds budget")
  digest=hashlib.sha256(json.dumps(asdict(spec),sort_keys=True).encode()).hexdigest();return {"spec":asdict(spec),"estimated_monthly_cost":cost,"plan_id":digest}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `CloudMLControlPlane.plan` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** Apply linearizes when the verified plan checksum and desired resource state are recorded for the deployment identity. Provider request submission alone is ambiguous; production adapters also use provider idempotency tokens.

**Implementation evidence.** [`ailab/cloud_control_plane.py · CloudMLControlPlane.apply`](../../ailab/cloud_control_plane.py) is the concrete control point used by this project:

```python
def apply(self,plan:dict)->str:
  spec=DeploymentSpec(**plan["spec"]);expected=self.plan(spec)
  if expected["plan_id"]!=plan.get("plan_id"):raise PolicyViolation("plan integrity failure")
  if spec.name in self.desired and self.desired[spec.name]==plan:return "unchanged"
  self.desired[spec.name]=plan;self.actual[spec.name]=dict(plan["spec"]);self.audit.append({"action":"apply","name":spec.name,"plan_id":plan["plan_id"]});return "applied"
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `CloudMLControlPlane.apply` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** Versioned desired state is authoritative for intent; provider observations are authoritative for actual state. Reconciliation is bounded to managed fields/resources in the plan and must not overwrite unowned provider configuration.

**Implementation evidence.** [`ailab/cloud_control_plane.py · CloudMLControlPlane.drift`](../../ailab/cloud_control_plane.py) is the concrete control point used by this project:

```python
def drift(self,name:str)->dict:
  if name not in self.desired:raise KeyError(name)
  desired=self.desired[name]["spec"];actual=self.actual.get(name,{});changes={key:{"desired":value,"actual":actual.get(key)} for key,value in desired.items() if actual.get(key)!=value};return {"drifted":bool(changes),"changes":changes}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `CloudMLControlPlane.drift` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade by staying on the current region/provider, reducing replicas within SLO, or producing a reviewed failover plan. Encryption, private networking, identity, plan checksum, provider support, and budget ceiling fail closed.

**Implementation evidence.** [`ailab/cloud_control_plane.py · CloudMLControlPlane.failover`](../../ailab/cloud_control_plane.py) is the concrete control point used by this project:

```python
def failover(self,name:str,target_region:str)->dict:
  if not target_region:raise ValueError("target region required")
  if name not in self.desired:raise KeyError(name)
  current=DeploymentSpec(**self.desired[name]["spec"]);replacement=DeploymentSpec(**{**asdict(current),"region":target_region});plan=self.plan(replacement);self.apply(plan);return plan
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `CloudMLControlPlane.failover` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track plan/policy rejection, apply success/idempotency, provider API errors, desired/actual drift by field, reconciliation age, quota/capacity, projected/actual cost, regional health, failover readiness, and security posture.

**Implementation evidence.** [`ailab/cloud_control_plane.py · CloudMLControlPlane.drift`](../../ailab/cloud_control_plane.py) is the concrete control point used by this project:

```python
def drift(self,name:str)->dict:
  if name not in self.desired:raise KeyError(name)
  desired=self.desired[name]["spec"];actual=self.actual.get(name,{});changes={key:{"desired":value,"actual":actual.get(key)} for key,value in desired.items() if actual.get(key)!=value};return {"drifted":bool(changes),"changes":changes}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `CloudMLControlPlane.drift` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Use asynchronous provider adapters, durable operations, rate/quota management, regional controllers, policy-as-code, and eventual-consistency reconciliation. Adversarial tenants require scoped credentials, budgets, resource allowlists, and immutable audit.

**Implementation evidence.** [`ailab/cloud_control_plane.py · CloudMLControlPlane.reconcile`](../../ailab/cloud_control_plane.py) is the concrete control point used by this project:

```python
def reconcile(self,name:str):
  report=self.drift(name)
  if report["drifted"]:self.actual[name]=dict(self.desired[name]["spec"]);self.audit.append({"action":"reconcile","name":name})
  return report
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `CloudMLControlPlane.reconcile` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns provider abstraction, credentials, policy, networking/encryption defaults, budgets, drift, reconciliation, failover, and audit. Application teams own workload SLO, data residency, capacity shape, acceptable providers/regions, and failover business approval.

**Implementation evidence.** [`ailab/cloud_control_plane.py · DeploymentSpec.validate`](../../ailab/cloud_control_plane.py) is the concrete control point used by this project:

```python
def validate(self):
  if not self.name or not self.name.replace("-","").isalnum():raise ValueError("invalid deployment name")
  if self.provider not in {"aws","gcp","azure"}:raise ValueError("unsupported provider")
  if not self.region or not self.instance_type:raise ValueError("region and instance type required")
  if self.replicas<1 or self.monthly_budget<=0:raise ValueError("replicas and budget must be positive")
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `DeploymentSpec.validate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
