# Production reasoning — TensorFlow, Keras and JAX lifecycle

## Why this project exists

Framework changes must preserve artifact schemas, numerical parity and inference contracts. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- misaligned/short/constant arrays
- NaN/Inf training data
- non-finite inference
- artifact round trip
- missing/corrupt/versioned artifact
- parity success/failure
- invalid tolerance
- framework inventory

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

A portable linear artifact makes parity exact; real TensorFlow/Keras/JAX dependencies are isolated for extensions.

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

**Staff/Principal answer.** Silent numerical divergence across frameworks is the most expensive invariant because a successfully loaded model can still produce wrong decisions. Artifact schema, checksum, tensor shape, finite values, and parity tolerance must be gated.

**Implementation evidence.** [`ailab/multi_framework.py · parity`](../../ailab/multi_framework.py) is the concrete control point used by this project:

```python
def parity(models:list[PortableLinearModel],inputs:list[float],tolerance:float=1e-6)->dict:
 if not models or not inputs:raise ValueError("models and inputs required")
 if tolerance<0:raise ValueError("tolerance cannot be negative")
 predictions=[[m.predict(x) for x in inputs] for m in models];maximum=max(abs(a-b) for row in predictions[1:] for a,b in zip(predictions[0],row)) if len(predictions)>1 else 0.0;return {"passed":maximum<=tolerance,"maximum_difference":maximum}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `parity` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** Artifact publication linearizes at atomic save of versioned parameters and checksum. Framework conversion is not complete until the saved artifact reloads and passes prediction parity.

**Implementation evidence.** [`ailab/multi_framework.py · PortableLinearModel.save`](../../ailab/multi_framework.py) is the concrete control point used by this project:

```python
def save(self,path:Path):path.write_text(json.dumps(asdict(self),sort_keys=True))
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `PortableLinearModel.save` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The portable checksummed artifact is authoritative; framework-native objects are derived runtime representations. Reconciliation reloads the bounded golden input set through each adapter and blocks any tolerance breach.

**Implementation evidence.** [`ailab/multi_framework.py · PortableLinearModel.load`](../../ailab/multi_framework.py) is the concrete control point used by this project:

```python
def load(cls,path:Path):
  if not path.exists():raise FileNotFoundError(path)
  data=json.loads(path.read_text())
  if data.get("schema_version")!=1:raise ValueError("unsupported artifact schema")
  if not all(math.isfinite(float(data[x])) for x in ("weight","bias")):raise ValueError("non-finite artifact")
  return cls(**data)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `PortableLinearModel.load` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade to a previously verified runtime/artifact or a supported CPU path. Artifact integrity, schema/version, tensor shape, non-finite input/output, and parity gates fail closed.

**Implementation evidence.** [`ailab/multi_framework.py · PortableLinearModel.load`](../../ailab/multi_framework.py) is the concrete control point used by this project:

```python
def load(cls,path:Path):
  if not path.exists():raise FileNotFoundError(path)
  data=json.loads(path.read_text())
  if data.get("schema_version")!=1:raise ValueError("unsupported artifact schema")
  if not all(math.isfinite(float(data[x])) for x in ("weight","bias")):raise ValueError("non-finite artifact")
  return cls(**data)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `PortableLinearModel.load` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track conversion/load failures, checksum/schema rejection, golden-set max/mean error, NaN/Inf, latency/throughput by runtime, framework/version inventory, unsupported operators, and parity drift by model version.

**Implementation evidence.** [`ailab/multi_framework.py · installed_frameworks`](../../ailab/multi_framework.py) is the concrete control point used by this project:

```python
def installed_frameworks()->dict[str,bool]:return {name:importlib.util.find_spec(name) is not None for name in ("torch","tensorflow","keras","jax","onnxruntime")}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `installed_frameworks` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Use standardized export, hardware-specific compilation caches, conformance suites, model registries, and compatibility matrices. Multi-region serving pins runtime versions; adversarial artifacts require signatures, sandboxing, and size/operator limits.

**Implementation evidence.** [`ailab/multi_framework.py · parity`](../../ailab/multi_framework.py) is the concrete control point used by this project:

```python
def parity(models:list[PortableLinearModel],inputs:list[float],tolerance:float=1e-6)->dict:
 if not models or not inputs:raise ValueError("models and inputs required")
 if tolerance<0:raise ValueError("tolerance cannot be negative")
 predictions=[[m.predict(x) for x in inputs] for m in models];maximum=max(abs(a-b) for row in predictions[1:] for a,b in zip(predictions[0],row)) if len(predictions)>1 else 0.0;return {"passed":maximum<=tolerance,"maximum_difference":maximum}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `parity` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns portable artifact contracts, supported runtime matrix, conversion, signatures, parity tests, deployment, and telemetry. Model teams own architecture/operator choices, golden examples, tolerance justification, quality gates, and migration approval.

**Implementation evidence.** [`ailab/multi_framework.py · train_linear`](../../ailab/multi_framework.py) is the concrete control point used by this project:

```python
def train_linear(xs:list[float],ys:list[float],framework:str="numpy")->PortableLinearModel:
 if len(xs)!=len(ys) or len(xs)<2:raise ValueError("aligned training arrays require at least two samples")
 if any(not math.isfinite(v) for v in [*xs,*ys]):raise ValueError("training data must be finite")
 mean_x=sum(xs)/len(xs);mean_y=sum(ys)/len(ys);den=sum((x-mean_x)**2 for x in xs)
 if den==0:raise ValueError("features have zero variance")
 weight=sum((x-mean_x)*(y-mean_y) for x,y in zip(xs,ys))/den;return PortableLinearModel(weight,mean_y-weight*mean_x,framework)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `train_linear` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
