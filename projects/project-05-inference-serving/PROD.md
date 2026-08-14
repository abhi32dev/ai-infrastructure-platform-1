# Production reasoning — Inference serving

## Why this project exists

Bounded work, deadlines and rollback protect availability under overload or bad releases. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- empty/malformed requests
- queue saturation
- deadline expiration
- dynamic batch boundaries
- model output validation
- canary failure and fallback
- rollback
- graceful drain under concurrency

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

Threads model queueing semantics cheaply; production uses async/network servers and accelerator-aware workers.

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

**Staff/Principal answer.** Unbounded queue growth is the most expensive availability violation because it converts overload into memory exhaustion and fleet-wide tail latency. Admission, deadlines, and bounded batching must reject early rather than accept work the server cannot finish.

**Implementation evidence.** [`ailab/inference_server.py · BatchedInferenceServer.infer`](../../ailab/inference_server.py) is the concrete control point used by this project:

```python
def infer(self, request: InferenceRequest) -> InferenceResponse:
        if not self.ready_event.is_set() or self.stop_event.is_set(): raise NotReady("server is not accepting traffic")
        now=time.perf_counter(); request_id=request.request_id or uuid.uuid4().hex; item=_Work(request,request_id,now,now+request.deadline_seconds,threading.Event())
        try: self.work.put_nowait(item)
        except queue.Full as exc: self.metrics["shed"]+=1; raise Overloaded("inference queue is full") from exc
        if not item.event.wait(request.deadline_seconds): self.metrics["deadline_exceeded"]+=1; raise DeadlineExceeded("request deadline expired while waiting")
        if item.error: raise item.error
        assert item.response is not None; return item.response
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `BatchedInferenceServer.infer` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** The request linearizes when its future is resolved with a validated output or typed terminal error. Queue insertion is only admission; callers must use request identity if retrying across an ambiguous network disconnect.

**Implementation evidence.** [`ailab/inference_server.py · BatchedInferenceServer._loop`](../../ailab/inference_server.py) is the concrete control point used by this project:

```python
def _loop(self) -> None:
        while not self.stop_event.is_set() or not self.work.empty():
            try: first=self.work.get(timeout=0.02)
            except queue.Empty: continue
            batch=[first]; started=time.perf_counter()
            while len(batch)<self.max_batch_size:
                remaining=self.max_batch_wait-(time.perf_counter()-started)
                if remaining<=0: break
                try: batch.append(self.work.get(timeout=remaining))
                except queue.Empty: break
            active=[]
            for item in batch:
                if time.perf_counter()>item.deadline:
                    item.error=DeadlineExceeded("deadline expired before inference"); item.event.set(); self.metrics["deadline_exceeded"]+=1
                else: active.append(item)
            if not active: continue
            inference_start=time.perf_counter()
            try:
                outputs=self.model([item.request.payload for item in active])
                if len(outputs)!=len(active): raise ServingError("model output count does not match batch")
                inference_ms=(time.perf_counter()-inference_start)*1000
                for item,output in zip(active,outputs):
                    queue_ms=(inference_start-item.submitted)*1000; item.response=InferenceResponse(item.request_id,output,self.version,queue_ms,inference_ms,len(active)); item.event.set(); self.metrics["completed"]+=1; self.latencies.append(queue_ms+inference_ms)
                self.metrics["batches"]+=1; self.metrics["max_batch_size"]=max(self.metrics["max_batch_size"],len(active))
            except Exception as exc:
                self.metrics["model_errors"]+=len(active)
                for item in active: item.error=ServingError(f"model execution failed: {exc}"); item.event.set()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `BatchedInferenceServer._loop` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The deployment controller's stable/canary configuration is authoritative for routing; worker queues are ephemeral. Reconciliation is bounded to draining accepted work and restoring stable routing, not migrating arbitrary in-flight execution between model versions.

**Implementation evidence.** [`ailab/inference_server.py · CanaryDeployment.rollback`](../../ailab/inference_server.py) is the concrete control point used by this project:

