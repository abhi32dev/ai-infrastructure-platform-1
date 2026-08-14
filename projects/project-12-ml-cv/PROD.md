# Production reasoning — ML and computer-vision lifecycle

## Why this project exists

Data, artifacts, promotion, drift and rollback must remain reproducible and measurable. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- empty/non-finite data
- split determinism
- training convergence
- metric boundaries
- artifact schema
- promotion and rollback
- drift/retraining trigger
- detection, IoU and tracking state

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

NumPy exposes lifecycle invariants cheaply; framework execution is added separately in Project 19.

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

**Staff/Principal answer.** Serving an untraceable or corrupted artifact is the costliest invariant because rollback, audit, and reproducibility all fail simultaneously. Data/version lineage, checksum integrity, promotion evidence, and serving identity must stay connected.

**Implementation evidence.** [`ailab/ml_lifecycle.py · ModelRegistry.register`](../../ailab/ml_lifecycle.py) is the concrete control point used by this project:

```python
def register(self,model:LogisticModel,metrics:Metrics,mean,version:str)->ModelArtifact:
  artifact=ModelArtifact(version,model.weights.tolist(),model.bias,asdict(metrics),np.asarray(mean).tolist(),time.time());(self.path/f"{version}.json").write_text(json.dumps(asdict(artifact),indent=2));self.data["versions"][version]=asdict(artifact);self._save();return artifact
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ModelRegistry.register` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** Model registration linearizes when the versioned artifact and metadata are atomically persisted; promotion linearizes when the production pointer changes after gates pass. Training completion in worker memory is not durable release state.

**Implementation evidence.** [`ailab/ml_lifecycle.py · ModelRegistry.promote`](../../ailab/ml_lifecycle.py) is the concrete control point used by this project:

```python
def promote(self,version,min_f1=.8):
  if version not in self.data["versions"]:raise ValueError("unknown model version")
  if self.data["versions"][version]["metrics"]["f1"]<min_f1:raise ValueError("model failed promotion quality gate")
  prior=self.data["production"];self.data["production"]=version;self.data["history"].append({"from":prior,"to":version,"at":time.time()});self._save()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ModelRegistry.promote` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The immutable registry artifact is authoritative for model contents and lineage; the production pointer is authoritative for serving intent. Reconciliation verifies checksum and pointer/version existence within the bounded registry.

**Implementation evidence.** [`ailab/ml_lifecycle.py · ModelRegistry.load`](../../ailab/ml_lifecycle.py) is the concrete control point used by this project:

```python
def load(self,version=None)->LogisticModel:
  version=version or self.data["production"]
  if not version:raise ValueError("no production model")
  a=self.data["versions"][version];m=LogisticModel(len(a["weights"]));m.weights=np.array(a["weights"]);m.bias=a["bias"];return m
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ModelRegistry.load` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade by rolling back to the last approved model or using a safe baseline. Artifact integrity, input schema, promotion thresholds, tenant policy, and invalid/non-finite predictions fail closed.

**Implementation evidence.** [`ailab/ml_lifecycle.py · ModelRegistry.rollback`](../../ailab/ml_lifecycle.py) is the concrete control point used by this project:

```python
def rollback(self):
  history=self.data["history"]
  if not history or history[-1]["from"] is None:raise ValueError("no previous production version")
  self.data["production"]=history[-1]["from"];self.data["history"].append({"from":history[-1]["to"],"to":history[-1]["from"],"at":time.time()});self._save()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ModelRegistry.rollback` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track data validation failures, training convergence, slice metrics, calibration, artifact checksum, promotion blocks, serving version, prediction drift, feature drift, retraining outcomes, and CV detector/tracker continuity.

**Implementation evidence.** [`ailab/ml_lifecycle.py · ModelRegistry.drift`](../../ailab/ml_lifecycle.py) is the concrete control point used by this project:

```python
def drift(self,x,version=None,threshold=.5):
  version=version or self.data["production"];baseline=np.array(self.data["versions"][version]["feature_mean"]);delta=np.abs(x.mean(axis=0)-baseline);return {"max_mean_shift":float(delta.max()),"per_feature":delta.tolist(),"drifted":bool((delta>threshold).any()),"retrain_recommended":bool((delta>threshold).any())}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ModelRegistry.drift` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Use distributed training/data validation, immutable object artifacts, a replicated registry, regional serving pointers, and staged rollout. At 100× data, incremental validation and lineage indexing are required; adversarial data needs poisoning checks.

**Implementation evidence.** [`ailab/ml_lifecycle.py · LogisticModel.train`](../../ailab/ml_lifecycle.py) is the concrete control point used by this project:

```python
def train(self,x,y,epochs=300,learning_rate=.1):
  validate(x,y)
  for _ in range(epochs):
   p=self.predict_proba(x);error=p-y;self.weights-=learning_rate*(x.T@error/len(x));self.bias-=learning_rate*error.mean()
  return self
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `LogisticModel.train` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns artifact/schema contracts, registry, lineage, deployment gates, monitoring, and rollback. Model teams own features, labels, training logic, evaluation slices, acceptance thresholds, and accountable interpretation of drift.

**Implementation evidence.** [`ailab/ml_lifecycle.py · ModelRegistry.register`](../../ailab/ml_lifecycle.py) is the concrete control point used by this project:

```python
def register(self,model:LogisticModel,metrics:Metrics,mean,version:str)->ModelArtifact:
  artifact=ModelArtifact(version,model.weights.tolist(),model.bias,asdict(metrics),np.asarray(mean).tolist(),time.time());(self.path/f"{version}.json").write_text(json.dumps(asdict(artifact),indent=2));self.data["versions"][version]=asdict(artifact);self._save();return artifact
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ModelRegistry.register` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