```python
def rollback(self) -> None: self.rolled_back=True
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `CanaryDeployment.rollback` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade by shedding overload, reducing batch wait, disabling canary traffic, or routing to stable capacity. Deadline correctness, output cardinality, readiness, and tenant limits fail closed; late or malformed results are not successful responses.

**Implementation evidence.** [`ailab/inference_server.py · BatchedInferenceServer._loop`](../../ailab/inference_server.py) is the concrete control point used by this project:

```python
def _loop(self) -> None:
        while not self.stop_event.is_set() or not self.work.empty():
            try: first=self.work.get(timeout=0.02)
            except queue.Empty: continue
            batch=[first]; started=time.perf_counter()
            while len(batch)<self.max_batch_size:
                remaining=self.max_batch_wait-(time.perf_counter()-started)
                if remaining<=0: break
                try: batch.append(self.work.get(timeout=remaining))
                except queue.Empty: break
            active=[]
            for item in batch:
                if time.perf_counter()>item.deadline:
                    item.error=DeadlineExceeded("deadline expired before inference"); item.event.set(); self.metrics["deadline_exceeded"]+=1
                else: active.append(item)
            if not active: continue
            inference_start=time.perf_counter()
            try:
                outputs=self.model([item.request.payload for item in active])
                if len(outputs)!=len(active): raise ServingError("model output count does not match batch")
                inference_ms=(time.perf_counter()-inference_start)*1000
                for item,output in zip(active,outputs):
                    queue_ms=(inference_start-item.submitted)*1000; item.response=InferenceResponse(item.request_id,output,self.version,queue_ms,inference_ms,len(active)); item.event.set(); self.metrics["completed"]+=1; self.latencies.append(queue_ms+inference_ms)
                self.metrics["batches"]+=1; self.metrics["max_batch_size"]=max(self.metrics["max_batch_size"],len(active))
            except Exception as exc:
                self.metrics["model_errors"]+=len(active)
                for item in active: item.error=ServingError(f"model execution failed: {exc}"); item.event.set()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `BatchedInferenceServer._loop` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Monitor queue depth, admission rejection, expired-before-execution, batch-size distribution, model errors, output validation, p50/p95/p99 latency, tokens/sec, GPU utilization, and canary-vs-stable error/latency deltas.

**Implementation evidence.** [`ailab/inference_server.py · BatchedInferenceServer.health`](../../ailab/inference_server.py) is the concrete control point used by this project:

```python
def health(self) -> dict:
        return {"live":self.worker.is_alive(),"ready":self.ready_event.is_set() and not self.stop_event.is_set(),"queue_depth":self.work.qsize(),"model_version":self.version,"metrics":dict(self.metrics)}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `BatchedInferenceServer.health` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Scale replicas and accelerator workers independently, use topology-aware load balancing, model-weight locality, priority queues, and regional admission budgets. Adversarial tenants need per-tenant concurrency and token limits before the shared queue.

**Implementation evidence.** [`ailab/inference_server.py · BatchedInferenceServer.infer`](../../ailab/inference_server.py) is the concrete control point used by this project:

```python
def infer(self, request: InferenceRequest) -> InferenceResponse:
        if not self.ready_event.is_set() or self.stop_event.is_set(): raise NotReady("server is not accepting traffic")
        now=time.perf_counter(); request_id=request.request_id or uuid.uuid4().hex; item=_Work(request,request_id,now,now+request.deadline_seconds,threading.Event())
        try: self.work.put_nowait(item)
        except queue.Full as exc: self.metrics["shed"]+=1; raise Overloaded("inference queue is full") from exc
        if not item.event.wait(request.deadline_seconds): self.metrics["deadline_exceeded"]+=1; raise DeadlineExceeded("request deadline expired while waiting")
        if item.error: raise item.error
        assert item.response is not None; return item.response
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `BatchedInferenceServer.infer` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns serving runtime, admission, batching, health, deployment, telemetry, and rollback. Application teams own model artifacts, preprocessing/postprocessing contracts, latency classes, correctness tests, and approved fallback semantics.

**Implementation evidence.** [`ailab/inference_server.py · CanaryDeployment.infer`](../../ailab/inference_server.py) is the concrete control point used by this project:

```python
def infer(self, request: InferenceRequest) -> InferenceResponse:
        key=request.request_id or request.payload; bucket=int(hashlib.sha256(key.encode()).hexdigest()[:8],16)%100
        target=self.canary if not self.rolled_back and bucket<self.canary_percent else self.stable
        try: return target.infer(request)
        except ServingError:
            if target is self.canary: return self.stable.infer(request)
            raise
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `CanaryDeployment.infer` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
